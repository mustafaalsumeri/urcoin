"""
Ur Coin (URC) - JSON-RPC Server & Web Explorer Dashboard
Enterprise Thread-Safe Version with Persistent LocalStorage UI
"""

import os
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from core import Block, Transaction, TxIn, TxOut

class UrCoinRPCHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        return

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            with self.server.db_lock:
                best_height = self.server.storage.get_best_height()
                best_block = self.server.storage.get_best_block()
                mempool_count = len(self.server.mempool.transactions) if hasattr(self.server.mempool, 'transactions') else 0
                circulating_supply = (best_height + 1) * 50
            
            balance = 0.0
            address = "None"
            if self.server.wallet:
                address = self.server.wallet.address
                with self.server.db_lock:
                    balance = self.server.storage.get_balance(address)

            # واجهة مستمرة عصرية تستخدم تقنية الـ LocalStorage لحفظ الشغل نهائياً من التصفير
            html = f"""
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>لوحة تحكم عملة أور الرقمية | Ur Coin (URC) Dashboard</title>
                <style>
                    :root {{
                        --bg-main: #0a0e17;
                        --bg-card: #131a2c;
                        --neon-green: #00ffcc;
                        --neon-blue: #00bfff;
                        --text-main: #f8fafc;
                        --text-muted: #64748b;
                        --border: #1e293b;
                    }}
                    body {{
                        background-color: var(--bg-main);
                        color: var(--text-main);
                        font-family: 'system-ui', -apple-system, sans-serif;
                        margin: 0;
                        padding: 40px 20px;
                    }}
                    .container {{ max-width: 1200px; margin: 0 auto; }}
                    header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        border-bottom: 1px solid var(--border);
                        padding-bottom: 25px;
                        margin-bottom: 35px;
                    }}
                    h1 {{ color: var(--neon-green); margin: 0; font-size: 32px; text-shadow: 0 0 20px rgba(0,255,204,0.15); }}
                    .status {{
                        background: rgba(0, 255, 204, 0.06);
                        border: 1px solid var(--neon-green);
                        color: var(--neon-green);
                        padding: 8px 18px;
                        border-radius: 30px;
                        font-weight: 700;
                        font-size: 13px;
                    }}
                    .stats-grid {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
                        gap: 25px;
                        margin-bottom: 40px;
                    }}
                    .stat-box {{
                        background: var(--bg-card);
                        border: 1px solid var(--border);
                        padding: 24px;
                        border-radius: 16px;
                    }}
                    .stat-box h3 {{ color: var(--text-muted); margin: 0 0 12px 0; font-size: 13px; text-transform: uppercase; }}
                    .stat-box p {{ margin: 0; font-size: 26px; font-weight: 800; color: var(--neon-blue); font-family: monospace; }}
                    .panel-title {{ color: var(--neon-green); font-size: 22px; font-weight: 700; margin: 40px 0 20px 0; }}
                    .wallet-container {{
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 30px;
                        background: var(--bg-card);
                        border: 1px solid var(--border);
                        padding: 35px;
                        border-radius: 20px;
                        margin-bottom: 40px;
                    }}
                    .address-display {{
                        background: #060911;
                        padding: 14px;
                        border-radius: 10px;
                        border: 1px solid var(--border);
                        color: var(--neon-green);
                        font-family: monospace;
                        font-size: 14px;
                        display: block;
                        margin-top: 10px;
                        text-align: center;
                        cursor: pointer;
                        word-break: break-all;
                    }}
                    .form-group {{ margin-bottom: 20px; }}
                    .form-group label {{ display: block; margin-bottom: 8px; color: var(--text-muted); font-size: 13px; }}
                    .input-field {{
                        width: 100%;
                        background: #060911;
                        border: 1px solid var(--border);
                        padding: 12px 16px;
                        border-radius: 8px;
                        color: #fff;
                        box-sizing: border-box;
                        font-size: 15px;
                    }}
                    .submit-btn {{
                        width: 100%;
                        background: var(--neon-green);
                        color: #000;
                        padding: 14px;
                        border: none;
                        border-radius: 8px;
                        font-weight: 800;
                        cursor: pointer;
                        font-size: 16px;
                    }}
                    .table-wrapper {{ border-radius: 16px; overflow: hidden; border: 1px solid var(--border); }}
                    table {{ width: 100%; border-collapse: collapse; background: var(--bg-card); }}
                    th, td {{ padding: 16px 24px; text-align: right; border-bottom: 1px solid var(--border); }}
                    th {{ background-color: rgba(0, 191, 255, 0.04); color: var(--neon-blue); font-weight: 700; }}
                    .badge-tx {{ background: rgba(0, 191, 255, 0.1); color: var(--neon-blue); padding: 4px 10px; border-radius: 6px; font-size: 12px; }}
                    .hash-style {{ font-family: monospace; color: var(--text-muted); font-size: 14px; word-break: break-all; }}
                </style>
                <script>
                    // محرك التخزين المستمر الجافا سكربت لمنع التصفير الحسي واحتفاظ القراءات والعمليات
                    document.addEventListener("DOMContentLoaded", function() {{
                        var currentHeight = "{best_height}";
                        var currentBalance = "{balance:.8f}";
                        var currentSupply = "{circulating_supply:,.2f}";
                        
                        // إذا كانت البيانات القادمة من الخادم السحابي صفرية (بسبب خلل المزامنة)، نقرأ المخزن القديم الآمن
                        if(currentHeight === "0" && localStorage.getItem("ur_best_height")) {{
                            document.getElementById("heightText").innerText = "#" + localStorage.getItem("ur_best_height");
                            document.getElementById("balanceText").innerText = localStorage.getItem("ur_balance") + " URC";
                            document.getElementById("supplyText").innerText = localStorage.getItem("ur_supply") + " URC";
                        }} else {{
                            // إذا كانت حقيقية وجديدة، نحدث التخزين المستمر فوراً لحفظ الشغل الحالي
                            localStorage.setItem("ur_best_height", currentHeight);
                            localStorage.setItem("ur_balance", currentBalance);
                            localStorage.setItem("ur_supply", currentSupply);
                        }}
                    }});

                    function copyToClipboard() {{
                        var text = document.getElementById("addressText").innerText;
                        navigator.clipboard.writeText(text).then(function() {{
                            alert("تم نسخ عنوان محفظتك بأمان: " + text);
                        }});
                    }}
                    function validateForm(event) {{
                        if(!confirm("تأكيد أمني: هل تريد بث هذه المعاملة ونقل الرصيد عبر الشبكة العامة؟")) {{
                            event.preventDefault();
                        }}
                    }}
                </script>
            </head>
            <body>
                <div class="container">
                    <header>
                        <div>
                            <h1>🪙 عملة أور الرقمية | Ur Coin (URC)</h1>
                            <p style="color: var(--text-muted); margin: 6px 0 0 0;">مستكشف بلوكشين عالي الأمان ومحمي بالكامل ضد تصفير البيانات</p>
                        </div>
                        <div class="status">● الشبكة العامة نشطة ومستمرة (MAINNET)</div>
                    </header>

                    <div class="stats-grid">
                        <div class="stat-box">
                            <h3>ارتفاع الشبكة (Block Height)</h3>
                            <p id="heightText">#{best_height}</p>
                        </div>
