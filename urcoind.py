"""
Ur Coin (URC) - Full Node Daemon (urcoind)
Launches:
- Blockchain Storage (SQLite)
- UTXO Mempool
- P2P Network Node (Port 9333)
- JSON-RPC & Web Explorer / Mining Dashboard (Port 9334)
"""

import sys
import time
import argparse
import signal

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from urcoin.storage import BlockchainStorage
from urcoin.mempool import Mempool
from urcoin.network import P2PNetwork
from urcoin.wallet import Wallet
from urcoin.rpc import UrCoinRPCServer
from urcoin.core import Block

def main():
    parser = argparse.ArgumentParser(description="Ur Coin (URC) Full Node Daemon")
    parser.add_argument("--p2p-port", type=int, default=9333, help="P2P network port (default: 9333)")
    parser.add_argument("--rpc-port", type=int, default=9334, help="RPC & Web Dashboard port (default: 9334)")
    parser.add_argument("--db-path", type=str, default="urcoin_data.db", help="Blockchain database file")
    parser.add_argument("--wallet-path", type=str, default="urcoin_wallet.json", help="Node wallet file")
    parser.add_argument("--peer", type=str, action="append", help="Connect to peer (host:port)")
    parser.add_argument("--mine", action="store_true", help="Automatically start GPU mining upon launch")

    args = parser.parse_args()

    print("==================================================================")
    print("      UR COIN (URC) - DECENTRALIZED GPU BLOCKCHAIN NODE")
    print("      Proof-of-Work Algorithm: UrHash-v1 (Memory-Hard PoW)")
    print("==================================================================")

    # 1. Initialize Storage
    storage = BlockchainStorage(args.db_path)
    best_height = storage.get_best_height()
    best_block = storage.get_best_block()
    print(f"[Storage] Loaded chain from '{args.db_path}'. Current Height: #{best_height}")
    print(f"[Storage] Best Block Hash: {best_block.hash if best_block else 'None'}")

    # 2. Initialize Mempool
    mempool = Mempool(storage)

    # 3. Initialize Wallet
    wallet = Wallet.create_or_load(args.wallet_path)
    print(f"[Wallet] Node Wallet Address: {wallet.address}")

    # 4. Initialize P2P Network
    def on_new_block(block: Block):
        if block.header.height > storage.get_best_height():
            if block.verify_pow():
                storage.add_block(block)
                mempool.remove_mined_transactions(block.transactions)
                print(f"[P2P] Synced Block #{block.header.height} from network! Hash: {block.hash[:16]}...")

    def get_chain_info():
        return {
            "height": storage.get_best_height(),
            "best_hash": storage.get_best_block().hash if storage.get_best_block() else ""
        }

    def get_blocks_range(from_h, to_h):
        blocks = []
        for h in range(from_h, to_h + 1):
            b = storage.get_block_by_height(h)
            if b:
                blocks.append(b)
        return blocks

    p2p = P2PNetwork(
        host="0.0.0.0",
        port=args.p2p_port,
        on_new_block=on_new_block,
        on_new_tx=lambda tx: mempool.add_transaction(tx),
        get_chain_info=get_chain_info,
        get_blocks_range=get_blocks_range
    )
    p2p.start()

    # Connect to initial peers if provided
    if args.peer:
        for p in args.peer:
            if ":" in p:
                phost, pport = p.split(":", 1)
                p2p.connect_to_peer(phost, int(pport))

    # 5. Initialize RPC & Web Dashboard
    rpc_server = UrCoinRPCServer(
        storage=storage,
        mempool=mempool,
        p2p=p2p,
        wallet=wallet,
        host="0.0.0.0",
        port=args.rpc_port
    )
    rpc_server.start()

    if args.mine:
        rpc_server.start_mining()

    print("\n------------------------------------------------------------------")
    print(f"  Web Dashboard & Explorer: http://localhost:{args.rpc_port}/")
    print(f"  P2P Gossip Port:         {args.p2p_port}")
    print("------------------------------------------------------------------\n")
    print("[Node] Ur Coin daemon is running. Press Ctrl+C to terminate.")

    def shutdown(signum=None, frame=None):
        print("\n[Node] Shutting down Ur Coin daemon cleanly...")
        rpc_server.stop()
        p2p.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    while True:
        time.sleep(1)

if __name__ == "__main__":
    main()
