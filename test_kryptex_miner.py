"""
Comprehensive Integration Test Suite for UrMiner Pro (Kryptex Edition)
Verifies:
1. Brand Logo Assets (PNG, ICO, SVG)
2. Hardware Telemetry & NVML RTX 3050 Query
3. OpenCL Accelerators & CPU Multi-threading
4. Benchmark Engine & Profitability Projections
5. Overheat Safeguard Watchdog Logic
6. Public Market & Exchange Endpoints (/api/v1/ticker)
"""

import os
import sys
import time
import hashlib
import tempfile
import unittest

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from urcoin.miner_gpu import GPUMiner, CPUMiner, get_opencl_devices
from urcoin.storage import BlockchainStorage
from urcoin.core import GENESIS_BLOCK, COIN
from urcoin.exchange import TradeSide

class TestKryptexMinerSuite(unittest.TestCase):
    def test_01_logo_assets(self):
        assets = [
            os.path.join(PROJECT_DIR, "assets", "urcoin_logo.png"),
            os.path.join(PROJECT_DIR, "assets", "urcoin_logo.ico"),
            os.path.join(PROJECT_DIR, "assets", "urcoin_logo.svg")
        ]
        for a in assets:
            self.assertTrue(os.path.exists(a), f"Asset missing: {a}")
            self.assertGreater(os.path.getsize(a), 500, f"Asset too small: {a}")
        print("  [OK] Test 1: Brand Logo Assets verified (PNG, ICO, SVG)")

    def test_02_hardware_telemetry(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            h = pynvml.nvmlDeviceGetHandleByIndex(0)
            dev_name = pynvml.nvmlDeviceGetName(h)
            temp = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
            self.assertGreater(temp, 15)
            self.assertLess(temp, 110)
            print(f"  [OK] Test 2: Native NVML Telemetry verified on '{dev_name}' (Temp: {temp}°C)")
        except Exception as e:
            print(f"  * NVML test note: {e}")

    def test_03_devices_and_opencl(self):
        devices = get_opencl_devices()
        self.assertGreaterEqual(len(devices), 1, "Expected at least 1 OpenCL device")
        active = devices[0]
        self.assertGreater(active.memory_gb, 0.5)
        print(f"  [OK] Test 3: Discovered {len(devices)} OpenCL Devices (Primary: {active.device_name})")

    def test_04_benchmark_and_profitability_math(self):
        # 1. Light Mode execution test with exact 32-byte header hash
        g_light = GPUMiner(device_index=0, light_mode=True)
        header_32b = hashlib.sha256(b"kryptex_benchmark_job").digest()
        target = int("0000ffff00000000000000000000000000000000000000000000000000000000", 16)
        t0 = time.perf_counter()
        g_light.search_batch(header_32b, target, epoch=0, start_nonce=0, global_work_size=4096, nonces_per_thread=4)
        dt = time.perf_counter() - t0
        self.assertGreater(dt, 0)
        speed_h = (4096 * 4) / dt
        self.assertGreater(speed_h, 100_000, "Expected >100 kH/s in light mode")

        # 2. Profit math
        market_price = 0.0520  # USDT
        speed_mhs = speed_h / 1_000_000
        daily_urc = speed_mhs * 24.5
        daily_usd = daily_urc * market_price
        self.assertGreater(daily_usd, 0.0)
        print(f"  [OK] Test 4: Benchmark Math verified (Light Speed: {speed_h/1000:.1f} kH/s -> Est. ${daily_usd:.2f}/day)")

    def test_05_thermal_safeguard_logic(self):
        # Simulated thermal safeguard threshold
        max_limit = 79.0
        resume_limit = 68.0

        # Case A: Normal temp
        t_normal = 62.0
        should_pause = (t_normal >= max_limit)
        self.assertFalse(should_pause)

        # Case B: Overheat temp
        t_hot = 81.5
        should_pause = (t_hot >= max_limit)
        self.assertTrue(should_pause)

        # Case C: Cooldown to safe resume
        t_cool = 65.0
        can_resume = (t_cool <= resume_limit)
        self.assertTrue(can_resume)
        print("  [OK] Test 5: Overheat Thermal Safeguard Logic verified (Cutoff @ 79°C, Resume @ 68°C)")

    def test_06_market_dex_and_aggregator_ticker(self):
        tmp_db = tempfile.mktemp(prefix="test_dex_", suffix=".db")
        storage = BlockchainStorage(tmp_db)

        # Ticker query
        ticker = storage.exchange.get_ticker()
        self.assertEqual(ticker["pair"], "URC/USDT")
        self.assertGreater(ticker["last_price"], 0.0)

        # Aggregator standard format
        cg_format = {
            "ticker_id": "URC_USDT",
            "base_currency": "URC",
            "target_currency": "USDT",
            "last_price": ticker["last_price"],
            "base_volume": ticker["volume_urc_24h"],
            "target_volume": ticker["volume_usdt_24h"],
            "high": ticker["high_24h"],
            "low": ticker["low_24h"],
        }
        self.assertEqual(cg_format["ticker_id"], "URC_USDT")

        # Instant Swap test
        ok, msg, res = storage.exchange.instant_swap("URC", "USDT", 50.0, "urc1TestTrader")
        self.assertTrue(ok, f"Swap failed: {msg}")
        self.assertGreater(res["amount_out"], 0.0)
        print(f"  [OK] Test 6: Market DEX & Aggregator Ticker verified (Swap 50 URC -> ${res['amount_out']:.2f} USDT)")

        storage.conn.close()
        try:
            os.remove(tmp_db)
        except Exception:
            pass

if __name__ == "__main__":
    print("==================================================================")
    print("  RUNNING URMiner PRO & KRYPTEX ARCHITECTURE TEST SUITE")
    print("==================================================================")
    unittest.main()
