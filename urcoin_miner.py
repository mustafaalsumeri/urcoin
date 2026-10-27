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

from urcoin.miner_gpu import GPUMiner, CPUMiner, get_opencl_devices
from urcoin.core import Block, BlockHeader, Transaction
from urcoin.crypto import DEFAULT_DAG_ITEMS, DEFAULT_ROUNDS
from urcoin.auth import RPC_COOKIE_HEADER, read_rpc_cookie

def rpc_call(url: str, endpoint: str, data: dict = None) -> dict:
    req_url = f"{url.rstrip('/')}{endpoint}"
    headers = {}
    cookie = read_rpc_cookie()
    if cookie:
        headers[RPC_COOKIE_HEADER] = cookie
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(req_url, data=payload, headers=headers)
    else:
        req = urllib.request.Request(req_url, headers=headers)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8"))

def main():
    parser = argparse.ArgumentParser(description="Ur Coin (URC) Adaptive Miner (Weak/Strong GPUs & CPU)")
    parser.add_argument("--node-url", type=str, default="http://127.0.0.1:9334", help="Ur Coin node RPC URL")
    parser.add_argument("--address", type=str, required=True, help="Your URC mining payout address (urc1...)")
    parser.add_argument("--device", type=int, default=0, help="OpenCL GPU device index (default: 0)")
    parser.add_argument("--profile", type=str, choices=["eco", "medium", "high"], default="eco",
                        help="Mining intensity profile (eco for weak/laptop GPUs, medium for mid-tier, high for top GPUs)")
    parser.add_argument("--light", action="store_true", help="Force Zero-VRAM Light GPU Mode (computes on-the-fly, 0 MB VRAM DAG)")
    parser.add_argument("--cpu", action="store_true", help="Mine using CPU multi-threading instead of GPU")
    parser.add_argument("--batch-threads", type=int, default=0, help="Custom GPU threads per batch")
    parser.add_argument("--nonces-per-thread", type=int, default=0, help="Custom nonces per thread")

    args = parser.parse_args()

    # Determine batch parameters based on profile
    if args.profile == "eco":
        batch_threads = 4096 if args.batch_threads <= 0 else args.batch_threads
        nonces_per_th = 4 if args.nonces_per_thread <= 0 else args.nonces_per_thread
    elif args.profile == "medium":
        batch_threads = 16384 if args.batch_threads <= 0 else args.batch_threads
        nonces_per_th = 8 if args.nonces_per_thread <= 0 else args.nonces_per_thread
    else:
        batch_threads = 65536 if args.batch_threads <= 0 else args.batch_threads
        nonces_per_th = 16 if args.nonces_per_thread <= 0 else args.nonces_per_thread

    print("==================================================================")
    print("      UR COIN (URC) - ADAPTIVE HIGH/WEAK GPU & CPU MINER")
    print(f"      Profile: {args.profile.upper()} | Threads: {batch_threads} | NPT: {nonces_per_th}")
    print("==================================================================")

    devices = get_opencl_devices()
    miner = None
    if not args.cpu and devices:
        print(f"Discovered GPU Devices: {devices}")
        try:
            miner = GPUMiner(device_index=args.device, dag_items=DEFAULT_DAG_ITEMS, light_mode=args.light if args.light else None)
            print(f"[Miner] Active GPU: {miner.device} (Light Mode: {miner.light_mode})")
        except Exception as e:
            print(f"[Miner] GPU initialization error: {e}. Falling back to CPU Miner...")

    if miner is None:
        print("[Miner] Initializing Multi-threaded CPU Miner Worker...")
        miner = CPUMiner()

    print(f"[Miner] Active Worker: {miner.device}")
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

            # Execute Mining Batch
            if isinstance(miner, CPUMiner):
                step_nonces = batch_threads * 2
                results = miner.search_batch(mining_hash, target_int, epoch, start_nonce=nonce_seq, count=step_nonces)
            else:
                step_nonces = batch_threads * nonces_per_th
                results = miner.search_batch(
                    mining_hash, target_int, epoch,
                    start_nonce=nonce_seq,
                    global_work_size=batch_threads,
                    nonces_per_thread=nonces_per_th
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
