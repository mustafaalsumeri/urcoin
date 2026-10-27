"""
UrMiner GUI - Next-Generation Desktop GPU Mining Suite for Windows
Inspired by NiceHash, Kryptex, and unMineable.
Features:
- Sleek Futuristic Dark Mode GUI (CustomTkinter)
- 1-Click Start / Stop Mining
- Real-Time Hardware Telemetry (GPU Temp, Fan, Power, VRAM, Load)
- Live Hashrate Meter & Block Rewards Tracker
- Multi-profile Intensity (Light / Balanced / Maximum)
- Integrated Wallet & Quick Send
"""

import sys
import os
import time
import json
import threading
import subprocess
import urllib.request
import customtkinter as ctk

# Ensure UTF-8 output
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from urcoin.miner_gpu import GPUMiner, get_opencl_devices
from urcoin.core import Block, BlockHeader, Transaction, calculate_block_reward, COIN, DEFAULT_DAG_ITEMS
from urcoin.wallet import Wallet
from urcoin.auth import RPC_COOKIE_HEADER, read_rpc_cookie

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class UrMinerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("UrMiner v1.0 - GPU Mining Suite (Ur Coin)")
        self.geometry("960x680")
        self.minsize(880, 620)
        self.configure(fg_color="#090d16")

        # Mining State
        self.is_mining = False
        self.mining_thread = None
        self.gpu_miner = None
        self.devices = get_opencl_devices()
        self.selected_device_idx = 0
        self.blocks_found = 0
        self.total_hashes = 0
        self.current_hashrate = 0.0

        # Hardware Stats
        self.gpu_temp = "N/A"
        self.gpu_power = "N/A"
        self.gpu_load = "N/A"
        self.gpu_mem_used = "N/A"

        # Load or create local wallet
        self.wallet = Wallet.create_or_load("urcoin_wallet.json")
        self.node_url = "http://127.0.0.1:9334"

        # Setup Layout
        self._setup_ui()

        # Start Background Telemetry & Node Monitor Thread
        self.running = True
        self.telemetry_thread = threading.Thread(target=self._telemetry_worker, daemon=True)
        self.telemetry_thread.start()

    def _setup_ui(self):
        # Grid layout: Left Sidebar (Navigation) + Right Content Frame
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ----------------- SIDEBAR -----------------
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0, fg_color="#0e1524")
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(6, weight=1)

        # Logo / Title
        self.logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.logo_frame.grid(row=0, column=0, padx=20, pady=(24, 20), sticky="w")

        self.logo_badge = ctk.CTkLabel(
            self.logo_frame, text="UR", width=42, height=42,
            fg_color="#f59e0b", text_color="#000", corner_radius=10,
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=20, weight="bold")
        )
        self.logo_badge.pack(side="left", padx=(0, 12))

        self.logo_text = ctk.CTkLabel(
            self.logo_frame, text="UrMiner",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=20, weight="bold"),
            text_color="#f8fafc"
        )
        self.logo_text.pack(side="left")

        # Navigation Buttons
        self.btn_nav_dash = ctk.CTkButton(
            self.sidebar, text="⚡  Dashboard", anchor="w", height=40,
            fg_color="#1e293b", hover_color="#334155", text_color="#f8fafc",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._select_tab("dashboard")
        )
        self.btn_nav_dash.grid(row=1, column=0, padx=16, pady=6, sticky="ew")

        self.btn_nav_wallet = ctk.CTkButton(
            self.sidebar, text="💼  Wallet & Payouts", anchor="w", height=40,
            fg_color="transparent", hover_color="#1e293b", text_color="#94a3b8",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._select_tab("wallet")
        )
        self.btn_nav_wallet.grid(row=2, column=0, padx=16, pady=6, sticky="ew")

        self.btn_nav_settings = ctk.CTkButton(
            self.sidebar, text="⚙️  Settings & Mode", anchor="w", height=40,
            fg_color="transparent", hover_color="#1e293b", text_color="#94a3b8",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=lambda: self._select_tab("settings")
        )
        self.btn_nav_settings.grid(row=3, column=0, padx=16, pady=6, sticky="ew")

        # Sidebar Footer: Node Status Indicator
        self.node_status_card = ctk.CTkFrame(self.sidebar, fg_color="#131c2e", corner_radius=12)
        self.node_status_card.grid(row=7, column=0, padx=16, pady=20, sticky="ew")

        self.lbl_node_indicator = ctk.CTkLabel(
            self.node_status_card, text="● NODE CONNECTED",
            text_color="#10b981", font=ctk.CTkFont(size=11, weight="bold")
        )
        self.lbl_node_indicator.pack(pady=(10, 2))

        self.lbl_node_height = ctk.CTkLabel(
            self.node_status_card, text="Height: #0",
            text_color="#64748b", font=ctk.CTkFont(size=11)
        )
        self.lbl_node_height.pack(pady=(0, 10))

        # ----------------- MAIN CONTENT CONTAINER -----------------
        self.content_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=24, pady=24)
        self.content_frame.grid_rowconfigure(0, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        # Tab Frames
        self.tab_dashboard = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_wallet = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.tab_settings = ctk.CTkFrame(self.content_frame, fg_color="transparent")

        self._build_dashboard_tab()
        self._build_wallet_tab()
        self._build_settings_tab()

        self._select_tab("dashboard")

    # =========================================================================
    # TAB 1: DASHBOARD
    # =========================================================================
    def _build_dashboard_tab(self):
        self.tab_dashboard.grid_columnconfigure((0, 1, 2), weight=1)

        # 1. Header Banner Card (Mining Button + Status)
        self.banner_card = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=18, border_width=1, border_color="#1e293b")
        self.banner_card.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 18), ipady=8)

        # Big Action Button
        self.btn_mine = ctk.CTkButton(
            self.banner_card, text="▶   START MINING",
            font=ctk.CTkFont(family="Plus Jakarta Sans", size=18, weight="bold"),
            height=60, width=280, corner_radius=14,
            fg_color="#10b981", hover_color="#059669",
            command=self._toggle_mining
        )
        self.btn_mine.pack(side="left", padx=24, pady=16)

        # Status & GPU banner info
        self.banner_info = ctk.CTkFrame(self.banner_card, fg_color="transparent")
        self.banner_info.pack(side="left", fill="both", expand=True, padx=12, pady=16)

        self.lbl_status = ctk.CTkLabel(
            self.banner_info, text="IDLE - READY TO MINE",
            font=ctk.CTkFont(size=14, weight="bold"), text_color="#94a3b8"
        )
        self.lbl_status.pack(anchor="w")

        dev_name = self.devices[0].device_name if self.devices else "No GPU Detected"
        self.lbl_gpu_header = ctk.CTkLabel(
            self.banner_info, text=f"Active Hardware: {dev_name}",
            font=ctk.CTkFont(size=13), text_color="#06b6d4"
        )
        self.lbl_gpu_header.pack(anchor="w", pady=(4, 0))

        # 2. Main Metrics Grid
        # Metric 1: Hashrate
        self.card_hashrate = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        self.card_hashrate.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 16), ipady=12)
        ctk.CTkLabel(self.card_hashrate, text="CURRENT HASHRATE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(pady=(12, 4))
        self.lbl_hashrate_val = ctk.CTkLabel(self.card_hashrate, text="0.00", font=ctk.CTkFont(family="JetBrains Mono", size=32, weight="bold"), text_color="#f59e0b")
        self.lbl_hashrate_val.pack()
        self.lbl_hashrate_unit = ctk.CTkLabel(self.card_hashrate, text="MH/s  (UrHash-v1)", font=ctk.CTkFont(size=12), text_color="#64748b")
        self.lbl_hashrate_unit.pack(pady=(0, 12))

        # Metric 2: Blocks & Rewards
        self.card_blocks = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        self.card_blocks.grid(row=1, column=1, sticky="nsew", padx=8, pady=(0, 16), ipady=12)
        ctk.CTkLabel(self.card_blocks, text="BLOCKS MINED", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(pady=(12, 4))
        self.lbl_blocks_val = ctk.CTkLabel(self.card_blocks, text="0", font=ctk.CTkFont(family="JetBrains Mono", size=32, weight="bold"), text_color="#10b981")
        self.lbl_blocks_val.pack()
        self.lbl_earned_val = ctk.CTkLabel(self.card_blocks, text="Earned: 0 URC", font=ctk.CTkFont(size=12), text_color="#64748b")
        self.lbl_earned_val.pack(pady=(0, 12))

        # Metric 3: Wallet Total Balance
        self.card_balance = ctk.CTkFrame(self.tab_dashboard, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        self.card_balance.grid(row=1, column=2, sticky="nsew", padx=(8, 0), pady=(0, 16), ipady=12)
        ctk.CTkLabel(self.card_balance, text="TOTAL CONFIRMED BALANCE", font=ctk.CTkFont(size=11, weight="bold"), text_color="#94a3b8").pack(pady=(12, 4))
        self.lbl_balance_val = ctk.CTkLabel(self.card_balance, text="0.00", font=ctk.CTkFont(family="JetBrains Mono", size=32, weight="bold"), text_color="#f8fafc")
        self.lbl_balance_val.pack()
        ctk.CTkLabel(self.card_balance, text="URC (Ur Coin)", font=ctk.CTkFont(size=12), text_color="#f59e0b").pack(pady=(0, 12))

        # 3. Hardware Telemetry Card
        self.card_hardware = ctk.CTkFrame(self.tab_dashboard, fg_color="#0e1524", corner_radius=16, border_width=1, border_color="#1e293b")
        self.card_hardware.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(0, 16), ipady=6)
        self.card_hardware.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self.telemetry_temp = self._create_telemetry_item(self.card_hardware, 0, "GPU TEMP", "-- °C", "#10b981")
        self.telemetry_power = self._create_telemetry_item(self.card_hardware, 1, "POWER DRAW", "-- W", "#38bdf8")
        self.telemetry_load = self._create_telemetry_item(self.card_hardware, 2, "GPU LOAD", "-- %", "#f59e0b")
        self.telemetry_vram = self._create_telemetry_item(self.card_hardware, 3, "VRAM USAGE", "-- / 6.0 GB", "#a855f7")

        # 4. Live Activity Log Window
        self.log_frame = ctk.CTkFrame(self.tab_dashboard, fg_color="#080c14", corner_radius=14, border_width=1, border_color="#1e293b")
        self.log_frame.grid(row=3, column=0, columnspan=3, sticky="nsew")
        self.tab_dashboard.grid_rowconfigure(3, weight=1)

        self.log_box = ctk.CTkTextbox(
            self.log_frame, fg_color="transparent", text_color="#94a3b8",
            font=ctk.CTkFont(family="JetBrains Mono", size=11), wrap="word"
        )
        self.log_box.pack(fill="both", expand=True, padx=12, pady=12)
        self._log("UrMiner v1.0 Desktop Mining Suite initialized.")
        self._log(f"Detected GPU: {dev_name}")
        self._log(f"Payout Address: {self.wallet.address}")

    def _create_telemetry_item(self, parent, col, title, initial_val, color):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.grid(row=0, column=col, pady=10)
        ctk.CTkLabel(f, text=title, font=ctk.CTkFont(size=10, weight="bold"), text_color="#64748b").pack()
        lbl = ctk.CTkLabel(f, text=initial_val, font=ctk.CTkFont(family="JetBrains Mono", size=16, weight="bold"), text_color=color)
        lbl.pack(pady=(2, 0))
        return lbl

    # =========================================================================
    # TAB 2: WALLET & PAYOUTS
    # =========================================================================
    def _build_wallet_tab(self):
        self.tab_wallet.grid_columnconfigure(0, weight=1)

        # Wallet Address Card
        card_addr = ctk.CTkFrame(self.tab_wallet, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_addr.pack(fill="x", pady=(0, 20), ipady=10)

        ctk.CTkLabel(card_addr, text="YOUR MINING PAYOUT ADDRESS", font=ctk.CTkFont(size=12, weight="bold"), text_color="#94a3b8").pack(padx=20, pady=(16, 6), anchor="w")
        self.entry_wallet_addr = ctk.CTkEntry(
            card_addr, height=44, font=ctk.CTkFont(family="JetBrains Mono", size=13),
            fg_color="#090d16", border_color="#1e293b"
        )
        self.entry_wallet_addr.insert(0, self.wallet.address)
        self.entry_wallet_addr.configure(state="readonly")
        self.entry_wallet_addr.pack(fill="x", padx=20, pady=(0, 12))

        btn_copy = ctk.CTkButton(
            card_addr, text="📋  Copy Address", height=36, width=160,
            fg_color="#1e293b", hover_color="#334155", font=ctk.CTkFont(size=12, weight="bold"),
            command=self._copy_address
        )
        btn_copy.pack(padx=20, pady=(0, 16), anchor="w")

        # Transfer Coins Form
        card_send = ctk.CTkFrame(self.tab_wallet, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_send.pack(fill="x", pady=(0, 20), ipady=10)

        ctk.CTkLabel(card_send, text="SEND UR COIN (URC)", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f8fafc").pack(padx=20, pady=(16, 12), anchor="w")

        ctk.CTkLabel(card_send, text="Recipient Address (urc1...)", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(padx=20, anchor="w")
        self.entry_send_to = ctk.CTkEntry(card_send, height=40, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b", placeholder_text="urc1...")
        self.entry_send_to.pack(fill="x", padx=20, pady=(4, 12))

        ctk.CTkLabel(card_send, text="Amount in URC", font=ctk.CTkFont(size=12), text_color="#94a3b8").pack(padx=20, anchor="w")
        self.entry_send_amount = ctk.CTkEntry(card_send, height=40, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b", placeholder_text="e.g. 50.0")
        self.entry_send_amount.pack(fill="x", padx=20, pady=(4, 16))

        btn_send = ctk.CTkButton(
            card_send, text="🚀  SEND TRANSACTION NOW", height=44,
            fg_color="#06b6d4", hover_color="#0284c7", font=ctk.CTkFont(size=14, weight="bold"),
            command=self._send_transaction
        )
        btn_send.pack(fill="x", padx=20, pady=(0, 16))

    # =========================================================================
    # TAB 3: SETTINGS & MODE
    # =========================================================================
    def _build_settings_tab(self):
        self.tab_settings.grid_columnconfigure(0, weight=1)

        card_settings = ctk.CTkFrame(self.tab_settings, fg_color="#111827", corner_radius=16, border_width=1, border_color="#1e293b")
        card_settings.pack(fill="both", expand=True, ipady=10)

        ctk.CTkLabel(card_settings, text="MINING INTENSITY PROFILE", font=ctk.CTkFont(size=15, weight="bold"), text_color="#f8fafc").pack(padx=20, pady=(20, 12), anchor="w")

        self.intensity_mode = ctk.StringVar(value="balanced")

        profiles = [
            ("⚡ Light Mode (0.5 GB VRAM) - Low power, perfect while gaming or browsing", "light"),
            ("🚀 Balanced Mode (1.0 GB VRAM) - Recommended optimal speed & desktop comfort", "balanced"),
            ("🔥 Maximum Power (1.5 GB VRAM) - Maximum hash output for overnight / AFK", "maximum")
        ]

        for text, mode in profiles:
            rb = ctk.CTkRadioButton(
                card_settings, text=text, variable=self.intensity_mode, value=mode,
                font=ctk.CTkFont(size=13), text_color="#f8fafc", fg_color="#f59e0b"
            )
            rb.pack(padx=24, pady=8, anchor="w")

        ctk.CTkLabel(card_settings, text="NODE RPC URL", font=ctk.CTkFont(size=13, weight="bold"), text_color="#94a3b8").pack(padx=20, pady=(24, 6), anchor="w")
        self.entry_node_url = ctk.CTkEntry(card_settings, height=40, font=ctk.CTkFont(family="JetBrains Mono", size=12), fg_color="#090d16", border_color="#1e293b")
        self.entry_node_url.insert(0, self.node_url)
        self.entry_node_url.pack(fill="x", padx=20, pady=(0, 20))

    # =========================================================================
    # ACTIONS & LOGIC
    # =========================================================================
    def _select_tab(self, tab_name: str):
        self.tab_dashboard.grid_forget()
        self.tab_wallet.grid_forget()
        self.tab_settings.grid_forget()

        self.btn_nav_dash.configure(fg_color="#1e293b" if tab_name == "dashboard" else "transparent", text_color="#f8fafc" if tab_name == "dashboard" else "#94a3b8")
        self.btn_nav_wallet.configure(fg_color="#1e293b" if tab_name == "wallet" else "transparent", text_color="#f8fafc" if tab_name == "wallet" else "#94a3b8")
        self.btn_nav_settings.configure(fg_color="#1e293b" if tab_name == "settings" else "transparent", text_color="#f8fafc" if tab_name == "settings" else "#94a3b8")

        if tab_name == "dashboard":
            self.tab_dashboard.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "wallet":
            self.tab_wallet.grid(row=0, column=0, sticky="nsew")
        elif tab_name == "settings":
            self.tab_settings.grid(row=0, column=0, sticky="nsew")

    def _log(self, msg: str):
        timestamp = time.strftime("%H:%M:%S")
        line = f"[{timestamp}] {msg}\n"
        self.log_box.insert("end", line)
        self.log_box.see("end")

    def _toggle_mining(self):
        if not self.is_mining:
            self._start_mining()
        else:
            self._stop_mining()

    def _start_mining(self):
        self.is_mining = True
        self.btn_mine.configure(text="⏹   STOP MINING", fg_color="#ef4444", hover_color="#dc2626")
        self.lbl_status.configure(text="● MINING ACTIVE", text_color="#10b981")
        self._log("Starting GPU OpenCL mining engine...")

        # Determine intensity items
        mode = self.intensity_mode.get()
        if mode == "light":
            dag_items = DEFAULT_DAG_ITEMS // 2
        elif mode == "maximum":
            dag_items = int(DEFAULT_DAG_ITEMS * 1.5)
        else:
            dag_items = DEFAULT_DAG_ITEMS

        self.mining_thread = threading.Thread(target=self._mining_loop, args=(dag_items,), daemon=True)
        self.mining_thread.start()

    def _rpc_call(self, endpoint: str, data: dict = None, timeout: int = 5) -> dict:
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

    def _stop_mining(self):
        self.is_mining = False
        self.btn_mine.configure(text="▶   START MINING", fg_color="#10b981", hover_color="#059669")
        self.lbl_status.configure(text="IDLE - MINER STOPPED", text_color="#94a3b8")
        self.lbl_hashrate_val.configure(text="0.00")
        self._log("Mining stopped.")

    def _mining_loop(self, dag_items: int):
        try:
            # Check selected intensity profile
            intensity = getattr(self, "intensity", "Balanced")
            if intensity == "Light":
                batch_threads = 4096
                npt = 4
                is_light = True
            elif intensity == "Maximum":
                batch_threads = 65536
                npt = 16
                is_light = False
            else:
                batch_threads = 16384
                npt = 8
                is_light = None # Auto-detect based on VRAM

            if not self.gpu_miner:
                self.gpu_miner = GPUMiner(device_index=self.selected_device_idx, dag_items=dag_items, light_mode=is_light)

            nonce_seq = 0
            while self.is_mining:
                # 1. Fetch info from node
                info = self._rpc_call("/api/info", timeout=5)

                height = info["height"] + 1
                best_hash = info["best_hash"]
                target_int = int(info["target"], 16)
                reward = info["current_reward"]
                epoch = height // 10_000

                # Prepare candidate block
                coinbase_tx = Transaction.create_coinbase(self.wallet.address, reward, height)
                header = BlockHeader(
                    version=1, prev_hash=best_hash, merkle_root=coinbase_tx.txid,
                    timestamp=int(time.time()), target=target_int, nonce=0,
                    height=height, epoch=epoch
                )
                candidate = Block(header, [coinbase_tx])
                mining_hash = candidate.header.get_mining_hash()

                # Search batch
                t0 = time.perf_counter()
                results = self.gpu_miner.search_batch(
                    mining_hash, target_int, epoch,
                    start_nonce=nonce_seq,
                    global_work_size=batch_threads,
                    nonces_per_thread=npt
                )
                dt = time.perf_counter() - t0
                nonce_seq += (batch_threads * npt)

                # Update speed
                if dt > 0:
                    speed_mhs = ((batch_threads * npt) / dt) / 1_000_000
                    self.current_hashrate = speed_mhs
                    self.after(0, lambda s=speed_mhs: self.lbl_hashrate_val.configure(text=f"{s:.2f}"))

                # Found block
                if results:
                    winning_nonce, block_hash = results[0]
                    candidate.header.nonce = winning_nonce
                    candidate.hash = block_hash

                    # Submit to node
                    s_res = self._rpc_call("/api/submit_block", data=candidate.to_dict(), timeout=5)

                    if s_res.get("success"):
                        self.blocks_found += 1
                        earned = self.blocks_found * (reward / COIN)
                        self.after(0, lambda bf=self.blocks_found, e=earned: (
                            self.lbl_blocks_val.configure(text=str(bf)),
                            self.lbl_earned_val.configure(text=f"Earned: {e:.0f} URC")
                        ))
                        self._log(f"🎉 BLOCK #{height} FOUND! Hash: {block_hash[:18]}... Nonce: {winning_nonce}")
                        nonce_seq = 0

        except Exception as e:
            self._log(f"Miner error: {e}")
            time.sleep(2)

    def _telemetry_worker(self):
        """Query GPU temperature and node balance every 2 seconds."""
        while self.running:
            # 1. Hardware stats via nvidia-smi
            try:
                out = subprocess.check_output(
                    ["nvidia-smi", "--query-gpu=temperature.gpu,power.draw,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    text=True
                )
                parts = [p.strip() for p in out.strip().split(",")]
                if len(parts) >= 5:
                    temp_c, power_w, load_pct, mem_used, mem_tot = parts
                    self.after(0, lambda t=temp_c, p=power_w, l=load_pct, mu=mem_used, mt=mem_tot: (
                        self.telemetry_temp.configure(text=f"{t} °C", text_color="#ef4444" if int(t) > 75 else "#10b981"),
                        self.telemetry_power.configure(text=f"{float(p):.0f} W"),
                        self.telemetry_load.configure(text=f"{l} %"),
                        self.telemetry_vram.configure(text=f"{float(mu)/1024:.1f} / {float(mt)/1024:.1f} GB")
                    ))
            except Exception:
                pass

            # 2. Query node status & wallet balance
            try:
                wdata = self._rpc_call("/api/wallet", timeout=2)
                bal = wdata["balance"] / COIN
                self.after(0, lambda b=bal: self.lbl_balance_val.configure(text=f"{b:.2f}"))

                idata = self._rpc_call("/api/info", timeout=2)
                h = idata["height"]
                self.after(0, lambda h=h: (
                    self.lbl_node_indicator.configure(text="● NODE CONNECTED", text_color="#10b981"),
                    self.lbl_node_height.configure(text=f"Height: #{h}")
                ))
            except Exception:
                self.after(0, lambda: (
                    self.lbl_node_indicator.configure(text="○ NODE OFFLINE", text_color="#ef4444"),
                    self.lbl_node_height.configure(text="Waiting for Node...")
                ))

            time.sleep(2)

    def _copy_address(self):
        self.clipboard_clear()
        self.clipboard_append(self.wallet.address)
        self._log("Wallet address copied to clipboard.")

    def _send_transaction(self):
        recipient = self.entry_send_to.get().strip()
        amount_str = self.entry_send_amount.get().strip()
        if not recipient or not amount_str:
            self._log("Error: Recipient and amount cannot be empty.")
            return

        try:
            amount = float(amount_str)
            res = self._rpc_call("/api/send_tx", data={"recipient": recipient, "amount_urc": amount}, timeout=5)

            if res.get("success"):
                self._log(f"✓ Sent {amount} URC! TXID: {res['txid']}")
                self.entry_send_to.delete(0, "end")
                self.entry_send_amount.delete(0, "end")
            else:
                self._log(f"Send failed: {res.get('error')}")
        except Exception as e:
            self._log(f"Send error: {e}")

if __name__ == "__main__":
    app = UrMinerApp()
    app.mainloop()
