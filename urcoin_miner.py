"""
Ur Coin (URC) - Dedicated Standalone GPU Miner
Connects to an active Ur Coin node, fetches jobs, and executes the
UrHash Memory-Hard PoW kernel on NVIDIA / AMD GPUs.
"""

import sys
import time
import json
import argparse
import urllib.request

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from urcoin.miner_gpu import GPUMiner, get_opencl_devices
from urcoin.core import Block, BlockHeader, Transaction, DEFAULT_DAG_ITEMS, DEFAULT_ROUNDS

def rpc_call(url: str, endpoint: str, data: dict = None) -> dict:
    req_url = f"{url.rstrip('/')}{endpoint}"
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(req_url, data=payload, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(req_url)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    parser = argparse.ArgumentParser(description="Ur Coin (URC) Standalone GPU Miner")
    parser.add_argument("--node-url", type=str, default="http://127.0.0.1:9334", help="Ur Coin node RPC URL")
    parser.add_argument("--address", type=str, required=True, help="Your URC mining payout address (urc1...)")
    parser.add_argument("--device", type=int, default=0, help="OpenCL GPU device index (default: 0)")
    parser.add_argument("--batch-threads", type=int, default=65536, help="GPU threads per batch (default: 65536)")
    parser.add_argument("--nonces-per-thread", type=int, default=32, help="Nonces per thread (default: 32)")

    args = parser.parse_args()

    print("==================================================================")
    print("         UR COIN (URC) - STANDALONE GPU OPENCL MINER")
    print("==================================================================")
    devices = get_opencl_devices()
    print(f"Discovered GPU Devices: {devices}")
    if not devices:
        print("[Error] No OpenCL GPU devices detected!")
        sys.exit(1)

    miner = GPUMiner(device_index=args.device, dag_items=DEFAULT_DAG_ITEMS)
    print(f"[Miner] Active GPU: {miner.device}")
    print(f"[Miner] Mining Reward Payout to: {args.address}")
    print(f"[Miner] Connecting to Node at: {args.node_url}")

    nonce_seq = 0
    blocks_mined = 0
    t0_stats = time.time()
    hashes_in_window = 0

    while True:
        try:
            info = rpc_call(args.node_url, "/api/info")
            best_height = info["height"]
            best_hash = info["best_hash"]
            target_int = int(info["target"], 16)
            reward = info["current_reward"]

            height = best_height + 1
            epoch = height // 10_000

            # Prepare block template
            coinbase_tx = Transaction.create_coinbase(args.address, reward, height)
            header = BlockHeader(
                version=1,
                prev_hash=best_hash,
                merkle_root=coinbase_tx.txid,
                timestamp=int(time.time()),
                target=target_int,
                nonce=0,
                height=height,
                epoch=epoch
            )
            candidate = Block(header, [coinbase_tx])
            mining_hash = candidate.header.get_mining_hash()

            # Execute GPU Batch
            step_nonces = args.batch_threads * args.nonces_per_thread
            results = miner.search_batch(
                mining_hash, target_int, epoch,
                start_nonce=nonce_seq,
                global_work_size=args.batch_threads,
                nonces_per_thread=args.nonces_per_thread
            )
            nonce_seq += step_nonces
            hashes_in_window += step_nonces

            now = time.time()
            if now - t0_stats >= 3.0:
                dt = now - t0_stats
                speed = hashes_in_window / dt
                speed_str = f"{speed / 1_000_000:.2f} MH/s" if speed >= 1_000_000 else f"{speed / 1000:.2f} kH/s"
                print(f"[Miner] Height: #{height} | Speed: {speed_str} | Blocks Mined: {blocks_mined} | Target: {info['target'][:14]}...")
                t0_stats = now
                hashes_in_window = 0

            # Winning nonce found!
            if results:
                winning_nonce, block_hash = results[0]
                candidate.header.nonce = winning_nonce
                candidate.hash = block_hash

                submit_res = rpc_call(args.node_url, "/api/submit_block", candidate.to_dict())
                if submit_res.get("success"):
                    blocks_mined += 1
                    print("\n******************************************************************")
                    print(f"🎉 SUCCESS: Block #{height} Accepted by Network!")
                    print(f"   Hash:  {block_hash}")
                    print(f"   Nonce: {winning_nonce}")
                    print(f"   Earned: {reward / 100_000_000:.2f} URC")
                    print("******************************************************************\n")
                    nonce_seq = 0

        except urllib.error.URLError:
            print(f"[Miner] Waiting for node at {args.node_url} to become reachable...")
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n[Miner] Stopping GPU miner...")
            break
        except Exception as e:
            print(f"[Miner] Error: {e}")
            time.sleep(2)

if __name__ == "__main__":
    main()
