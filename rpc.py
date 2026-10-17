"""
Ur Coin (URC) - JSON-RPC Server & Web Explorer Dashboard
Secure Thread-Safe Version
"""

import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from core import Block, Transaction, TxIn, TxOut

class UrCoinRPCHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # تعطيل طباعة الطلبات الكثيرة في الـ Terminal للحفاظ على نظافة الشاشة
        return

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        # 1. مستكشف البلوكشين الرئيسي (Web Explorer)
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            # قراءة حية وآمنة لحالة الشبكة باستخدام القفل البرمجي
            with self.server.db_lock:
                best_height = self.server.storage.get_best_height()
                best_block = self.server.storage.get_best_block()
            
            balance = 0
            address = "None"
            if self.server.wallet:
                address = self.server.wallet.address
                with self.server.db_lock:
                    balance = self.server.storage.get_balance(address)

            html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Ur Coin (URC) Explorer</title>
                <style>
                    body {{ background-color: #121212; color: #ffffff; font-family: sans-serif; padding: 20px; }}
                    .card {{ background-color: #1e1e1e; padding: 20px; margin-bottom: 15px; border-radius: 8px; border: 1px solid #333; }}
                    h1 {{ color: #00ffcc; }}
                    .btn {{ background-color: #00ffcc; color: #000; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }}
                </style>
            </head>
            <body>
                <h1>🪙 لوحة تحكم عملة أور الرقمية | Ur Coin Dashboard</h1>
                <div class="card">
                    <h3>📊 حالة الشبكة العامة (Network Status)</h3>
                    <p><b>ارتفاع البلوكشين الحالي:</b> #{best_height}</p>
                    <p><b>هاش آخر كتلة:</b> {best_block.hash if best_block else 'None'}</p>
                </div>
                <div class="card">
                    <h3>👛 محفظة العقدة المحلية (Node Wallet)</h3>
                    <p><b>عنوان الاستقبال:</b> <code style="color:#00ffcc;">{address}</code></p>
                    <p><b>الرصيد الإجمالي:</b> {balance:.8f} URC</p>
                </div>
            </body>
            </html>
            """
            self.wfile.write(html.encode('utf-8'))
            return

        # 2. مستكشف الكتل البرمجي (API Blocks)
        elif path == "/api/blocks":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            
            with self.server.db_lock:
                height = self.server.storage.get_best_height()
                blocks_data = []
                # جلب آخر 10 كتل بأمان
                start = max(0, height - 10)
                for h in range(start, height + 1):
                    b = self.server.storage.get_block_by_height(h)
                    if b:
                        blocks_data.append({{"height": b.header.height, "hash": b.hash, "tx_count": len(b.transactions)}})
            
            self.wfile.write(json.dumps(blocks_data).encode('utf-8'))
            return

        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        # معالجة طلبات الـ JSON-RPC من سطر الأوامر والتعدين
        if self.path == "/rpc" or self.path == "/":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                req = json.loads(post_data.decode('utf-8'))
                method = req.get("method")
                params = req.get("params", [])
                
                result = None
                error = None

                # استخدام قفل الحماية لجميع عمليات الـ RPC لضمان عدم تداخل البيانات
                with self.server.db_lock:
                    if method == "get_chain_info":
                        result = {
                            "height": self.server.storage.get_best_height(),
                            "best_hash": self.server.storage.get_best_block().hash if self.server.storage.get_best_block() else ""
                        }
                    elif method == "get_balance":
                        addr = params[0] if params else ""
                        result = self.server.storage.get_balance(addr)
                    elif method == "submit_block":
                        # استقبال كتلة جديدة من المعدّن وبثها
                        block_dict = params[0]
                        block = Block.from_dict(block_dict)
                        if block.verify_pow():
                            self.server.storage.add_block(block)
                            if self.server.p2p:
                                self.server.p2p.broadcast_block(block)
                            result = "SUCCESS"
                        else:
                            error = "INVALID_POW"
                    else:
                        error = "UNKNOWN_METHOD"

                response = {"result": result, "error": error, "id": req.get("id")}
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(response).encode('utf-8'))
                
            except Exception as e:
                self.send_error(500, str(e))


class UrCoinRPCServer:
    def __init__(self, storage, mempool, p2p, wallet, host="0.0.0.0", port=9334, db_lock=None):
        self.storage = storage
        self.mempool = mempool
        self.p2p = p2p
        self.wallet = wallet
        self.host = host
        self.port = port
        # 🟥 إذا لم يمرر قفل، ننشئ واحداً افتراضياً لمنع حدوث خطأ برمي
        self.db_lock = db_lock if db_lock else threading.Lock()
        
        # حماية قراءة عنوان المحفظة بوضع شرط ذكي
        if self.wallet:
            self.reward_address = self.wallet.address
        else:
            self.reward_address = "None"

        self.httpd = HTTPServer((self.host, self.port), UrCoinRPCHandler)
        # ربط الكائنات بالخادم لكي يتمكن الـ Handler من قراءتها بأمان
        self.httpd.storage = self.storage
        self.httpd.mempool = self.mempool
        self.httpd.p2p = self.p2p
        self.httpd.wallet = self.wallet
        self.httpd.db_lock = self.db_lock

    def start(self):
        self.server_thread = threading.Thread(target=self.httpd.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        print(f"[RPC] Thread-Safe RPC Server active on Address http://{self.host}:{self.port}/")

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
