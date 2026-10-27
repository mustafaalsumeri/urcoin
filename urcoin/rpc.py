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
    calculate_next_target, circulating_supply, COIN
)
from urcoin.storage import BlockchainStorage
from urcoin.mempool import Mempool
from urcoin.network import P2PNetwork
from urcoin.wallet import Wallet
from urcoin.miner_gpu import GPUMiner, get_opencl_devices
from urcoin.web_ui import HTML_DASHBOARD
from urcoin.auth import (
    RPC_COOKIE_HEADER, load_or_create_rpc_cookie, DEFAULT_COOKIE_PATH
)
import hmac

DEFAULT_RPC_PORT = 9334

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class UrCoinRPCServer:
    def __init__(self, storage: BlockchainStorage, mempool: Mempool,
                 p2p: P2PNetwork, wallet: Wallet,
                 host: str = "127.0.0.1", port: int = DEFAULT_RPC_PORT,
                 cookie_path: str = DEFAULT_COOKIE_PATH):
        self.storage = storage
        self.mempool = mempool
        self.p2p = p2p
        self.wallet = wallet
        self.host = host
        self.port = port
        self.rpc_cookie = load_or_create_rpc_cookie(cookie_path)
        self.cookie_path = cookie_path
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
        print(f"[RPC] Dashboard: http://127.0.0.1:{self.port}/  (bound to {self.host})")
        print(f"[RPC] Cookie file: {self.cookie_path}")

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
                    ok, msg = self.storage.accept_block(candidate_block)
                    if ok:
                        self.mempool.remove_mined_transactions(block_txs)
                        self.p2p.broadcast_new_block(candidate_block)
                        self.gpu_miner.blocks_found += 1
                        print(f"[Miner] Mined Block #{candidate_block.header.height}! Hash: {block_hash}")
                    else:
                        print(f"[Miner] Block rejected: {msg}")

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

            def _check_cookie(self) -> bool:
                got = self.headers.get(RPC_COOKIE_HEADER, "") or ""
                expected = outer.rpc_cookie
                if len(got) != len(expected):
                    return False
                return hmac.compare_digest(got, expected)

            def do_GET(self):
                parsed = urlparse(self.path)
                path = parsed.path

                if path == "/" or path == "/index.html":
                    html = HTML_DASHBOARD.replace("__URC_RPC_COOKIE__", outer.rpc_cookie)
                    self._send_html(html)
                    return

                if path.startswith("/api/") and not self._check_cookie():
                    self._send_json({"error": "Unauthorized"}, status=401)
                    return

                if path == "/api/info":
                    height = outer.storage.get_best_height()
                    best_b = outer.storage.get_best_block()
                    next_height = height + 1
                    reward = calculate_block_reward(next_height)
                    supply = circulating_supply(height)
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

                elif path == "/api/exchange/ticker":
                    ticker = outer.storage.exchange.get_ticker()
                    self._send_json(ticker)

                elif path == "/api/exchange/orderbook":
                    limit = int(parse_qs(parsed.query).get("limit", [20])[0])
                    book = outer.storage.exchange.get_order_book(limit=limit)
                    self._send_json(book)

                elif path == "/api/exchange/trades":
                    limit = int(parse_qs(parsed.query).get("limit", [30])[0])
                    trades = outer.storage.exchange.get_recent_trades(limit=limit)
                    self._send_json(trades)

                elif path == "/api/exchange/user_orders":
                    address = parse_qs(parsed.query).get("address", [outer.wallet.address])[0]
                    orders = outer.storage.exchange.get_user_orders(address=address)
                    self._send_json(orders)

                else:
                    self._send_json({"error": "Not Found"}, status=404)

            def do_POST(self):
                parsed = urlparse(self.path)
                path = parsed.path
                if not self._check_cookie():
                    self._send_json({"error": "Unauthorized"}, status=401)
                    return
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
                        ok, msg = outer.storage.accept_block(block)
                        if ok:
                            outer.mempool.remove_mined_transactions(block.transactions)
                            outer.mempool.revalidate()
                            outer.p2p.broadcast_new_block(block)
                            self._send_json({"success": True, "hash": block.hash, "status": msg})
                        else:
                            self._send_json({"success": False, "error": msg}, status=400)
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=400)

                elif path == "/api/exchange/order":
                    try:
                        side = data.get("side", "BUY")
                        price = float(data["price"])
                        amount = float(data["amount"])
                        creator = data.get("creator_address", outer.wallet.address)
                        ok, msg, res = outer.storage.exchange.place_order(side, price, amount, creator)
                        if ok:
                            self._send_json({"success": True, "message": msg, "order": res})
                        else:
                            self._send_json({"success": False, "error": msg}, status=400)
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=400)

                elif path == "/api/exchange/cancel":
                    try:
                        order_id = data["order_id"]
                        requester = data.get("requester_address", outer.wallet.address)
                        ok, msg = outer.storage.exchange.cancel_order(order_id, requester)
                        if ok:
                            self._send_json({"success": True, "message": msg})
                        else:
                            self._send_json({"success": False, "error": msg}, status=400)
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=400)

                elif path == "/api/exchange/swap":
                    try:
                        from_asset = data.get("from_asset", "URC")
                        to_asset = data.get("to_asset", "USDT")
                        amount_in = float(data["amount_in"])
                        creator = data.get("creator_address", outer.wallet.address)
                        ok, msg, res = outer.storage.exchange.instant_swap(from_asset, to_asset, amount_in, creator)
                        if ok:
                            self._send_json({"success": True, "message": msg, "swap": res})
                        else:
                            self._send_json({"success": False, "error": msg}, status=400)
                    except Exception as e:
                        self._send_json({"success": False, "error": str(e)}, status=400)

                elif path == "/api/rpc" or path == "/jsonrpc":
                    try:
                        method = data.get("method")
                        params = data.get("params", [])
                        req_id = data.get("id", 1)

                        if method == "getbalance":
                            addr = params[0] if params else outer.wallet.address
                            bal = outer.storage.get_balance(addr)
                            self._send_json({"result": bal / COIN, "error": None, "id": req_id})
                        elif method == "getblockcount":
                            self._send_json({"result": outer.storage.get_best_height(), "error": None, "id": req_id})
                        elif method == "getbestblockhash":
                            b = outer.storage.get_best_block()
                            self._send_json({"result": b.hash if b else "", "error": None, "id": req_id})
                        elif method == "getnewaddress":
                            self._send_json({"result": outer.wallet.address, "error": None, "id": req_id})
                        elif method == "validateaddress":
                            from urcoin.crypto import is_valid_address
                            addr = params[0] if params else ""
                            self._send_json({"result": {"isvalid": is_valid_address(addr), "address": addr}, "error": None, "id": req_id})
                        elif method == "getorderbook":
                            book = outer.storage.exchange.get_order_book()
                            self._send_json({"result": book, "error": None, "id": req_id})
                        elif method == "getticker":
                            ticker = outer.storage.exchange.get_ticker()
                            self._send_json({"result": ticker, "error": None, "id": req_id})
                        else:
                            self._send_json({"result": None, "error": f"Method {method} not implemented", "id": req_id}, status=404)
                    except Exception as e:
                        self._send_json({"result": None, "error": str(e), "id": data.get("id", 1)}, status=500)

                else:
                    self._send_json({"error": "Not Found"}, status=404)

        return RPCRequestHandler
