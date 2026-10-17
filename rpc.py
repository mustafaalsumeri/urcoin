"""
Ur Coin (URC) - Stable JSON-RPC Server & Web Explorer Daemon
Professional Isolated Production Engine - Clean Version
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

        # تخديم صفحة الويب من ملف خارجي مستقل تماماً لمنع أخطاء السنتكس
        if path == "/" or path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            
            # إذا لم يجد ملف الواجهة الخارجي، يعرض واجهة طوارئ خفيفة جداً
            if not os.path.exists("index.html"):
                self.wfile.write(b"<h1>Ur Coin Node Running - index.html missing</h1>")
                return
                
            with open("index.html", "r", encoding="utf-8") as f:
                html_template = f.read()
                
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

            # استبدال المتغيرات الحية بذكاء
            rendered_html = html_template.replace("{{best_height}}", str(best_height))\
                                         .replace("{{balance}}", f"{balance:.8f}")\
                                         .replace("{{circulating_supply}}", f"{circulating_supply:,.2f}")\
                                         .replace("{{mempool_count}}", str(mempool_count))\
                                         .replace("{{address}}", address)
            
            self.wfile.write(rendered_html.encode('utf-8'))
            return

        elif path == "/api/blocks":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            with self.server.db_lock:
                height = self.server.storage.get_best_height()
                blocks_data = []
                start = max(0, height - 10)
                for h in range(start, height + 1):
                    b = self.server.storage.get_block_by_height(h)
                    if b:
                        blocks_data.append({"height": b.header.height, "hash": b.hash, "tx_count": len(b.transactions)})
            self.wfile.write(json.dumps(blocks_data).encode('utf-8'))
            return
        else:
            self.send_error(404, "File Not Found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path

        if path == "/action/send":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = parse_qs(post_data.decode('utf-8'))
            
            wallet_to_use = self.server.wallet if self.server.wallet else getattr(self.server, 'local_wallet', None)
            if not wallet_to_use:
                self.send_error(403, "Wallet Restricted.")
                return
            
            try:
                recipient = params.get('recipient')[0]
                amount = float(params.get('amount')[0])
                
                with self.server.db_lock:
                    tx = wallet_to_use.create_transaction(self.server.storage, recipient, amount)
                    if self.server.mempool.add_transaction(tx):
                        if self.server.p2p:
                            self.server.p2p.broadcast_transaction(tx)
                
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return
            except Exception as e:
                self.send_error(400, f"Error: {str(e)}")
                return

        elif path == "/rpc" or path == "/":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                req = json.loads(post_data.decode('utf-8'))
                method = req.get("method")
                params = req.get("params", [])
                
                result = None
                error = None

                with self.server.db_lock:
                    if method == "get_chain_info":
                        result = {
                            "height": self.server.storage.get_best_height(),
                            "best_hash": self.server.storage.get_best_block().hash if self.server.storage.get_best_block() else ""
                        }
                    elif method == "get_balance":
                        addr = params if isinstance(params, list) and params else (params if params else "")
                        result = self.server.storage.get_balance(addr)
                    elif method == "submit_block":
                        block_dict = params
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
        self.db_lock = db_lock if db_lock else threading.Lock()
        
        if self.wallet:
            self.reward_address = self.wallet.address
        else:
            self.reward_address = "None"

        self.httpd = HTTPServer((self.host, self.port), UrCoinRPCHandler)
        self.httpd.storage = self.storage
        self.httpd.mempool = self.mempool
        self.httpd.p2p = self.p2p
        self.httpd.wallet = self.wallet
        self.httpd.db_lock = self.db_lock

    def start(self):
        self.server_thread = threading.Thread(target=self.httpd.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()
        print(f"[RPC] Isolated Engine Active on port {self.port}")

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
