"""
Ur Coin (URC) - JSON-RPC Server & Web Explorer Dashboard
Professional Thread-Safe Version with Advanced Cyberpunk UI
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
        # تعطيل طباعة طلبات الويب للحفاظ على نظافة الـ Terminal
        return

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # 1. مستكشف البلوكشين الرئيسي المطور (Professional Web Explorer Dashboard)
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            # استعلام آمن ومحمي باستخدام القفل البرمجي للشبكة
            with self.server.db_lock:
                best_height = self.server.storage.get_best_height()
                best_block = self.server.storage.get_best_block()
                mempool_count = len(self.server.mempool.transactions) if hasattr(self.server.mempool, 'transactions') else 0
                circulating_supply = (best_height + 1) * 50  # مكافأة الـ 50 URC لكل كتلة
            
            balance = 0.0
            address = "None"
            if self.server.wallet:
                address = self.server.wallet.address
                with self.server.db_lock:
                    balance = self.server.storage.get_balance(address)

            # بناء الواجهة الهندسية المحدثة بالكامل المتوافقة مع أداء الـ RTX 3050
            html = f"""
            <!DOCTYPE html>
            <html lang="ar" dir="rtl">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Ur Coin (URC) - لوحة التحكم الاحترافية</title>
                <style>
                    :root {{
                        --bg-main: #0b0f19;
                        --bg-card: #151d30;
                        --neon-green: #00ffcc;
                        --neon-blue: #00bfff;
                        --text-main: #f1f5f9;
                        --text-muted: #94a3b8;
                        --border-color: #243454;
                    }}
                    body {{
                        background-color: var(--bg-main);
                        color: var(--text-main);
                        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                        margin: 0;
                        padding: 30px;
                    }}
                    .container {{ max-width: 1200px; margin: 0 auto; }}
                    header {{
                        display: flex;
                        justify-content: space-between;
                        align-items: center;
                        border-bottom: 2px solid var(--border-color);
                        padding-bottom: 20px;
                        margin-bottom: 30px;
                    }}
                    h1 {{ color: var(--neon-green); margin: 0; font-size: 28px; text-shadow: 0 0 10px rgba(0,255,204,0.2); }}
                    .status-badge {{
                        background: rgba(0, 255, 204, 0.1);
                        border: 1px solid var(--neon-green);
                        color: var(--neon-green);
                        padding: 6px 16px;
                        border-radius: 20px;
                        font-weight: bold;
                        font-size: 14px;
                    }}
                    .grid-stats {{
                        display: grid;
                        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                        gap: 20px;
                        margin-bottom: 30px;
                    }}
                    .stat-card {{
                        background: var(--bg-card);
                        border: 1px solid var(--border-color);
                        padding: 20px;
                        border-radius: 12px;
                        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
                    }}
                    .stat-card h3 {{ color: var(--text-muted); margin: 0 0 10px 0; font-size: 14px; text-transform: uppercase; }}
                    .stat-card p {{ margin: 0; font-size: 22px; font-weight: bold; color: var(--neon-blue); }}
                    
                    .section-title {{ color: var(--neon-green); font-size: 20px; margin: 30px 0 15px 0; display: flex; align-items: center; gap: 10px; }}
                    
                    .wallet-box {{
                        background: linear-gradient(135deg, #151d30 0%, #1e2942 100%);
                        border: 1px solid var(--border-color);
                        padding: 25px;
                        border-radius: 16px;
                        display: flex;
                        justify-content: space-between;
                        flex-wrap: wrap;
                        gap: 20px;
                    }}
                    .wallet-info {{ flex: 1; min-width: 280px; }}
                    .address-bar {{
                        background: rgba(0,0,0,0.3);
                        padding: 12px;
                        border-radius: 8px;
                        border: 1px solid var(--border-color);
                        color: var(--neon-green);
                        font-family: monospace;
                        font-size: 15px;
                        display: block;
                        margin-top: 8px;
                        cursor: pointer;
                        text-align: center;
                    }}
                    .transfer-form {{
                        flex: 1;
                        min-width: 280px;
                        background: rgba(0,0,0,0.2);
                        padding: 20px;
                        border-radius: 12px;
                        border: 1px solid var(--border-color);
                    }}
                    .form-group {{ margin-bottom: 15px; }}
                    .form-group label {{ display: block; margin-bottom: 5px; color: var(--text-muted); font-size: 14px; }}
                    .form-control {{
                        width: 100%;
                        background: var(--bg-main);
                        border: 1px solid var(--border-color);
                        padding: 10px;
                        border-radius: 6px;
                        color: #fff;
                        box-sizing: border-box;
                    }}
                    .form-control:focus {{ border-color: var(--neon-blue); outline: none; }}
                    .btn-send {{
                        width: 100%;
                        background: var(--neon-green);
                        color: #000;
                        padding: 12px;
                        border: none;
                        border-radius: 6px;
                        font-weight: bold;
                        cursor: pointer;
                        font-size: 16px;
                        transition: all 0.2s;
                    }}
                    .btn-send:hover {{ background: #00cc66; box-shadow: 0 0 15px rgba(0,255,204,0.4); }}
                    
                    table {{
                        width: 100%;
                        border-collapse: collapse;
                        background: var(--bg-card);
                        border-radius: 12px;
                        overflow: hidden;
                        border: 1px solid var(--border-color);
                    }}
                    th, td {{ padding: 14px 20px; text-align: right; border-bottom: 1px solid var(--border-color); }}
                    th {{ background-color: rgba(0, 191, 255, 0.1); color: var(--neon-blue); font-weight: 600; }}
                    tr:hover {{ background-color: rgba(255,255,255,0.02); }}
                    .tx-count {{
                        background: rgba(0, 191, 255, 0.15);
                        color: var(--neon-blue);
                        padding: 2px 8px;
                        border-radius: 4px;
                        font-size: 13px;
                    }}
                    .hash-code {{ font-family: monospace; color: var(--text-muted); font-size: 14px; word-break: break-all; }}
                </style>
                <script>
                    function copyAddress() {{
                        var addressText = document.getElementById("walletAddress").innerText;
                        navigator.clipboard.writeText(addressText);
                        alert("تم نسخ عنوان محفظتك بنجاح: " + addressText);
                    }}
                    function confirmTransaction(e) {{
                        if(!confirm("هل أنت متأكد من رغبتك في بث هذه المعاملة المالية وإرسال العملات؟")) {{
                            e.preventDefault();
                        }}
                    }}
                </script>
            </head>
            <body>
                <div class="container">
                    <header>
                        <div>
                            <h1>🪙 لوحة تحكم عملة أور الرقمية | Ur Coin Explorer</h1>
                            <p style="color: var(--text-muted); margin: 5px 0 0 0;">شبكة بلوكشين مستقلة (Layer-1) مخصصة لكروت الشاشة متوسطة الذاكرة</p>
                        </div>
                        <div class="status-badge">● العقدة متصلة وحية (MAINNET)</div>
                    </header>

                    <div class="grid-stats">
                        <div class="stat-card">
                            <h3>ارتفاع البلوكشين (Height)</h3>
                            <p>#{best_height}</p>
                        </div>
                        <div class="stat-card">
                            <h3>المعروض المتداول (Supply)</h3>
