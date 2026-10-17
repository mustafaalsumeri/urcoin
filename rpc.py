"""
Ur Coin JSON-RPC & Web API Server:
- Serves HTTP REST/RPC endpoints for miners, wallets, and blockchain explorer
- Hosts integrated Web Dashboard on port 9334
"""

import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.parse import urlparse, parse_qs
from typing import Optional

from urcoin.core import (
    Block, BlockHeader, Transaction, calculate_block_reward,
    calculate_next_target, COIN, INITIAL_TARGET, INITIAL_BLOCK_REWARD
)
from urcoin.storage import BlockchainStorage
from urcoin.mempool import Mempool
from urcoin.network import P2PNetwork
from urcoin.wallet import Wallet
from urcoin.miner_gpu import GPUMiner, get_opencl_devices
from urcoin.web_ui import HTML_DASHBOARD

DEFAULT_RPC_PORT = 9334

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class UrCoinRPCServer:
    def __init__(self, storage: BlockchainStorage, mempool: Mempool,
                 p2p: P2PNetwork, wallet: Wallet,
                 host: str = "0.0.0.0", port: int = DEFAULT_RPC_PORT):
        self.storage = storage
        self.mempool = mempool
        self.p2p = p2p
        self.wallet = wallet
        self.host = host
        self.port = port
        self.server: Optional[ThreadedHTTPServer] = None
        self.server_thread: Optional[threading.Thread] = None

        # GPU Miner Integration
        self.gpu_miner: Optional[GPUMiner] = None
        self.mining_thread: Optional[threading.Thread] = None
        self.is_mining = False
        self.reward_address = self.wallet.address

        try:
            self.gpu_miner = GPUMiner(device_index=0)
        except Exception as e:
            print(f"[Miner] Note: Could not pre-initialize GPU miner: {e}")

    def start(self):
        handler_factory = self._create_handler()
        self.server = ThreadedHTTPServer((self.host, self.port), handler_factory)
        print(f"[RPC] Ur Coin Web Dashboard & RPC API available at http://localhost:{self.port}/")

        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()

    def stop(self):
        self.stop_mining()
        if self.server:
            self.server.shutdown()
            self.server.server_close()

    def start_mining(self, reward_address: Optional[str] = None):
        """Start background GPU mining thread."""
        if self.is_mining:
            return
        if reward_address:
            self.reward_address = reward_address

        self.is_mining = True
        self.mining_thread = threading.Thread(target=self._mining_worker, daemon=True)
        self.mining_thread.start()
        print(f"[Miner] Started GPU Mining directly to {self.reward_address}!")

    def stop_mining(self):
        """Stop background GPU mining."""
        self.is_mining = False
        if self.mining_thread:
            self.mining_thread.join(timeout=1.0)
            self.mining_thread = None
        if self.gpu_miner:
            self.gpu_miner.hashrate = 0.0
        print("[Miner] Stopped GPU Mining.")

    def _mining_worker(self):
        """Continuous background GPU mining worker."""
        if not self.gpu_miner:
            try:
                self.gpu_miner = GPUMiner(device_index=0)
            except Exception as e:
                print(f"[Miner] GPU Init error: {e}")
                self.is_mining = False
                return

        nonce_counter = 0
        while self.is_mining:
            try:
                # 1. Fetch mining template
                best_block = self.storage.get_best_block()
                if not best_block:
                    time.sleep(0.5)
                    continue

                height = best_block.header.height + 1
                epoch = height // 10_000
                reward = calculate_block_reward(height)

                # Prepare transactions: Coinbase + Mempool txs
                coinbase_tx = Transaction.create_coinbase(self.reward_address, reward, height)
                mempool_txs = self.mempool.get_transactions_for_block(max_count=200)
                block_txs = [coinbase_tx] + mempool_txs

                # Calculate next target
                past_headers = self.storage.get_past_headers(10)
                next_target = calculate_next_target(past_headers)

                # Construct candidate block
                header = BlockHeader(
                    version=1,
                    prev_hash=best_block.hash,
                    merkle_root="",
                    timestamp=int(time.time()),
                    target=next_target,
                    nonce=0,
                    height=height,
                    epoch=epoch
                )
                candidate_block = Block(header, block_txs)
                candidate_block.header.merkle_root = candidate_block.calculate_merkle_root()
                mining_hash = candidate_block.header.get_mining_hash()

                # Execute GPU batch: 65,536 threads * 32 nonces = ~2.1 million nonces per batch
                batch_size = 65536
                nonces_per_th = 32
                results = self.gpu_miner.search_batch(
                    mining_hash, next_target, epoch,
                    start_nonce=nonce_counter,
                    global_work_size=batch_size,
                    nonces_per_thread=nonces_per_th
                )
                nonce_counter += (batch_size * nonces_per_th)

                # If block found
                if results:
                    winning_nonce, block_hash = results[0]
                    candidate_block.header.nonce = winning_nonce
                    candidate_block.hash = block_hash

                    # Submit to local storage
                    if candidate_block.verify_pow():
                        self.storage.add_block(candidate_block)
                        self.mempool.remove_mined_transactions(block_txs)
                        self.p2p.broadcast_new_block(candidate_block)
                        self.gpu_miner.blocks_found += 1
                        print(f"🎉 [Miner] Mined Block #{candidate_block.header.height}! Hash: {block_hash}")

            except Exception as e:
                print(f"[Miner] Mining worker error: {e}")
                time.sleep(1.0)

    def _create_handler(self):
        outer = self

        class RPCRequestHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass # Suppress noisy HTTP logs in console

            def _send_json(self, data: dict, status: int = 200):
                payload = json.dumps(data).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def _send_html(self, html_str: str):
                payload = html_str.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/" or path == "/index.html":
                    self._send_html(HTML_DASHBOARD)

                elif path == "/api/info":
                    height = outer.storage.get_best_height()
                    best_b = outer.storage.get_best_block()
                    reward = calculate_block_reward(height)
                    supply = (height + 1) * INITIAL_BLOCK_REWARD # Approx
                    past_headers = outer.storage.get_past_headers(10)
                    target = calculate_next_target(past_headers)

                    self._send_json({
                        "height": height,
                        "best_hash": best_b.hash if best_b else "",
                        "circulating_supply": supply,
                        "current_reward": reward,
                        "target": hex(target),
                        "mempool_size": outer.mempool.size()
                    })

                elif path == "/api/blocks":
                    blocks = outer.storage.get_recent_blocks(limit=20)
                    self._send_json(blocks)

                elif path.startswith("/api/block/"):
                    identifier = path.split("/")[-1]
                    block = None
                    if identifier.isdigit():
                        block = outer.storage.get_block_by_height(int(identifier))
                    else:
                        block = outer.storage.get_block_by_hash(identifier)
                    if block:
                        self._send_json(block.to_dict())
                    else:
                        self._send_json({"error": "Block not found"}, status=404)

                elif path == "/api/wallet":
                    balance = outer.storage.get_balance(outer.wallet.address)
                    self._send_json({
                        "address": outer.wallet.address,
                        "balance": balance
                    })

                elif path == "/api/miner/status":
                    dev_name = outer.gpu_miner.device.device_name if (outer.gpu_miner and outer.gpu_miner.device) else "CPU / OpenCL Fallback"
                    self._send_json({
                        "mining": outer.is_mining,
                        "device_name": dev_name,
                        "hashrate": outer.gpu_miner.hashrate if outer.gpu_miner else 0.0,
                        "blocks_found": outer.gpu_miner.blocks_found if outer.gpu_miner else 0,
                        "total_hashes": outer.gpu_miner.total_hashes if outer.gpu_miner else 0,
                        "reward_address": outer.reward_address
                    })

                else:
                    self._send_json({"error": "Not Found"}, status=404)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length).decode("utf-8") if length > 0 else "{}"
                data = json.loads(body) if body else {}

                if path == "/api/miner/start":
                    reward_addr = data.get("reward_address", outer.wallet.address)
                    outer.start_mining(reward_addr)
                    self._send_json({"success": True, "mining": True})

                elif path == "/api/miner/stop":
                    outer.stop_mining()
                    self._send_json({"success": True, "mining": False})

                elif path == "/api/send_tx":
                    try:
                        recipient = data["recipient"]
                        amount_atomic = int(float(data["amount_urc"]) * COIN)
                        utxos = outer.storage.get_utxos_for_address(outer.wallet.address)
                        tx = outer.wallet.create_transaction(recipient, amount_atomic, utxos)
                        ok, msg = outer.mempool.add_transaction(tx)
                        if ok:
                            outer.p2p.broadcast_new_tx(tx)
                            self._send_json({"success": True, "txid": tx.txid})
                        else:
                            self._send_json({"success": False, "error": msg}, status=400)
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=400)

                elif path == "/api/submit_block":
                    try:
                        block = Block.from_dict(data)
                        if block.verify_pow():
                            outer.storage.add_block(block)
                            outer.mempool.remove_mined_transactions(block.transactions)
                            outer.p2p.broadcast_new_block(block)
                            self._send_json({"success": True, "hash": block.hash})
                        else:
                            self._send_json({"success": False, "error": "Invalid Proof-of-Work"}, status=400)
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=400)

                else:
                    self._send_json({"error": "Not Found"}, status=404)

        return RPCRequestHandler
