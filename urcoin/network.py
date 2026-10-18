"""
Ur Coin P2P Network Engine:
- Peer discovery, connection management, and socket protocol
- Real-time block & transaction gossip broadcasting
- Automatic chain synchronization
"""

import socket
import threading
import json
import time
from typing import List, Set, Optional, Callable
from urcoin.core import Block, Transaction

DEFAULT_P2P_PORT = 9333
BUFFER_SIZE = 65536

class P2PMessage:
    HANDSHAKE = "HANDSHAKE"
    GET_BLOCKS = "GET_BLOCKS"
    BLOCKS = "BLOCKS"
    NEW_BLOCK = "NEW_BLOCK"
    NEW_TX = "NEW_TX"
    GET_PEERS = "GET_PEERS"
    PEERS = "PEERS"

class P2PNetwork:
    def __init__(self, host: str = "0.0.0.0", port: int = DEFAULT_P2P_PORT,
                 on_new_block: Optional[Callable[[Block], None]] = None,
                 on_new_tx: Optional[Callable[[Transaction], None]] = None,
                 get_chain_info: Optional[Callable[[], dict]] = None,
                 get_blocks_range: Optional[Callable[[int, int], List[Block]]] = None):
        self.host = host
        self.port = port
        self.on_new_block = on_new_block
        self.on_new_tx = on_new_tx
        self.get_chain_info = get_chain_info
        self.get_blocks_range = get_blocks_range

        self.running = False
        self.server_socket: Optional[socket.socket] = None
        self.peers: Set[str] = set() # "ip:port"
        self.peer_sockets: List[socket.socket] = []
        self.lock = threading.Lock()

    def start(self):
        """Start listening for incoming peer connections."""
        self.running = True
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(32)
        print(f"[P2P] Ur Coin Node listening on {self.host}:{self.port}")

        listener_thread = threading.Thread(target=self._listen_loop, daemon=True)
        listener_thread.start()

    def _listen_loop(self):
        while self.running:
            try:
                client_sock, addr = self.server_socket.accept()
                peer_str = f"{addr[0]}:{addr[1]}"
                with self.lock:
                    self.peer_sockets.append(client_sock)
                handler = threading.Thread(target=self._handle_peer, args=(client_sock, peer_str), daemon=True)
                handler.start()
            except Exception:
                break

    def connect_to_peer(self, peer_host: str, peer_port: int):
        """Actively connect to an external peer node."""
        peer_str = f"{peer_host}:{peer_port}"
        if peer_str in self.peers:
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((peer_host, peer_port))
            with self.lock:
                self.peers.add(peer_str)
                self.peer_sockets.append(sock)
            print(f"[P2P] Successfully connected to peer {peer_str}")

            # Send Handshake
            if self.get_chain_info:
                info = self.get_chain_info()
                self._send(sock, {
                    "type": P2PMessage.HANDSHAKE,
                    "height": info.get("height", 0),
                    "best_hash": info.get("best_hash", "")
                })

            handler = threading.Thread(target=self._handle_peer, args=(sock, peer_str), daemon=True)
            handler.start()
        except Exception as e:
            print(f"[P2P] Failed to connect to peer {peer_str}: {e}")

    def _send(self, sock: socket.socket, message: dict):
        try:
            payload = json.dumps(message).encode("utf-8") + b"\n"
            sock.sendall(payload)
        except Exception:
            pass

    def broadcast(self, message: dict):
        """Broadcast a message to all connected peers."""
        with self.lock:
            for sock in list(self.peer_sockets):
                self._send(sock, message)

    def broadcast_new_block(self, block: Block):
        """Gossip newly mined block to all network peers."""
        self.broadcast({
            "type": P2PMessage.NEW_BLOCK,
            "block": block.to_dict()
        })

    def broadcast_new_tx(self, tx: Transaction):
        """Gossip newly submitted transaction to all network peers."""
        self.broadcast({
            "type": P2PMessage.NEW_TX,
            "tx": tx.to_dict()
        })

    def _handle_peer(self, sock: socket.socket, peer_str: str):
        buffer = ""
        while self.running:
            try:
                data = sock.recv(BUFFER_SIZE)
                if not data:
                    break
                buffer += data.decode("utf-8")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if line.strip():
                        msg = json.loads(line)
                        self._process_message(sock, msg, peer_str)
            except Exception:
                break

        with self.lock:
            if sock in self.peer_sockets:
                self.peer_sockets.remove(sock)
            self.peers.discard(peer_str)
        try:
            sock.close()
        except Exception:
            pass

    def _process_message(self, sock: socket.socket, msg: dict, peer_str: str):
        msg_type = msg.get("type")

        if msg_type == P2PMessage.HANDSHAKE:
            peer_height = msg.get("height", 0)
            if self.get_chain_info:
                local_info = self.get_chain_info()
                local_height = local_info.get("height", 0)
                # If peer is further ahead, request missing blocks
                if peer_height > local_height:
                    self._send(sock, {
                        "type": P2PMessage.GET_BLOCKS,
                        "from_height": local_height + 1,
                        "to_height": peer_height
                    })

        elif msg_type == P2PMessage.GET_BLOCKS:
            from_h = msg.get("from_height", 0)
            to_h = msg.get("to_height", from_h + 100)
            if self.get_blocks_range:
                blocks = self.get_blocks_range(from_h, to_h)
                self._send(sock, {
                    "type": P2PMessage.BLOCKS,
                    "blocks": [b.to_dict() for b in blocks]
                })

        elif msg_type == P2PMessage.BLOCKS:
            raw_blocks = msg.get("blocks", [])
            for raw_b in raw_blocks:
                block = Block.from_dict(raw_b)
                if self.on_new_block:
                    self.on_new_block(block)

        elif msg_type == P2PMessage.NEW_BLOCK:
            block = Block.from_dict(msg["block"])
            if self.on_new_block:
                self.on_new_block(block)

        elif msg_type == P2PMessage.NEW_TX:
            tx = Transaction.from_dict(msg["tx"])
            if self.on_new_tx:
                self.on_new_tx(tx)

    def stop(self):
        self.running = False
        with self.lock:
            for sock in self.peer_sockets:
                try:
                    sock.close()
                except Exception:
                    pass
            self.peer_sockets.clear()
        if self.server_socket:
            try:
                self.server_socket.close()
            except Exception:
                pass
