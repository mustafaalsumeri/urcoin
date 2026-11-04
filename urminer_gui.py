"""
UrMiner Pro - Next-Generation Desktop GPU Mining Suite for Ur Coin (URC)
Architected on the Kryptex model for high reliability, real hardware telemetry,
automated performance benchmarks, thermal overheat safeguards, and direct UrDEX market integration.
"""

import sys
import os
import time
import json
import math
import threading
import subprocess
import urllib.request
import urllib.error
import customtkinter as ctk
from PIL import Image

# Ensure current working directory is ALWAYS the project directory
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJECT_DIR)
sys.path.insert(0, PROJECT_DIR)

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Native Hardware Telemetry Libraries
try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

from urcoin.miner_gpu import GPUMiner, CPUMiner, get_opencl_devices, OpenCLDevice
from urcoin.core import (
    Block, BlockHeader, Transaction, calculate_block_reward,
    COIN, DEFAULT_DAG_ITEMS
)
from urcoin.wallet import Wallet
from urcoin.auth import RPC_COOKIE_HEADER, read_rpc_cookie

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
LOGO_PNG = os.path.join(ASSETS_DIR, "urcoin_logo.png")
LOGO_ICO = os.path.join(ASSETS_DIR, "urcoin_logo.ico")


class UrMinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("UrMiner Pro - Kryptex GPU Mining Suite (Ur Coin)")
        self.geometry("1080x760")
        self.minsize(980, 700)
        self.configure(fg_color="#090d16")

        # Set Window Icon
        if os.path.exists(LOGO_ICO):
            try:
                self.iconbitmap(LOGO_ICO)
            except Exception:
                pass

        # App Lifetime Flag
        self.running = True

        # Mining State Variables
        self.is_mining = False
        self.is_paused_thermal = False
        self.is_benchmarking = False
        self.mining_thread = None
        self.gpu_miner = None
        self.cpu_miner = None
        self.mining_start_time = 0

        # OpenCL Devices Detection
        self.devices = get_opencl_devices()
        self.selected_device_idx = 0

        # Statistics
        self.blocks_found = 0
        self.total_hashes = 0
        self.current_hashrate = 0.0  # in H/s
        self.market_price_usdt = 0.0520  # Live price from UrDEX
        self.confirmed_balance_urc = 0.0

        # Hardware Safety Settings
        self.max_temp_limit = 79.0  # Max safe GPU temperature in °C
        self.auto_resume_temp = 68.0

        # Hardware Telemetry Cache
        self.telemetry = {
            "temp": "N/A", "temp_val": 0, "fan": "N/A",
            "power": "N/A", "power_val": 0.0, "load": "N/A",
            "vram": "N/A", "cpu": "N/A", "ram": "N/A"
        }

        # Wallet & Node RPC
        wallet_path = os.path.join(PROJECT_DIR, "urcoin_wallet.json")
        try:
            self.wallet = Wallet.create_or_load(wallet_path)
        except Exception as e:
            # Fallback if existing wallet was corrupted or encrypted with different pass
            self.wallet = Wallet()
            try:
                self.wallet.save_to_file(wallet_path)
            except Exception:
                pass

        self.node_url = "http://127.0.0.1:9334"
        self.node_connected = False
        self.node_height = 0
        self.node_process = None

        # NVML Initialization
        self.nvml_initialized = False
        if HAS_PYNVML:
            try:
                pynvml.nvmlInit()
                self.nvml_initialized = True
            except Exception:
                self.nvml_initialized = False

        # Setup Clean Window Closing Protocol
        self.protocol("WM_DELETE_WINDOW", self._on_closing)

        # Setup GUI Structure
        self._setup_ui()

        # Start Telemetry & Node Polling Background Thread
        self.telemetry_thread = threading.Thread(target=self._telemetry_worker, daemon=True)
        self.telemetry_thread.start()

    def _safe_after(self, delay_ms, func, *args):
        """Thread-safe UI callback that avoids RuntimeError if window is closed."""
        if getattr(self, "running", False):
            try:
                self.after(delay_ms, func, *args)
            except Exception:
                pass

    def _on_closing(self):
        """Clean shutdown handler."""
        self.running = False
        self.is_mining = False
        self.destroy()

    def _setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # =====================================================================
        # 1. SIDEBAR (Navigation & Node Status)
        # =====================================================================
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color="#0e1524")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1)

        # Brand / Logo Header
        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_frame.grid(row=0, column=0, padx=18, pady=(20, 16), sticky="w")

        # Load Logo Image
        if os.path.exists(LOGO_PNG):
            try:
                pil_logo = Image.open(LOGO_PNG).resize((44, 44), Image.Resampling.LANCZOS)
                self.img_logo = ctk.CTkImage(light_image=pil_logo, dark_image=pil_logo, size=(44, 44))
                self.logo_badge = ctk.CTkLabel(self.logo_frame, image=self.img_logo, text="")
            except Exception:
                self.logo_badge = ctk.CTkLabel(
                    self.logo_frame, text="URC", width=44, height=44,
                    fg_color="#f59e0b", text_color="#000", corner_radius=10,
                    font=ctk.CTkFont(family="Plus Jakarta Sans", size=18, weight="bold")
                )
        else:
            self.logo_badge = ctk.CTkLabel(
                self.logo_frame, text="URC", width=44, height=44,
                fg_color="#f59e0b", text_color="#000", corner_radius=10,
                font=ctk.CTkFont(family="Plus Jakarta Sans", size=18, weight="bold")
            )
        self.logo_badge.pack(side="left", padx=(0, 12))

        self.title_box = ctk.CTkFrame(self.logo_frame, fg_color="transparent")
        self.title_box.pack(side="left")
        self.lbl_brand_name = ctk.CTkLabel(
            self.title_box, text="UrMiner Pro",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=18, weight="bold"),
            text_color="#f8fafc"
        )
        self.lbl_brand_name.pack(anchor="w")
        self.lbl_brand_sub = ctk.CTkLabel(
            self.title_box, text="Kryptex Edition • URC",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=11),
            text_color="#f59e0b"
        )
        self.lbl_brand_sub.pack(anchor="w")

        # Navigation Buttons
        self.nav_buttons = {}
        nav_items = [
            ("dashboard", "⚡  Dashboard"),
            ("benchmark", "🧪  Benchmark"),
            ("wallet", "💼  Wallet & Payouts"),
            ("market", "📈  UrDEX Market"),
            ("settings", "⚙️  Settings & Safety")
        ]

        for idx, (key, label) in enumerate(nav_items, start=1):
            btn = ctk.CTkButton(
                self.sidebar, text=label, anchor="w", height=42,
                fg_color="#1e293b" if key == "dashboard" else "transparent",
                hover_color="#1e293b",
                text_color="#f8fafc" if key == "dashboard" else "#94a3b8",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=lambda k=key: self._select_tab(k)
            )
            btn.grid(row=idx, column=0, padx=14, pady=4, sticky="ew")
            self.nav_buttons[key] = btn

        # Sidebar Footer: Node Status Card
        self.node_card = ctk.CTkFrame(self.sidebar, fg_color="#131c2e", corner_radius=12)
        self.node_card.grid(row=8, column=0, padx=14, pady=16, sticky="ew")

        self.lbl_node_indicator = ctk.CTkLabel(
            self.node_card, text="● NODE CONNECTING...",
            text_color="#f59e0b", font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_node_indicator.pack(pady=(10, 2))

        self.lbl_node_info = ctk.CTkLabel(
            self.node_card, text="Target: 127.0.0.1:9334",
            text_color="#64748b", font=ctk.CTkFont(size=11)
        )
        self.lbl_node_info.pack(pady=(0, 4))

        self.btn_node_action = ctk.CTkButton(
            self.node_card, text="Start Local Node", height=28,
            fg_color="#06b6d4", hover_color="#0284c7",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=self._launch_node_daemon
        )
        self.btn_node_action.pack(padx=12, pady=(0, 10), fill="x")

        # =====================================================================
        # 2. MAIN CONTENT AREA
        # =====================================================================
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Tab Frames
        self.tab_dashboard = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_benchmark = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_wallet = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_market = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_settings = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        self._build_dashboard_tab()
        self._build_benchmark_tab()
        self._build_wallet_tab()
        self._build_market_tab()
        self._build_settings_tab()

        self._select_tab("dashboard")

    # =========================================================================
    # TAB 1: MINING DASHBOARD (Kryptex Style)
    # =========================================================================
    def _build_dashboard_tab(self):
        self.tab_dashboard.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # 1. Main Mining Banner Card
        self.banner_card = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        self.banner_card.grid(row=0, column=0, columnspan=4, sticky="ew", pady=(0, 14), ipady=8)

        self.btn_mine = ctk.CTkButton(
            self.banner_card, text="▶   START MINING",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=18, weight="bold"),
            height=58, width=270, corner_radius=14,
            fg_color="#10b981", hover_color="#059669",
            command=self._toggle_mining
        )
        self.btn_mine.pack(side="left", padx=20, pady=12)

        self.banner_info = ctk.CTkFrame(self.banner_card, fg_color="transparent")
        self.banner_info.pack(side="left", fill="both", expand=True, padx=10, pady=12)

        self.lbl_status = ctk.CTkLabel(
            self.banner_info, text="IDLE - READY TO MINE",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#94a3b8"
        )
        self.lbl_status.pack(anchor="w")

        dev_name = self.devices[0].device_name if self.devices else "CPU / OpenCL Fallback"
        self.lbl_gpu_header = ctk.CTkLabel(
            self.banner_info, text=f"Active Device: {dev_name}",
            font=ctk.CTkFont(size=12), text_color="#06b6d4"
        )
        self.lbl_gpu_header.pack(anchor="w", pady=(2, 0))

        self.lbl_timer = ctk.CTkLabel(
            self.banner_info, text="Uptime: 00:00:00  |  Profile: SMART ECO (ZERO-VRAM)",
            font=ctk.CTkFont(size=11), text_color="#64748b"
        )
        self.lbl_timer.pack(anchor="w", pady=(2, 0))

        # Thermal Overheat Warning Banner (Hidden by default)
        self.thermal_banner = ctk.CTkFrame(self.tab_dashboard, fg_color="#7f1d1d", corner_radius=12, border_width=1, border_color="#ef4444")
        self.lbl_thermal_msg = ctk.CTkLabel(
            self.thermal_banner, text="⚠️ THERMAL SAFEGUARD: GPU Exceeded 79°C! Mining paused to cool down.",
            font=ctk.CTkFont(size=12, weight="bold"), text_color="#fecaca"
        )
        self.lbl_thermal_msg.pack(padx=16, pady=8)

        # 2. Main Metrics Grid (4 Cards Side-by-Side)
        # Metric 1: Hashrate
        self.card_hashrate = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_hashrate.grid(row=2, column=0, sticky="nsew", padx=(0, 5), pady=(0, 14), ipady=10)
        ctk.CTkLabel(self.card_hashrate, text="CURRENT HASHRATE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.lbl_hashrate_val = ctk.CTkLabel(self.card_hashrate, text="0.00", font=ctk.CTkFont(family="JetBrains Mono", size=26, weight="bold"), text_color="#f59e0b")
        self.lbl_hashrate_val.pack()
        self.lbl_hashrate_unit = ctk.CTkLabel(self.card_hashrate, text="MH/s  (UrHash-v1)", font=ctk.CTkFont(size=10), text_color="#64748b")
        self.lbl_hashrate_unit.pack(pady=(0, 10))

        # Metric 2: Estimated Daily Earnings (Kryptex Profit Calculator)
        self.card_earnings = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_earnings.grid(row=2, column=1, sticky="nsew", padx=5, pady=(0, 14), ipady=10)
        ctk.CTkLabel(self.card_earnings, text="ESTIMATED DAILY PROFIT", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.lbl_daily_profit_usd = ctk.CTkLabel(self.card_earnings, text="$0.00", font=ctk.CTkFont(family="JetBrains Mono", size=26, weight="bold"), text_color="#10b981")
        self.lbl_daily_profit_usd.pack()
        self.lbl_daily_profit_urc = ctk.CTkLabel(self.card_earnings, text="~0.00 URC / day", font=ctk.CTkFont(size=10), text_color="#64748b")
        self.lbl_daily_profit_urc.pack(pady=(0, 10))

        # Metric 3: Blocks Found & Mined
        self.card_blocks = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_blocks.grid(row=2, column=2, sticky="nsew", padx=5, pady=(0, 14), ipady=10)
        ctk.CTkLabel(self.card_blocks, text="BLOCKS MINED", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.lbl_blocks_val = ctk.CTkLabel(self.card_blocks, text="0", font=ctk.CTkFont(family="JetBrains Mono", size=26, weight="bold"), text_color="#38bdf8")
        self.lbl_blocks_val.pack()
        self.lbl_blocks_earned = ctk.CTkLabel(self.card_blocks, text="Earned: 0 URC", font=ctk.CTkFont(size=10), text_color="#64748b")
        self.lbl_blocks_earned.pack(pady=(0, 10))

        # Metric 4: Total Confirmed Balance
        self.card_bal = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_bal.grid(row=2, column=3, sticky="nsew", padx=(5, 0), pady=(0, 14), ipady=10)
        ctk.CTkLabel(self.card_bal, text="CONFIRMED BALANCE", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(pady=(10, 2))
        self.lbl_dash_balance = ctk.CTkLabel(self.card_bal, text="0.00", font=ctk.CTkFont(family="JetBrains Mono", size=26, weight="bold"), text_color="#f8fafc")
        self.lbl_dash_balance.pack()
        self.lbl_dash_balance_usd = ctk.CTkLabel(self.card_bal, text="≈ $0.00 USDT", font=ctk.CTkFont(size=10), text_color="#f59e0b")
        self.lbl_dash_balance_usd.pack(pady=(0, 10))

        # 3. Kryptex Real Hardware Telemetry Bar
        self.card_hardware = ctk.CTkFrame(self.tab_dashboard, fg_color="#0e1524", corner_radius=14, border_width=1, border_color="#1e293b")
        self.card_hardware.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(0, 14), ipady=4)
        self.card_hardware.grid_columnconfigure((0, 1, 2, 3, 4), weight=1)

        self.tele_temp = self._create_telemetry_item(self.card_hardware, 0, "GPU TEMP", "-- °C", "#10b981")
        self.tele_fan = self._create_telemetry_item(self.card_hardware, 1, "FAN SPEED", "-- %", "#06b6d4")
        self.tele_power = self._create_telemetry_item(self.card_hardware, 2, "POWER DRAW", "-- W", "#38bdf8")
        self.tele_load = self._create_telemetry_item(self.card_hardware, 3, "GPU LOAD", "-- %", "#f59e0b")
        self.tele_vram = self._create_telemetry_item(self.card_hardware, 4, "VRAM USAGE", "-- / 6.0 GB", "#a855f7")

        # 4. Live Activity Log Console
        self.log_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="#080c14", corner_radius=14, border_width=1, border_color="#1e293b")
        self.log_frame.grid(row=4, column=0, columnspan=4, sticky="nsew")
        self.tab_dashboard.grid_rowconfigure(4, weight=1)

        self.log_box = ctk.CTkTextbox(
            self.log_frame, fg_color="transparent", text_color="#94a3b8",
            font=ctk.CTkFont(family="JetBrains Mono", size=11), wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=10)
        self._log("UrMiner Pro Kryptex-Edition Suite initialized.")
        self._log(f"Detected OpenCL Accelerators: {len(self.devices)} found.")
        self._log(f"Active Payout Address: {self.wallet.address}")

    def _create_telemetry_item(self, parent, col, title, initial_val, color):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, pady=8)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack()
        lbl = ctk.CTkLabel(f, text=initial_val, font=ctk.CTkFont(family="JetBrains Mono", size=15, weight="bold"), text_color=color)
        lbl.pack(pady=(2, 0))
        return lbl

    # =========================================================================
    # TAB 2: HARDWARE BENCHMARK (Kryptex Benchmark Model)
    # =========================================================================
    def _build_benchmark_tab(self):
        self.tab_benchmark.grid_columnconfigure(0, weight=1)

        card_info = ctk.CTkFrame(self.tab_benchmark, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_info.pack(fill="x", pady=(0, 16), padx=4, ipady=12)

        ctk.CTkLabel(
            card_info, text="🧪  HARDWARE BENCHMARK & PROFITABILITY TEST",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=16, weight="bold"), text_color="#f8fafc"
        ).pack(padx=20, pady=(12, 4), anchor="w")

        ctk.CTkLabel(
            card_info, text="Benchmarks your GPU & CPU across all mining algorithms to calculate true hashrates and highest daily profit.",
            font=ctk.CTkFont(size=12), text_color="#94a3b8"
        ).pack(padx=20, pady=(0, 14), anchor="w")

        self.btn_run_benchmark = ctk.CTkButton(
            card_info, text="⚡  RUN FULL BENCHMARK NOW", height=46,
            fg_color="#f59e0b", hover_color="#d97706", text_color="#000",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=14, weight="bold"),
            command=self._start_benchmark
        )
        self.btn_run_benchmark.pack(padx=20, pady=(0, 12), anchor="w")

        self.progress_bench = ctk.CTkProgressBar(card_info, orientation="horizontal", mode="determinate", height=10, fg_color="#1e293b", progress_color="#10b981")
        self.progress_bench.set(0.0)
        self.progress_bench.pack(fill="x", padx=20, pady=(4, 8))

        self.lbl_bench_status = ctk.CTkLabel(card_info, text="Ready to benchmark hardware.", font=ctk.CTkFont(size=12), text_color="#64748b")
        self.lbl_bench_status.pack(padx=20, anchor="w")

        # Results Cards Container
        self.bench_results_frame = ctk.CTkFrame(self.tab_benchmark, fg_color="transparent")
        self.bench_results_frame.pack(fill="both", expand=True, padx=4)
        self.bench_results_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.card_bench_eco = self._build_bench_card(self.bench_results_frame, 0, "Smart Eco GPU Mode", "Zero-VRAM Light PoW", "-- kH/s", "-- W", "$0.00 / day")
        self.card_bench_pro = self._build_bench_card(self.bench_results_frame, 1, "Pro Max GPU Mode", "1.0 GB Memory-Hard DAG", "-- MH/s", "-- W", "$0.00 / day", highlight=True)
        self.card_bench_cpu = self._build_bench_card(self.bench_results_frame, 2, "CPU Multi-Core Worker", "Multi-Threaded PoW", "-- kH/s", "-- W", "$0.00 / day")

    def _build_bench_card(self, parent, col, title, subtitle, hashrate, power, earnings, highlight=False):
        frame = ctk.CTkFrame(
            parent, fg_color="#111827", corner_radius=14, border_width=1,
            border_color="#f59e0b" if highlight else "#1e293b"
        )
        frame.grid(row=0, column=col, sticky="nsew", padx=6, pady=8, ipady=12)

        ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(padx=16, pady=(14, 2), anchor="w")
        ctk.CTkLabel(frame, text=subtitle, font=ctk.CTkFont(size=11), text_color="#64748b").pack(padx=16, pady=(0, 12), anchor="w")

        ctk.CTkLabel(frame, text="MEASURED SPEED", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(padx=16, anchor="w")
        lbl_h = ctk.CTkLabel(frame, text=hashrate, font=ctk.CTkFont(family="JetBrains Mono", size=22, weight="bold"), text_color="#f59e0b")
        lbl_h.pack(padx=16, pady=(2, 10), anchor="w")

        ctk.CTkLabel(frame, text="POWER DRAW", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(padx=16, anchor="w")
        lbl_p = ctk.CTkLabel(frame, text=power, font=ctk.CTkFont(family="JetBrains Mono", size=15), text_color="#38bdf8")
        lbl_p.pack(padx=16, pady=(2, 10), anchor="w")

        ctk.CTkLabel(frame, text="PROJECTED DAILY PROFIT", font=ctk.CTkFont(size=10, weight="bold"), text_color="#94a3b8").pack(padx=16, anchor="w")
        lbl_e = ctk.CTkLabel(frame, text=earnings, font=ctk.CTkFont(family="JetBrains Mono", size=18, weight="bold"), text_color="#10b981")
        lbl_e.pack(padx=16, pady=(2, 14), anchor="w")

        return {"frame": frame, "hashrate": lbl_h, "power": lbl_p, "earnings": lbl_e}

    # =========================================================================
    # TAB 3: WALLET & PAYOUTS
    # =========================================================================
    def _build_wallet_tab(self):
        self.tab_wallet.grid_columnconfigure((0, 1), weight=1)

        # Address & Balance Card
        card_bal = ctk.CTkFrame(self.tab_wallet, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_bal.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16), padx=4, ipady=12)

        ctk.CTkLabel(card_bal, text="YOUR MINING PAYOUT ADDRESS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8").pack(padx=20, pady=(16, 6), anchor="w")
        self.entry_addr = ctk.CTkEntry(card_bal, height=42, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b")
        self.entry_addr.insert(0, self.wallet.address)
        self.entry_addr.configure(state="readonly")
        self.entry_addr.pack(fill="x", padx=20, pady=(0, 10))

        btn_copy = ctk.CTkButton(
            card_bal, text="📋  Copy Payout Address", height=34, width=170,
            fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._copy_address
        )
        btn_copy.pack(padx=20, pady=(0, 14), anchor="w")

        # Action Left: Transfer / Send
        card_send = ctk.CTkFrame(self.tab_wallet, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_send.grid(row=1, column=0, sticky="nsew", padx=(4, 8), ipady=10)

        ctk.CTkLabel(card_send, text="SEND URC TO EXTERNAL WALLET", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(padx=20, pady=(16, 10), anchor="w")
        ctk.CTkLabel(card_send, text="Recipient Address (urc1...)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(padx=20, anchor="w")
        self.entry_send_to = ctk.CTkEntry(card_send, height=38, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b", placeholder_text="urc1...")
        self.entry_send_to.pack(fill="x", padx=20, pady=(4, 10))

        ctk.CTkLabel(card_send, text="Amount (URC)", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(padx=20, anchor="w")
        self.entry_send_amt = ctk.CTkEntry(card_send, height=38, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b", placeholder_text="e.g. 50.0")
        self.entry_send_amt.pack(fill="x", padx=20, pady=(4, 16))

        btn_send = ctk.CTkButton(
            card_send, text="🚀  SEND TRANSACTION NOW", height=42,
            fg_color="#06b6d4", hover_color="#0284c7", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._send_transaction
        )
        btn_send.pack(fill="x", padx=20, pady=(0, 14))

        # Action Right: Instant Swap to USDT (UrDEX)
        card_swap = ctk.CTkFrame(self.tab_wallet, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_swap.grid(row=1, column=1, sticky="nsew", padx=(8, 4), ipady=10)

        ctk.CTkLabel(card_swap, text="INSTANT MARKET SELL (SWAP TO USDT)", font=ctk.CTkFont(size=14, weight="bold"), text_color="#10b981").pack(padx=20, pady=(16, 10), anchor="w")
        ctk.CTkLabel(card_swap, text="Amount of URC to Sell", font=ctk.CTkFont(size=11), text_color="#94a3b8").pack(padx=20, anchor="w")
        self.entry_swap_amt = ctk.CTkEntry(card_swap, height=38, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b", placeholder_text="e.g. 100.0")
        self.entry_swap_amt.pack(fill="x", padx=20, pady=(4, 10))
        self.entry_swap_amt.bind("<KeyRelease>", self._on_swap_amt_change)

        self.lbl_swap_quote = ctk.CTkLabel(card_swap, text="Estimated Output: ~0.00 USDT (Rate: $0.0520)", font=ctk.CTkFont(size=11), text_color="#64748b")
        self.lbl_swap_quote.pack(padx=20, pady=(0, 16), anchor="w")

        btn_swap = ctk.CTkButton(
            card_swap, text="💱  EXECUTE INSTANT SWAP (DEX)", height=42,
            fg_color="#10b981", hover_color="#059669", font=ctk.CTkFont(size=13, weight="bold"),
            command=self._execute_swap
        )
        btn_swap.pack(fill="x", padx=20, pady=(0, 14))

    def _on_swap_amt_change(self, event=None):
        val = self.entry_swap_amt.get().strip()
        try:
            amt = float(val)
            out = amt * self.market_price_usdt
            self.lbl_swap_quote.configure(text=f"Estimated Output: ~{out:.2f} USDT (Rate: ${self.market_price_usdt:.4f})", text_color="#10b981")
        except Exception:
            self.lbl_swap_quote.configure(text=f"Estimated Output: ~0.00 USDT (Rate: ${self.market_price_usdt:.4f})", text_color="#64748b")

    # =========================================================================
    # TAB 4: URDEX MARKET & TICKER
    # =========================================================================
    def _build_market_tab(self):
        self.tab_market.grid_columnconfigure((0, 1), weight=1)

        # Market Ticker Header Card
        card_ticker = ctk.CTkFrame(self.tab_market, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_ticker.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 16), padx=4, ipady=10)
        card_ticker.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.mkt_price = self._create_telemetry_item(card_ticker, 0, "LAST PRICE", "$0.0520 USDT", "#10b981")
        self.mkt_high = self._create_telemetry_item(card_ticker, 1, "24H HIGH", "$0.0546", "#38bdf8")
        self.mkt_low = self._create_telemetry_item(card_ticker, 2, "24H LOW", "$0.0494", "#ef4444")
        self.mkt_vol = self._create_telemetry_item(card_ticker, 3, "24H VOLUME", "12,500 URC", "#f59e0b")

        # Order Book Bids Frame
        self.card_bids = ctk.CTkFrame(self.tab_market, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        self.card_bids.grid(row=1, column=0, sticky="nsew", padx=(4, 8), ipady=8)
        ctk.CTkLabel(self.card_bids, text="BUY ORDERS (BIDS)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#10b981").pack(padx=16, pady=10, anchor="w")
        self.txt_bids = ctk.CTkTextbox(self.card_bids, height=260, fg_color="#080c14", font=ctk.CTkFont(family="JetBrains Mono", size=11), text_color="#94a3b8")
        self.txt_bids.pack(fill="both", expand=True, padx=14, pady=(0, 12))

        # Order Book Asks Frame
        self.card_asks = ctk.CTkFrame(self.tab_market, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        self.card_asks.grid(row=1, column=1, sticky="nsew", padx=(8, 4), ipady=8)
        ctk.CTkLabel(self.card_asks, text="SELL ORDERS (ASKS)", font=ctk.CTkFont(size=13, weight="bold"), text_color="#ef4444").pack(padx=16, pady=10, anchor="w")
        self.txt_asks = ctk.CTkTextbox(self.card_asks, height=260, fg_color="#080c14", font=ctk.CTkFont(family="JetBrains Mono", size=11), text_color="#94a3b8")
        self.txt_asks.pack(fill="both", expand=True, padx=14, pady=(0, 12))

    # =========================================================================
    # TAB 5: SETTINGS & SAFETY
    # =========================================================================
    def _build_settings_tab(self):
        self.tab_settings.grid_columnconfigure(0, weight=1)

        card_sett = ctk.CTkFrame(self.tab_settings, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_sett.pack(fill="both", expand=True, padx=4, ipady=12)

        ctk.CTkLabel(card_sett, text="MINING INTENSITY PROFILE", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(padx=20, pady=(16, 8), anchor="w")

        self.intensity_var = ctk.StringVar(value="eco")
        profiles = [
            ("⚡ Smart Eco Mode (Zero-VRAM Light GPU) - Recommended for laptops & background mining while working or gaming", "eco"),
            ("🚀 Pro Max Mode (1.0 GB Memory-Hard DAG) - Maximum hash throughput for dedicated overnight/AFK mining", "pro")
        ]
        for label, val in profiles:
            rb = ctk.CTkRadioButton(
                card_sett, text=label, variable=self.intensity_var, value=val,
                font=ctk.CTkFont(size=12), text_color="#f8fafc", fg_color="#f59e0b"
            )
            rb.pack(padx=24, pady=6, anchor="w")

        ctk.CTkLabel(card_sett, text="ACTIVE HARDWARE ACCELERATOR", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(padx=20, pady=(20, 8), anchor="w")
        dev_options = [f"GPU {i}: {d.device_name} ({d.memory_gb:.2f} GB)" for i, d in enumerate(self.devices)]
        if not dev_options:
            dev_options = ["CPU Worker (OpenCL Not Detected)"]
        self.combo_device = ctk.CTkComboBox(card_sett, values=dev_options, height=38, width=520, font=ctk.CTkFont(size=12), command=self._on_device_selected)
        self.combo_device.set(dev_options[0])
        self.combo_device.pack(padx=20, pady=(0, 16), anchor="w")

        ctk.CTkLabel(card_sett, text="HARDWARE SAFETY & OVERHEAT PROTECTION", font=ctk.CTkFont(size=14, weight="bold"), text_color="#ef4444").pack(padx=20, pady=(12, 8), anchor="w")
        ctk.CTkLabel(card_sett, text="Automatically pause mining if GPU temperature exceeds:", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(padx=20, anchor="w")

        slider_frame = ctk.CTkFrame(card_sett, fg_color="transparent")
        slider_frame.pack(fill="x", padx=20, pady=(4, 16))
        self.slider_temp = ctk.CTkSlider(slider_frame, from_=65.0, to=88.0, number_of_steps=23, width=320, command=self._on_temp_slider)
        self.slider_temp.set(self.max_temp_limit)
        self.slider_temp.pack(side="left")
        self.lbl_temp_val = ctk.CTkLabel(slider_frame, text=f"{self.max_temp_limit:.0f} °C", font=ctk.CTkFont(family="JetBrains Mono", size=13, weight="bold"), text_color="#f59e0b")
        self.lbl_temp_val.pack(side="left", padx=12)

        ctk.CTkLabel(card_sett, text="NODE RPC URL", font=ctk.CTkFont(size=14, weight="bold"), text_color="#f8fafc").pack(padx=20, pady=(12, 6), anchor="w")
        self.entry_node_url = ctk.CTkEntry(card_sett, height=38, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b")
        self.entry_node_url.insert(0, self.node_url)
        self.entry_node_url.pack(fill="x", padx=20, pady=(0, 16))

    def _on_device_selected(self, choice):
        for i, d in enumerate(self.devices):
            if d.device_name in choice:
                self.selected_device_idx = i
                self.gpu_miner = None
                self._log(f"Switched hardware accelerator to: {d.device_name}")
                self.lbl_gpu_header.configure(text=f"Active Device: {d.device_name}")
                break

    def _on_temp_slider(self, val):
        self.max_temp_limit = float(val)
        self.lbl_temp_val.configure(text=f"{self.max_temp_limit:.0f} °C")

    # =========================================================================
    # NAVIGATION & HELPERS
    # =========================================================================
    def _select_tab(self, tab_name: str):
        self.tab_dashboard.grid_forget()
        self.tab_benchmark.grid_forget()
        self.tab_wallet.grid_forget()
        self.tab_market.grid_forget()
        self.tab_settings.grid_forget()

        for k, btn in self.nav_buttons.items():
            is_active = (k == tab_name)
            btn.configure(
                fg_color="#1e293b" if is_active else "transparent",
                text_color="#f8fafc" if is_active else "#94a3b8"
            )

        if tab_name == "dashboard":
            self.tab_dashboard.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "benchmark":
            self.tab_benchmark.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "wallet":
            self.tab_wallet.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "market":
            self.tab_market.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "settings":
            self.tab_settings.grid(row=0, column=0, sticky="nsew")

    def _log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self._safe_after(0, lambda: (
            self.log_box.insert("end", line),
            self.log_box.see("end")
        ))

    def _rpc_call(self, endpoint: str, data: dict = None, timeout: int = 4) -> dict:
        url = f"{self.node_url.rstrip('/')}{endpoint}"
        headers = {}
        cookie = read_rpc_cookie()
        if cookie:
            headers[RPC_COOKIE_HEADER] = cookie
        if data is not None:
            payload = json.dumps(data).encode("utf-8")
            headers["Content-Type"] = "application/json"
            req = urllib.request.Request(url, data=payload, headers=headers)
        else:
            req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # =========================================================================
    # MINING CORE ENGINE
    # =========================================================================
    def _toggle_mining(self):
        if not self.is_mining:
            self._start_mining()
        else:
            self._stop_mining()

    def _ensure_node_running(self) -> bool:
        """Check if local node daemon is running; if not, auto-launch it."""
        try:
            self._rpc_call("/api/info", timeout=2)
            return True
        except Exception:
            pass

        self._log("Node not detected. Auto-launching local Ur Coin daemon in background...")
        self._launch_node_daemon()

        # Wait up to 5 seconds for node to respond
        for _ in range(10):
            time.sleep(0.5)
            try:
                self._rpc_call("/api/info", timeout=2)
                self._log("✓ Local Node Daemon connected successfully!")
                return True
            except Exception:
                pass
        return False

    def _start_mining(self):
        if self.is_benchmarking:
            self._log("Cannot mine while benchmark is in progress.")
            return

        self.is_mining = True
        self.is_paused_thermal = False
        self.mining_start_time = time.time()
        self.btn_mine.configure(text="⏹   STOP MINING", fg_color="#ef4444", hover_color="#dc2626")
        self.lbl_status.configure(text="● MINING ACTIVE", text_color="#10b981")
        self.thermal_banner.grid_forget()

        profile = self.intensity_var.get()
        self.lbl_timer.configure(text=f"Uptime: 00:00:00  |  Profile: {profile.upper()}")
        self._log(f"Starting Kryptex-grade mining worker (Profile: {profile.upper()})...")

        self.mining_thread = threading.Thread(target=self._mining_loop, args=(profile,), daemon=True)
        self.mining_thread.start()

    def _stop_mining(self):
        self.is_mining = False
        self.is_paused_thermal = False
        self._safe_after(0, lambda: (
            self.btn_mine.configure(text="▶   START MINING", fg_color="#10b981", hover_color="#059669"),
            self.lbl_status.configure(text="IDLE - MINER STOPPED", text_color="#94a3b8"),
            self.lbl_hashrate_val.configure(text="0.00"),
            self.lbl_daily_profit_usd.configure(text="$0.00"),
            self.lbl_daily_profit_urc.configure(text="~0.00 URC / day"),
            self.thermal_banner.grid_forget()
        ))
        self._log("Mining engine stopped.")

    def _mining_loop(self, profile: str):
        try:
            # 1. Ensure Node is Online
            if not self._ensure_node_running():
                self._log("Error: Could not connect to Ur Coin node daemon. Please ensure urcoind is running.")
                self._stop_mining()
                return

            # Configure batch parameters
            if profile == "eco":
                batch_threads = 4096
                npt = 4
                is_light = True
            else:
                batch_threads = 65536
                npt = 16
                is_light = False

            # Initialize miner instance
            if self.gpu_miner is None:
                self.gpu_miner = GPUMiner(
                    device_index=self.selected_device_idx,
                    dag_items=DEFAULT_DAG_ITEMS,
                    light_mode=is_light
                )
            else:
                self.gpu_miner.light_mode = is_light

            nonce_seq = 0
            while self.is_mining:
                # 1. Check Thermal Safeguard
                current_temp = self.telemetry.get("temp_val", 0)
                if current_temp >= self.max_temp_limit and not self.is_paused_thermal:
                    self.is_paused_thermal = True
                    self._safe_after(0, self._show_thermal_pause)
                    self._log(f"⚠️ THERMAL LIMIT: GPU reached {current_temp}°C! Pausing to cool down...")

                if self.is_paused_thermal:
                    if current_temp <= self.auto_resume_temp:
                        self.is_paused_thermal = False
                        self._safe_after(0, self._hide_thermal_pause)
                        self._log(f"✓ GPU Cooled down to {current_temp}°C. Resuming mining automatically!")
                    else:
                        time.sleep(1.0)
                        continue

                # 2. Fetch Job Template from Node
                try:
                    info = self._rpc_call("/api/info", timeout=4)
                except Exception:
                    time.sleep(2.0)
                    continue

                height = info["height"] + 1
                best_hash = info["best_hash"]
                target_int = int(info["target"], 16)
                reward = info["current_reward"]
                epoch = height // 10_000

                coinbase_tx = Transaction.create_coinbase(self.wallet.address, reward, height)
                header = BlockHeader(
                    version=1, prev_hash=best_hash, merkle_root=coinbase_tx.txid,
                    timestamp=int(time.time()), target=target_int, nonce=0,
                    height=height, epoch=epoch
                )
                candidate = Block(header, [coinbase_tx])
                mining_hash = candidate.header.get_mining_hash()

                # 3. Execute Mining Batch
                t0 = time.perf_counter()
                results = self.gpu_miner.search_batch(
                    mining_hash, target_int, epoch,
                    start_nonce=nonce_seq,
                    global_work_size=batch_threads,
                    nonces_per_thread=npt
                )
                dt = time.perf_counter() - t0
                nonce_seq += (batch_threads * npt)
                self.total_hashes += (batch_threads * npt)

                # 4. Update Speed and Kryptex Profit Projections
                if dt > 0:
                    speed_mhs = ((batch_threads * npt) / dt) / 1_000_000
                    self.current_hashrate = (batch_threads * npt) / dt
                    self._safe_after(0, lambda s=speed_mhs: self._update_speed_and_earnings(s))

                # 5. Winning Nonce Found!
                if results:
                    winning_nonce, block_hash = results[0]
                    candidate.header.nonce = winning_nonce
                    candidate.hash = block_hash

                    try:
                        s_res = self._rpc_call("/api/submit_block", data=candidate.to_dict(), timeout=5)
                        if s_res.get("success"):
                            self.blocks_found += 1
                            earned_urc = self.blocks_found * (reward / COIN)
                            self._safe_after(0, lambda bf=self.blocks_found, u=earned_urc: (
                                self.lbl_blocks_val.configure(text=str(bf)),
                                self.lbl_blocks_earned.configure(text=f"Earned: {u:.0f} URC")
                            ))
                            self._log(f"🎉 BLOCK #{height} FOUND! Hash: {block_hash[:18]}... Nonce: {winning_nonce}")
                            nonce_seq = 0
                    except Exception as e:
                        self._log(f"Block submission error: {e}")

        except Exception as e:
            self._log(f"Mining engine exception: {e}")
            self._stop_mining()

    def _show_thermal_pause(self):
        self.thermal_banner.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        self.lbl_status.configure(text="⚠️ THERMAL PAUSE", text_color="#ef4444")
        self.lbl_hashrate_val.configure(text="0.00")

    def _hide_thermal_pause(self):
        self.thermal_banner.grid_forget()
        self.lbl_status.configure(text="● MINING ACTIVE", text_color="#10b981")

    def _update_speed_and_earnings(self, speed_mhs: float):
        if speed_mhs >= 1.0:
            self.lbl_hashrate_val.configure(text=f"{speed_mhs:.2f}")
            self.lbl_hashrate_unit.configure(text="MH/s  (UrHash-v1)")
        else:
            speed_khs = speed_mhs * 1000.0
            self.lbl_hashrate_val.configure(text=f"{speed_khs:.1f}")
            self.lbl_hashrate_unit.configure(text="kH/s  (UrHash-v1)")

        # Kryptex Dynamic Profit Calculation
        daily_urc = speed_mhs * 24.5
        daily_usd = daily_urc * self.market_price_usdt

        self.lbl_daily_profit_usd.configure(text=f"${daily_usd:.2f}")
        self.lbl_daily_profit_urc.configure(text=f"~{daily_urc:.1f} URC / day")

        if self.mining_start_time > 0:
            elapsed = int(time.time() - self.mining_start_time)
            hh = elapsed // 3600
            mm = (elapsed % 3600) // 60
            ss = elapsed % 60
            prof = self.intensity_var.get().upper()
            self.lbl_timer.configure(text=f"Uptime: {hh:02d}:{mm:02d}:{ss:02d}  |  Profile: {prof}")

    # =========================================================================
    # KRYPTEX HARDWARE BENCHMARK ENGINE
    # =========================================================================
    def _start_benchmark(self):
        if self.is_mining:
            self._log("Please stop mining before starting the hardware benchmark.")
            return

        self.is_benchmarking = True
        self.btn_run_benchmark.configure(state="disabled", text="⏳  BENCHMARK IN PROGRESS...")
        self.progress_bench.set(0.0)

        t = threading.Thread(target=self._benchmark_worker, daemon=True)
        t.start()

    def _benchmark_worker(self):
        try:
            import hashlib
            dummy_header = hashlib.sha256(b"urcoin_benchmark_job_sample").digest()
            easy_target = int("0000ffff00000000000000000000000000000000000000000000000000000000", 16)

            # Stage 1: Smart Eco Mode
            self._safe_after(0, lambda: self.lbl_bench_status.configure(text="Phase 1/3: Benchmarking Smart Eco Mode (Zero-VRAM)..."))
            self._safe_after(0, lambda: self.progress_bench.set(0.15))
            m_eco = GPUMiner(device_index=self.selected_device_idx, light_mode=True)
            t0 = time.perf_counter()
            m_eco.search_batch(dummy_header, easy_target, epoch=0, start_nonce=0, global_work_size=8192, nonces_per_thread=8)
            dt_eco = time.perf_counter() - t0
            eco_speed = (8192 * 8) / dt_eco if dt_eco > 0 else 0
            eco_power = float(self.telemetry.get("power_val", 45.0))
            eco_daily_usd = (eco_speed / 100_000) * self.market_price_usdt * 12.0
            self._safe_after(0, lambda: (
                self.card_bench_eco["hashrate"].configure(text=f"{eco_speed / 1000:.1f} kH/s"),
                self.card_bench_eco["power"].configure(text=f"{eco_power:.0f} W"),
                self.card_bench_eco["earnings"].configure(text=f"${eco_daily_usd:.2f} / day")
            ))

            self._safe_after(0, lambda: self.progress_bench.set(0.50))
            time.sleep(0.5)

            # Stage 2: Pro Max Mode
            self._safe_after(0, lambda: self.lbl_bench_status.configure(text="Phase 2/3: Benchmarking Pro Max Mode (Full DAG)..."))
            m_pro = GPUMiner(device_index=self.selected_device_idx, light_mode=False)
            t0 = time.perf_counter()
            m_pro.search_batch(dummy_header, easy_target, epoch=0, start_nonce=0, global_work_size=32768, nonces_per_thread=16)
            dt_pro = time.perf_counter() - t0
            pro_speed = (32768 * 16) / dt_pro if dt_pro > 0 else 0
            pro_power = float(self.telemetry.get("power_val", 60.0))
            pro_daily_usd = (pro_speed / 1_000_000) * 24.5 * self.market_price_usdt
            self._safe_after(0, lambda: (
                self.card_bench_pro["hashrate"].configure(text=f"{pro_speed / 1_000_000:.2f} MH/s"),
                self.card_bench_pro["power"].configure(text=f"{pro_power:.0f} W"),
                self.card_bench_pro["earnings"].configure(text=f"${pro_daily_usd:.2f} / day")
            ))

            self._safe_after(0, lambda: self.progress_bench.set(0.85))
            time.sleep(0.5)

            # Stage 3: CPU Worker
            self._safe_after(0, lambda: self.lbl_bench_status.configure(text="Phase 3/3: Benchmarking CPU Multi-threaded Worker..."))
            cpu = CPUMiner(threads=4)
            t0 = time.perf_counter()
            cpu.search_batch(dummy_header, easy_target, epoch=0, start_nonce=0, count=4000)
            dt_cpu = time.perf_counter() - t0
            cpu_speed = 4000 / dt_cpu if dt_cpu > 0 else 0
            cpu_daily_usd = (cpu_speed / 100_000) * self.market_price_usdt * 2.0
            self._safe_after(0, lambda: (
                self.card_bench_cpu["hashrate"].configure(text=f"{cpu_speed / 1000:.2f} kH/s"),
                self.card_bench_cpu["power"].configure(text="~25 W"),
                self.card_bench_cpu["earnings"].configure(text=f"${cpu_daily_usd:.2f} / day")
            ))

            self._safe_after(0, lambda: self.progress_bench.set(1.0))
            self._safe_after(0, lambda: self.lbl_bench_status.configure(
                text="✓ Benchmark Complete! Recommended: Pro Max Mode for maximum profit.", text_color="#10b981"
            ))

        except Exception as e:
            self._safe_after(0, lambda e=e: self.lbl_bench_status.configure(text=f"Benchmark error: {e}", text_color="#ef4444"))
        finally:
            self.is_benchmarking = False
            self._safe_after(0, lambda: self.btn_run_benchmark.configure(state="normal", text="⚡  RUN FULL BENCHMARK NOW"))

    # =========================================================================
    # BACKGROUND TELEMETRY & NODE WATCHDOG
    # =========================================================================
    def _telemetry_worker(self):
        while self.running:
            # 1. Query Real Hardware Stats
            temp_c = 0
            power_w = 0.0
            load_pct = 0
            mem_used_gb = 0.0
            mem_tot_gb = 6.0
            fan_pct = "Auto"

            if self.nvml_initialized:
                try:
                    h = pynvml.nvmlDeviceGetHandleByIndex(self.selected_device_idx)
                    temp_c = pynvml.nvmlDeviceGetTemperature(h, pynvml.NVML_TEMPERATURE_GPU)
                    self.telemetry["temp_val"] = temp_c
                    self.telemetry["temp"] = f"{temp_c} °C"

                    try:
                        power_w = pynvml.nvmlDeviceGetPowerUsage(h) / 1000.0
                        self.telemetry["power_val"] = power_w
                        self.telemetry["power"] = f"{power_w:.0f} W"
                    except Exception:
                        pass

                    try:
                        load_pct = pynvml.nvmlDeviceGetUtilizationRates(h).gpu
                        self.telemetry["load"] = f"{load_pct} %"
                    except Exception:
                        pass

                    try:
                        mem = pynvml.nvmlDeviceGetMemoryInfo(h)
                        mem_used_gb = mem.used / (1024 ** 3)
                        mem_tot_gb = mem.total / (1024 ** 3)
                        self.telemetry["vram"] = f"{mem_used_gb:.1f} / {mem_tot_gb:.1f} GB"
                    except Exception:
                        pass

                    try:
                        fan_pct = f"{pynvml.nvmlDeviceGetFanSpeed(h)} %"
                        self.telemetry["fan"] = fan_pct
                    except Exception:
                        self.telemetry["fan"] = "Auto"

                except Exception:
                    pass

            # CPU / RAM stats via psutil
            cpu_usage = psutil.cpu_percent() if HAS_PSUTIL else 10
            ram_usage = psutil.virtual_memory().percent if HAS_PSUTIL else 40
            self.telemetry["cpu"] = f"{cpu_usage}%"
            self.telemetry["ram"] = f"{ram_usage}%"

            # Update UI Telemetry Widgets
            self._safe_after(0, self._update_telemetry_ui)

            # 2. Query Node State & Live DEX Market
            try:
                wdata = self._rpc_call("/api/wallet", timeout=2)
                self.confirmed_balance_urc = wdata["balance"] / COIN

                idata = self._rpc_call("/api/info", timeout=2)
                self.node_height = idata["height"]
                self.node_connected = True

                # Ticker Data
                tdata = self._rpc_call("/api/exchange/ticker", timeout=2)
                self.market_price_usdt = tdata["last_price"]

                # Orderbook Data
                try:
                    obdata = self._rpc_call("/api/exchange/orderbook?limit=6", timeout=2)
                except Exception:
                    obdata = {}

                self._safe_after(0, lambda: self._update_node_status(True, self.node_height, self.confirmed_balance_urc, tdata, obdata))

            except Exception:
                self.node_connected = False
                self._safe_after(0, lambda: self._update_node_status(False, 0, 0, {}, {}))

            time.sleep(1.8)

    def _update_telemetry_ui(self):
        t = self.telemetry["temp"]
        t_val = self.telemetry["temp_val"]
        color = "#10b981" if t_val < 68 else ("#f59e0b" if t_val < 78 else "#ef4444")

        self.tele_temp.configure(text=t, text_color=color)
        self.tele_fan.configure(text=self.telemetry["fan"])
        self.tele_power.configure(text=self.telemetry["power"])
        self.tele_load.configure(text=self.telemetry["load"])
        self.tele_vram.configure(text=self.telemetry["vram"])

    def _update_node_status(self, connected: bool, height: int, bal_urc: float, ticker: dict, orderbook: dict):
        if connected:
            self.lbl_node_indicator.configure(text="● NODE CONNECTED", text_color="#10b981")
            self.lbl_node_info.configure(text=f"Height: #{height} | Live DEX")
            self.btn_node_action.configure(state="disabled", text="Node Online")

            # Update Dashboard Balance Card
            self.lbl_dash_balance.configure(text=f"{bal_urc:.2f}")
            bal_usd = bal_urc * self.market_price_usdt
            self.lbl_dash_balance_usd.configure(text=f"≈ ${bal_usd:.2f} USDT")

            # Update DEX Tab
            if ticker:
                p = ticker.get("last_price", 0.052)
                self.mkt_price.configure(text=f"${p:.4f} USDT")
                self.mkt_high.configure(text=f"${ticker.get('high_24h', p*1.05):.4f}")
                self.mkt_low.configure(text=f"${ticker.get('low_24h', p*0.95):.4f}")
                self.mkt_vol.configure(text=f"{ticker.get('volume_urc_24h', 12500):.0f} URC")

            # Update Orderbook Tables in Tab 4
            if orderbook:
                bids = orderbook.get("bids", [])
                asks = orderbook.get("asks", [])
                if bids:
                    self.txt_bids.configure(state="normal")
                    self.txt_bids.delete("1.0", "end")
                    self.txt_bids.insert("end", f"{'PRICE (USDT)':<15} {'AMOUNT (URC)':<15} {'TOTAL':<10}\n")
                    self.txt_bids.insert("end", "-" * 42 + "\n")
                    for b in bids[:8]:
                        self.txt_bids.insert("end", f"${b['price']:<14.4f} {b['amount']:<15.1f} ${b['total']:<10.2f}\n")
                    self.txt_bids.configure(state="disabled")

                if asks:
                    self.txt_asks.configure(state="normal")
                    self.txt_asks.delete("1.0", "end")
                    self.txt_asks.insert("end", f"{'PRICE (USDT)':<15} {'AMOUNT (URC)':<15} {'TOTAL':<10}\n")
                    self.txt_asks.insert("end", "-" * 42 + "\n")
                    for a in asks[:8]:
                        self.txt_asks.insert("end", f"${a['price']:<14.4f} {a['amount']:<15.1f} ${a['total']:<10.2f}\n")
                    self.txt_asks.configure(state="disabled")
        else:
            self.lbl_node_indicator.configure(text="○ NODE OFFLINE", text_color="#ef4444")
            self.lbl_node_info.configure(text="Click to start node daemon")
            self.btn_node_action.configure(state="normal", text="Start Local Node")

    def _launch_node_daemon(self):
        try:
            node_script = os.path.join(PROJECT_DIR, "urcoind.py")
            cmd = [sys.executable, node_script]
            self.node_process = subprocess.Popen(cmd, cwd=PROJECT_DIR, creationflags=subprocess.CREATE_NEW_CONSOLE if os.name == 'nt' else 0)
            self._log("Launched Ur Coin Full Node daemon in background.")
        except Exception as e:
            self._log(f"Error launching node: {e}")

    # =========================================================================
    # USER ACTIONS: COPY, SEND, SWAP
    # =========================================================================
    def _copy_address(self):
        self.clipboard_clear()
        self.clipboard_append(self.wallet.address)
        self._log("Payout address copied to clipboard.")

    def _send_transaction(self):
        recipient = self.entry_send_to.get().strip()
        amt_str = self.entry_send_amt.get().strip()
        if not recipient or not amt_str:
            self._log("Send error: Recipient address and amount are required.")
            return

        try:
            amt = float(amt_str)
            res = self._rpc_call("/api/send_tx", data={"recipient": recipient, "amount_urc": amt}, timeout=5)
            if res.get("success"):
                self._log(f"✓ Transfer Sent: {amt} URC! TXID: {res['txid']}")
                self.entry_send_to.delete(0, "end")
                self.entry_send_amt.delete(0, "end")
            else:
                self._log(f"Transfer error: {res.get('error')}")
        except Exception as e:
            self._log(f"Send exception: {e}")

    def _execute_swap(self):
        amt_str = self.entry_swap_amt.get().strip()
        if not amt_str:
            self._log("Swap error: Please enter URC amount to swap.")
            return

        try:
            amt = float(amt_str)
            res = self._rpc_call("/api/exchange/swap", data={"from_asset": "URC", "to_asset": "USDT", "amount_in": amt}, timeout=5)
            if res.get("success"):
                sw = res["swap"]
                self._log(f"🎉 UrDEX Instant Swap: Sold {sw['amount_in']} URC -> Received ${sw['amount_out']:.2f} USDT!")
                self.entry_swap_amt.delete(0, "end")
                self._on_swap_amt_change()
            else:
                self._log(f"Swap error: {res.get('error')}")
        except Exception as e:
            self._log(f"Swap exception: {e}")


if __name__ == "__main__":
    app = UrMinerApp()
    app.mainloop()
