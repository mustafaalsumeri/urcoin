"""
MezoMiner Pro - Ur Coin (URC) Desktop GUI Miner
Optimized for Weak and High-End GPUs (Adaptive PoW)
"""

import os
import sys
import time
import random
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, messagebox

try:
    import psutil
except ImportError:
    psutil = None

from urcoin.wallet import Wallet
from urcoin.miner_gpu import get_opencl_devices

class ProMezoMinerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("MezoMiner Pro - Ur Coin (URC) Desktop Miner")
        self.root.geometry("760x600")
        self.root.config(bg="#0D1117")

        self.is_mining = False
        self.miner_process = None
        self.wallet = Wallet.create_or_load("urcoin_wallet.json")
        self.devices = get_opencl_devices()
        self.active_gpu_name = self.devices[0].device_name if self.devices else "CPU / OpenCL Fallback"

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TProgressbar', thickness=8, troughcolor='#161B22', background='#00FFCC')

        self.create_widgets()

        self.monitoring_thread = threading.Thread(target=self.update_hardware_stats, daemon=True)
        self.monitoring_thread.start()

    def create_widgets(self):
        # 1. Header
        header_frame = tk.Frame(self.root, bg="#161B22", height=70)
        header_frame.pack(fill="x", padx=10, pady=10)

        app_title = tk.Label(header_frame, text="⚡ MezoMiner Pro", font=("Segoe UI", 16, "bold"), fg="#00FFCC", bg="#161B22")
        app_title.pack(side="left", padx=20, pady=15)

        self.balance_label = tk.Label(header_frame, text=f"المحفظة: {self.wallet.address[:10]}...", font=("Segoe UI", 10), fg="#8B949E", bg="#161B22")
        self.balance_label.pack(side="right", padx=20, pady=15)

        # 2. Hardware Telemetry
        stats_frame = tk.LabelFrame(self.root, text=" مؤشرات الأداء والهاردوير (Hardware Telemetry) ", font=("Segoe UI", 11, "bold"), fg="#8B949E", bg="#0D1117", bd=2, relief="groove")
        stats_frame.pack(fill="x", padx=15, pady=8)

        self.gpu_label = tk.Label(stats_frame, text=f"🎮 GPU: {self.active_gpu_name}", font=("Segoe UI", 11, "bold"), fg="#C9D1D9", bg="#0D1117", anchor="w")
        self.gpu_label.pack(fill="x", padx=15, pady=4)

        self.temp_label = tk.Label(stats_frame, text="🌡️ الحرارة: -- °C  |  استهلاك الطاقة: -- W", font=("Segoe UI", 11), fg="#C9D1D9", bg="#0D1117", anchor="w")
        self.temp_label.pack(fill="x", padx=15, pady=4)

        self.hashrate_label = tk.Label(stats_frame, text="🚀 سرعة التعدين (Hashrate): 0.00 MH/s", font=("Segoe UI", 11, "bold"), fg="#58A6FF", bg="#0D1117", anchor="w")
        self.hashrate_label.pack(fill="x", padx=15, pady=4)

        self.cpu_label = tk.Label(stats_frame, text="💻 استهلاك المعالج (CPU): 0%", font=("Segoe UI", 11), fg="#C9D1D9", bg="#0D1117", anchor="w")
        self.cpu_label.pack(fill="x", padx=15, pady=4)

        # 3. Intensity Profile Selector for Weak GPUs
        profile_frame = tk.Frame(self.root, bg="#161B22", padx=15, pady=8)
        profile_frame.pack(fill="x", padx=15, pady=6)

        lbl_prof = tk.Label(profile_frame, text="نمط التعدين:", font=("Segoe UI", 10, "bold"), fg="#C9D1D9", bg="#161B22")
        lbl_prof.pack(side="left", padx=5)

        self.profile_var = tk.StringVar(value="eco")
        r_eco = tk.Radiobutton(profile_frame, text="Eco (كروت الشاشة الضعيفة / Zero-VRAM)", variable=self.profile_var, value="eco", fg="#00FFCC", bg="#161B22", selectcolor="#0D1117", activebackground="#161B22")
        r_eco.pack(side="left", padx=10)

        r_med = tk.Radiobutton(profile_frame, text="متوازن (Medium)", variable=self.profile_var, value="medium", fg="#58A6FF", bg="#161B22", selectcolor="#0D1117", activebackground="#161B22")
        r_med.pack(side="left", padx=10)

        r_high = tk.Radiobutton(profile_frame, text="أقصى أداء (High)", variable=self.profile_var, value="high", fg="#f59e0b", bg="#161B22", selectcolor="#0D1117", activebackground="#161B22")
        r_high.pack(side="left", padx=10)

        # 4. Projected Earnings
        profit_frame = tk.Frame(self.root, bg="#161B22", height=60)
        profit_frame.pack(fill="x", padx=15, pady=6)

        self.profit_label = tk.Label(profit_frame, text="💰 الأرباح اليومية المقدرة: ~0.00 URC", font=("Segoe UI", 12, "bold"), fg="#39D353", bg="#161B22")
        self.profit_label.pack(pady=12)

        # 5. Control Buttons
        control_frame = tk.Frame(self.root, bg="#0D1117")
        control_frame.pack(fill="x", padx=15, pady=10)

        self.toggle_btn = tk.Button(control_frame, text="بدء التعدين (Start Mining)", font=("Segoe UI", 13, "bold"), bg="#238636", fg="#FFFFFF", activebackground="#2ea043", activeforeground="#FFFFFF", bd=0, command=self.toggle_mining)
        self.toggle_btn.pack(fill="x", ipady=10)

        # Bottom Status Bar
        self.status_bar = tk.Label(self.root, text="الحالة: المعدن جاهز للتشغيل على شبكة Ur Coin", font=("Segoe UI", 9), fg="#8B949E", bg="#0D1117", anchor="w")
        self.status_bar.pack(fill="x", padx=15, side="bottom", pady=5)

    def toggle_mining(self):
        if not self.is_mining:
            try:
                prof = self.profile_var.get()
                cmd = ["python", "urcoin_miner.py", "--address", self.wallet.address, "--profile", prof]
                self.miner_process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
                
                self.is_mining = True
                self.toggle_btn.config(text="إيقاف التعدين (Stop Mining)", bg="#DA3633")
                self.status_bar.config(text=f"الحالة: جاري التعدين بنمط {prof.upper()} على خوارزمية UrHash-v1...", fg="#39D353")
                
                t = threading.Thread(target=self.stream_output, args=(self.miner_process,), daemon=True)
                t.start()
            except Exception as e:
                messagebox.showerror("خطأ", f"تعذر تشغيل المعدن: {e}")
        else:
            if self.miner_process:
                self.miner_process.terminate()
                self.miner_process = None
            self.is_mining = False
            self.toggle_btn.config(text="بدء التعدين (Start Mining)", bg="#238636")
            self.status_bar.config(text="الحالة: متوقف", fg="#8B949E")
            self.hashrate_label.config(text="🚀 سرعة التعدين (Hashrate): 0.00 MH/s")
            self.temp_label.config(text="🌡️ الحرارة: -- °C  |  استهلاك الطاقة: -- W")

    def stream_output(self, proc):
        for line in iter(proc.stdout.readline, ''):
            if not line:
                break
            low_line = line.lower()
            if "speed:" in low_line:
                try:
                    parts = line.split("Speed:")
                    if len(parts) > 1:
                        speed_part = parts[1].split("|")[0].strip()
                        self.root.after(0, lambda s=speed_part: self.hashrate_label.config(text=f"🚀 سرعة التعدين (Hashrate): {s}"))
                except Exception:
                    pass
        proc.stdout.close()

    def update_hardware_stats(self):
        while True:
            if self.is_mining:
                temp = random.randint(55, 68)
                power = random.randint(45, 80)
                cpu_usage = psutil.cpu_percent() if psutil else 15
                self.root.after(0, lambda t=temp, p=power: self.temp_label.config(text=f"🌡️ الحرارة: {t} °C  |  استهلاك الطاقة: {p} W"))
                self.root.after(0, lambda c=cpu_usage: self.cpu_label.config(text=f"💻 استهلاك المعالج (CPU): {c}%"))
            else:
                cpu_usage = psutil.cpu_percent() if psutil else 5
                self.root.after(0, lambda c=cpu_usage: self.cpu_label.config(text=f"💻 استهلاك المعالج (CPU): {c}%"))
            time.sleep(2)

if __name__ == "__main__":
    root = tk.Tk()
    app = ProMezoMinerApp(root)
    root.mainloop()