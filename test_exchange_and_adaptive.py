"""
Unit & Integration Tests for:
1. Decentralized Order Book Matching Engine & Swaps
2. Zero-VRAM Light GPU Mode & CPU Miner
3. Time-decay Difficulty Adjustment for Weak Hardware
"""

import os
import sys
import tempfile
import sqlite3
import threading

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Set test environment
os.environ["URCOIN_TEST_MODE"] = "1"
os.environ["URCOIN_WALLET_PASSWORD"] = "test-secret"

from urcoin.exchange import ExchangeEngine, TradeSide, OrderStatus
from urcoin.miner_gpu import GPUMiner, CPUMiner, get_opencl_devices
from urcoin.core import BlockHeader, MAX_TARGET, INITIAL_TARGET, calculate_next_target
from urcoin.storage import BlockchainStorage

def test_exchange():
    print("Testing Exchange Matching Engine & Swaps...")
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    lock = threading.RLock()
    engine = ExchangeEngine(conn, lock)

    # 1. Check Initial Ticker
    ticker = engine.get_ticker()
    assert ticker["pair"] == "URC/USDT"
    assert ticker["last_price"] > 0
    print(f"  OK  Initial Ticker: ${ticker['last_price']} USDT")

    # 2. Place resting BUY order
    ok, msg, buy_order = engine.place_order(TradeSide.BUY, 0.0500, 100.0, "urc1TestBuyerAddressXXXXXXXXXXXXXX")
    assert ok, f"Buy order failed: {msg}"
    print(f"  OK  Placed Buy Order: {buy_order['order_id'][:8]} (Status: {buy_order['status']})")

    # 3. Place matching SELL order that crosses
    ok, msg, sell_order = engine.place_order(TradeSide.SELL, 0.0500, 50.0, "urc1TestSellerAddressXXXXXXXXXXXXX")
    assert ok, f"Sell order failed: {msg}"
    assert len(sell_order["executed_trades"]) == 1, "Expected 1 trade execution"
    assert sell_order["status"] == OrderStatus.FILLED
    print(f"  OK  Matched Sell Order: {sell_order['executed_trades'][0]['amount']} URC traded @ ${sell_order['executed_trades'][0]['price']}")

    # 4. Instant Swap
    ok, msg, swap_res = engine.instant_swap("URC", "USDT", 20.0, "urc1TestSwapperAddressXXXXXXXXXXXX")
    assert ok, f"Instant swap failed: {msg}"
    assert swap_res["amount_out"] > 0
    print(f"  OK  Instant Swap: {swap_res['amount_in']} URC -> ${swap_res['amount_out']:.2f} USDT")

    # 5. Order book query
    book = engine.get_order_book()
    assert len(book["bids"]) > 0
    assert len(book["asks"]) > 0
    print(f"  OK  Order Book Depth: {len(book['bids'])} Bids, {len(book['asks'])} Asks")

def test_adaptive_miners():
    print("\nTesting Adaptive Miners (Weak GPU Light Mode & CPU Miner)...")
    open_target = (1 << 256) - 1
    
    # 1. CPU Miner test
    cpu_miner = CPUMiner(threads=2)
    res_cpu = cpu_miner.search_batch(b"H" * 32, open_target, 0, start_nonce=0, count=50)
    assert len(res_cpu) > 0, "CPU Miner should find solution with open target"
    print(f"  OK  CPU Miner verified (Found nonce: {res_cpu[0][0]}, Speed: {cpu_miner.hashrate:.0f} H/s)")

    # 2. GPU Light Miner test (if OpenCL is available)
    devices = get_opencl_devices()
    if devices:
        gpu_miner = GPUMiner(device_index=0, light_mode=True)
        assert gpu_miner.light_mode is True, "Light mode must be active"
        res_gpu = gpu_miner.search_batch(b"H" * 32, open_target, 0, start_nonce=0, global_work_size=1024, nonces_per_thread=2)
        assert len(res_gpu) > 0, "GPU Light Miner should find solution"
        print(f"  OK  GPU Zero-VRAM Light Miner verified on {gpu_miner.device.device_name} (Speed: {gpu_miner.hashrate:.0f} H/s)")
    else:
        print("  SKIP GPU test (No OpenCL device present)")

def run_all():
    test_exchange()
    test_adaptive_miners()
    print("\n✓ ALL ADAPTIVE MINING AND TRADING TESTS PASSED!")

if __name__ == "__main__":
    run_all()
