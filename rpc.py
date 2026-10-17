"""
Ur Coin (URC) - Secure Web Hot Wallet & Explorer Daemon
Enterprise Thread-Safe Cloud Engine [2026 Update]
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

        # 1. بوابة محفظة الإنترنت الساخنة ومستكشف الشبكة المباشر
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

            html = f"""
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Ur Coin (URC) - محفظة الإنترنت الساخنة الرسمية</title>
                <style>
                    :root {{
                        --bg-main: #060913;
                        --bg-card: #0f1626;
                        --neon-gold: #f59e0b;
                        --neon-blue: #3b82f6;
                        --text-main: #f8fafc;
                        --text-muted: #64748b;
                        --border: #1e293b;
                    }}
                    body {{
                        background-color: var(--bg-main);
                        color: var(--text-main);
                        font-family: 'system-ui', -apple-system, sans-serif;
                        margin: 0;
                        padding: 30px 15px;
                    }}
                    .container {{ max-width: 1000px; margin: 0 auto; }}
                    header {{
                        background: var(--bg-card);
                        padding: 25px;
                        border-radius: 20px;
                        border: 1px solid var(--border);
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        margin-bottom: 30px;
                    }}
                    h1 {{ color: var(--neon-gold); margin: 0; font-size: 26px; text-shadow: 0 0 15px rgba(245,158,11,0.2); }}
                    .hot-badge {{
                        background: rgba(245, 158, 11, 0.08);
                        border: 1px solid var(--neon-gold);
                        color: var(--neon-gold);
                        padding: 6px 14px;
                        border-radius: 30px;
                        font-weight: 700;
                        font-size: 12px;
                    }}
                    .wallet-grid {{
                        display: grid;
                        grid-template-columns: 1fr 1fr;
                        gap: 25px;
                        margin-bottom: 30px;
                    }}
                    @media (max-width: 768px) {{ .wallet-grid {{ grid-template-columns: 1fr; }} }}
                    .wallet-card {{
                        background: var(--bg-card);
                        border: 1px solid var(--border);
                        padding: 30px;
                        border-radius: 20px;
                        box-shadow: 0 10px 25px rgba(0,0,0,0.3);
                    }}
                    .address-box {{
                        background: #020617;
                        padding: 14px;
                        border-radius: 10px;
                        border: 1px solid var(--border);
                        color: var(--neon-gold);
                        font-family: monospace;
                        font-size: 13px;
                        text-align: center;
                        cursor: pointer;
                        word-break: break-all;
                        margin-top: 15px;
                    }}
                    .form-group {{ margin-bottom: 20px; }}
                    .form-group label {{ display: block; margin-bottom: 8px; color: var(--text-muted); font-size: 13px; }}
                    .input-field {{
                        width: 100%;
                        background: #020617;
                        border: 1px solid var(--border);
                        padding: 12px 16px;
                        border-radius: 8px;
                        color: #fff;
                        box-sizing: border-box;
                    }}
                    .btn-action {{
                        width: 100%;
                        background: var(--neon-gold);
                        color: #000;
                        padding: 14px;
                        border: none;
                        border-radius: 8px;
                        font-weight: 800;
                        cursor: pointer;
                        font-size: 16px;
                    }}
                    .btn-action:hover {{ opacity: 0.9; box-shadow: 0 0 20px rgba(245,158,11,0.3); }}
                    
                    table {{ width: 100%; border-collapse: collapse; background: var(--bg-card); border-radius: 16px; overflow: hidden; border: 1px solid var(--border); }}
                    th, td {{ padding: 14px 20px; text-align: right; border-bottom: 1px solid var(--border); }}
                    th {{ background-color: rgba(245, 158, 11, 0.03); color: var(--neon-gold); font-size: 13px; }}
                    .hash-style {{ font-family: monospace; color: var(--text-muted); font-size: 13px; word-break: break-all; }}
                </style>
                <script>
                    function copyAddress() {{
                        var text = document.getElementById("walletAddr").innerText;
                        navigator.clipboard.writeText(text).then(function() {{
                            alert("تم نسخ عنوان محفظتك الساخنة بنجاح: " + text);
                        }});
                    }}
                    function verifyTx(e) {{
                        if(!confirm("تأكيد أمني من محفظة أور الحية: هل تريد بث هذه العملية المالية عبر الإنترنت؟")) {{
                            e.preventDefault();
                        }}
                    }}
                </script>
            </head>
            <body>
                <div class="container">
                    <header>
                        <div>
                            <h1>🔥 محفظة أور الساخنة | Ur Coin (URC) Hot Wallet</h1>
                            <p style="color: var(--text-muted); margin: 5px 0 0 0;">إدارة الحوالات الفورية ومراقبة البلوكشين مباشرة عبر الإنترنت</p>
                        </div>
                        <div class="hot-badge">● محفظة حية متصلة بالإنترنت (ONLINE)</div>
                    </header>

                    <div class="wallet-grid">
                        <div class="wallet-card">
                            <h4 style="margin: 0; color: var(--text-muted);">الرصيد الحي الإجمالي المتاح:</h4>
                            <div style="font-size: 42px; font-weight: 900; color: var(--neon-gold); margin: 15px 0;">{balance:,.8f} <span style="font-size: 18px; color:#fff; font-weight:400;">URC</span></div>
                            <h4 style="margin: 25px 0 5px 0; color: var(--text-muted);">عنوان الاستلام الفوري الخاص بك (انقر للنسخ):</h4>
                            <div id="walletAddr" class="address-box" onclick="copyAddress()">{address}</div>
                        </div>

                        <div class="wallet-card">
                            <h4 style="margin: 0 0 20px 0; color: var(--neon-gold); font-weight: 700;">⚡ تحويل مستعجل عبر الإنترنت</h4>
                            <form action="/action/send" method="POST" onsubmit="verifyTx(event)">
                                <div class="form-group">
                                    <label>إلى عنوان المحفظة المستلمة:</label>
                                    <input type="text" name="recipient" class="input-field" placeholder="urc1..." required>
                                    <input type="hidden" name="web_source" value="true">
                                </div>
                                <div class="form-group">
                                    <label>الكمية المراد بثها (URC):</label>
                                    <input type="number" step="0.00000001" name="amount" class="input-field" placeholder="0.00" required>
                                </div>
                                <button type="submit" class="btn-action">توقيع وبث الحوالة الحية 🚀</button>
                            </form>
                        </div>
                    </div>

                    <h3 style="color: var(--neon-blue); margin: 40px 0 15px 0;">⛓️ مستكشف المعاملات والكتل الحية (Live Explorer)</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>الكتلة</th>
                                <th>هاش معرف الكتلة (Block Hash)</th>
                                <th>المعاملات</th>
                                <th>الـ Nonce الحسابي</th>
                                <th>توقيت البث والمزامنة</th>
                            </tr>
                        </thead>
