"""
Ur Coin persistent storage:
- Blocks indexed by hash (forks allowed)
- Main chain marked with in_main
- UTXO set for the best chain only
- Undo logs so a heavier fork can reorganize
"""

import json
import sqlite3
import threading
from typing import Dict, List, Optional, Tuple

from urcoin.consensus import validate_block
from urcoin.core import GENESIS_BLOCK, Block, Transaction, block_work
from urcoin.exchange import ExchangeEngine


class BlockchainStorage:
    def __init__(self, db_path: str = "urcoin_data.db"):
        self.db_path = db_path
        self.lock = threading.RLock()
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.init_db()
        self.exchange = ExchangeEngine(self.conn, self.lock)

    def init_db(self):
        with self.lock:
            self._migrate_if_needed()
            with self.conn:
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS blocks (
                        hash TEXT PRIMARY KEY,
                        height INTEGER NOT NULL,
                        prev_hash TEXT NOT NULL,
                        merkle_root TEXT,
                        timestamp INTEGER,
                        target TEXT,
                        nonce INTEGER,
                        epoch INTEGER,
                        tx_count INTEGER,
                        chainwork TEXT NOT NULL,
                        in_main INTEGER NOT NULL DEFAULT 0,
                        raw_json TEXT
                    )
                """)
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_blocks_main_height ON blocks(in_main, height)"
                )
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_blocks_prev ON blocks(prev_hash)"
                )
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS transactions (
                        txid TEXT PRIMARY KEY,
                        block_hash TEXT,
                        block_height INTEGER,
                        timestamp INTEGER,
                        raw_json TEXT
                    )
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS utxos (
                        txid TEXT,
                        vout INTEGER,
                        amount INTEGER,
                        recipient TEXT,
                        PRIMARY KEY(txid, vout)
                    )
                """)
                self.conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_utxo_recipient ON utxos(recipient)"
                )
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS metadata (
                        key TEXT PRIMARY KEY,
                        value TEXT
                    )
                """)
                self.conn.execute("""
                    CREATE TABLE IF NOT EXISTS undo_log (
                        block_hash TEXT PRIMARY KEY,
                        payload TEXT NOT NULL
                    )
                """)

            if self.get_best_height() < 0:
                ok, msg = self.accept_block(GENESIS_BLOCK)
                if not ok:
                    raise RuntimeError(f"Failed to insert genesis: {msg}")

    def _migrate_if_needed(self):
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='blocks'"
        )
        if not cur.fetchone():
            return
        cols = [r[1] for r in self.conn.execute("PRAGMA table_info(blocks)")]
        if "chainwork" in cols and "in_main" in cols:
            return
        print("[Storage] Migrating blockchain database to fork-safe schema...")
        rows = list(self.conn.execute("SELECT raw_json FROM blocks ORDER BY height ASC"))
        with self.conn:
            self.conn.execute("ALTER TABLE blocks RENAME TO blocks_legacy")
            self.conn.execute("""
                CREATE TABLE blocks (
                    hash TEXT PRIMARY KEY,
                    height INTEGER NOT NULL,
                    prev_hash TEXT NOT NULL,
                    merkle_root TEXT,
                    timestamp INTEGER,
                    target TEXT,
                    nonce INTEGER,
                    epoch INTEGER,
                    tx_count INTEGER,
                    chainwork TEXT NOT NULL,
                    in_main INTEGER NOT NULL DEFAULT 0,
                    raw_json TEXT
                )
            """)
            chainwork = 0
            for row in rows:
                block = Block.from_dict(json.loads(row["raw_json"]))
                chainwork += block_work(block.header.target)
                self.conn.execute("""
                    INSERT OR REPLACE INTO blocks
                    (hash, height, prev_hash, merkle_root, timestamp, target, nonce,
                     epoch, tx_count, chainwork, in_main, raw_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """, (
                    block.hash,
                    block.header.height,
                    block.header.prev_hash,
                    block.header.merkle_root,
                    block.header.timestamp,
                    hex(block.header.target),
                    block.header.nonce,
                    block.header.epoch,
                    len(block.transactions),
                    str(chainwork),
                    json.dumps(block.to_dict()),
                ))
            self.conn.execute("DROP TABLE blocks_legacy")
            if rows:
                last = Block.from_dict(json.loads(rows[-1]["raw_json"]))
                self.conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_block_hash', ?)",
                    (last.hash,),
                )
                self.conn.execute(
                    "INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_height', ?)",
                    (str(last.header.height),),
                )

    def get_best_height(self) -> int:
        with self.lock:
            cur = self.conn.execute(
                "SELECT value FROM metadata WHERE key = 'best_height'"
            )
            row = cur.fetchone()
            if row:
                return int(row["value"])
            cur = self.conn.execute(
                "SELECT MAX(height) as max_h FROM blocks WHERE in_main = 1"
            )
            row = cur.fetchone()
            if row and row["max_h"] is not None:
                return row["max_h"]
            return -1

    def get_best_block(self) -> Optional[Block]:
        with self.lock:
            cur = self.conn.execute(
                "SELECT value FROM metadata WHERE key = 'best_block_hash'"
            )
            row = cur.fetchone()
            if row:
                return self.get_block_by_hash(row["value"])
            height = self.get_best_height()
            if height < 0:
                return None
            return self.get_block_by_height(height)

    def get_block_by_height(self, height: int) -> Optional[Block]:
        with self.lock:
            cur = self.conn.execute(
                "SELECT raw_json FROM blocks WHERE height = ? AND in_main = 1",
                (height,),
            )
            row = cur.fetchone()
            if not row:
                return None
            return Block.from_dict(json.loads(row["raw_json"]))

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        with self.lock:
            return self._get_block_by_hash_unlocked(block_hash)

    def _get_block_by_hash_unlocked(self, block_hash: str) -> Optional[Block]:
        cur = self.conn.execute(
            "SELECT raw_json FROM blocks WHERE hash = ?", (block_hash,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return Block.from_dict(json.loads(row["raw_json"]))

    def get_utxo(self, txid: str, vout: int) -> Optional[Dict]:
        with self.lock:
            cur = self.conn.execute(
                "SELECT txid, vout, amount, recipient FROM utxos WHERE txid = ? AND vout = ?",
                (txid, vout),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def add_block(self, block: Block) -> bool:
        ok, _msg = self.accept_block(block)
        return ok

    def accept_block(self, block: Block) -> Tuple[bool, str]:
        """Validate and store a block. May reorg to a heavier fork."""
        with self.lock:
            if self._get_block_by_hash_unlocked(block.hash):
                return True, "already known"

            parent = None
            ancestor_headers = []
            if block.header.height == 0:
                ancestor_headers = [block.header]
            else:
                parent = self._get_block_by_hash_unlocked(block.header.prev_hash)
                if parent is None:
                    return False, "parent block not found"
                ancestor_headers = self._headers_ending_at(block.header.prev_hash, 32)

            def get_utxo(txid: str, vout: int):
                cur = self.conn.execute(
                    "SELECT txid, vout, amount, recipient FROM utxos WHERE txid = ? AND vout = ?",
                    (txid, vout),
                )
                row = cur.fetchone()
                return dict(row) if row else None

            tip = self._best_block_unlocked()
            extends_tip = parent is None or tip is None or parent.hash == tip.hash

            ok, err = validate_block(
                block,
                parent=parent,
                get_utxo=get_utxo,
                ancestor_headers=ancestor_headers,
                skip_utxo=not extends_tip,
            )
            if not ok:
                return False, err

            self._insert_block_row(block, in_main=0)
            if extends_tip:
                self._connect_block(block)
                return True, "connected"

            if tip is not None and self._chainwork_of(block.hash) > self._chainwork_of(tip.hash):
                return self._reorg_to(block.hash)
            return True, "stored side block"

    def _best_block_unlocked(self) -> Optional[Block]:
        cur = self.conn.execute(
            "SELECT value FROM metadata WHERE key = 'best_block_hash'"
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._get_block_by_hash_unlocked(row["value"])

    def _headers_ending_at(self, block_hash: str, count: int) -> list:
        headers = []
        current = block_hash
        while current and len(headers) < count:
            block = self._get_block_by_hash_unlocked(current)
            if not block:
                break
            headers.append(block.header)
            if block.header.height == 0:
                break
            current = block.header.prev_hash
        headers.reverse()
        return headers

    def _chainwork_of(self, block_hash: str) -> int:
        cur = self.conn.execute(
            "SELECT chainwork FROM blocks WHERE hash = ?", (block_hash,)
        )
        row = cur.fetchone()
        return int(row["chainwork"]) if row else 0

    def _insert_block_row(self, block: Block, in_main: int):
        parent_work = 0
        if block.header.height > 0:
            parent_work = self._chainwork_of(block.header.prev_hash)
        work = parent_work + block_work(block.header.target)
        with self.conn:
            self.conn.execute("""
                INSERT OR REPLACE INTO blocks
                (hash, height, prev_hash, merkle_root, timestamp, target, nonce,
                 epoch, tx_count, chainwork, in_main, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block.hash,
                block.header.height,
                block.header.prev_hash,
                block.header.merkle_root,
                block.header.timestamp,
                hex(block.header.target),
                block.header.nonce,
                block.header.epoch,
                len(block.transactions),
                str(work),
                in_main,
                json.dumps(block.to_dict()),
            ))

    def _connect_block(self, block: Block):
        spent = []
        created = []
        with self.conn:
            for tx in block.transactions:
                self.conn.execute("""
                    INSERT OR REPLACE INTO transactions
                    (txid, block_hash, block_height, timestamp, raw_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    tx.txid,
                    block.hash,
                    block.header.height,
                    tx.timestamp,
                    json.dumps(tx.to_dict()),
                ))
                if not tx.is_coinbase():
                    for tx_in in tx.inputs:
                        cur = self.conn.execute(
                            "SELECT txid, vout, amount, recipient FROM utxos WHERE txid = ? AND vout = ?",
                            (tx_in.txid, tx_in.vout),
                        )
                        row = cur.fetchone()
                        if row:
                            spent.append(dict(row))
                        self.conn.execute(
                            "DELETE FROM utxos WHERE txid = ? AND vout = ?",
                            (tx_in.txid, tx_in.vout),
                        )
                for vout, tx_out in enumerate(tx.outputs):
                    created.append({
                        "txid": tx.txid,
                        "vout": vout,
                        "amount": tx_out.amount,
                        "recipient": tx_out.recipient,
                    })
                    self.conn.execute("""
                        INSERT OR REPLACE INTO utxos (txid, vout, amount, recipient)
                        VALUES (?, ?, ?, ?)
                    """, (tx.txid, vout, tx_out.amount, tx_out.recipient))

            self.conn.execute(
                "INSERT OR REPLACE INTO undo_log (block_hash, payload) VALUES (?, ?)",
                (block.hash, json.dumps({"spent": spent, "created": created})),
            )
            self.conn.execute(
                "UPDATE blocks SET in_main = 1 WHERE hash = ?", (block.hash,)
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_block_hash', ?)",
                (block.hash,),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_height', ?)",
                (str(block.header.height),),
            )

    def _disconnect_block(self, block: Block):
        cur = self.conn.execute(
            "SELECT payload FROM undo_log WHERE block_hash = ?", (block.hash,)
        )
        row = cur.fetchone()
        payload = json.loads(row["payload"]) if row else {"spent": [], "created": []}
        with self.conn:
            for u in payload.get("created", []):
                self.conn.execute(
                    "DELETE FROM utxos WHERE txid = ? AND vout = ?",
                    (u["txid"], u["vout"]),
                )
            for u in payload.get("spent", []):
                self.conn.execute("""
                    INSERT OR REPLACE INTO utxos (txid, vout, amount, recipient)
                    VALUES (?, ?, ?, ?)
                """, (u["txid"], u["vout"], u["amount"], u["recipient"]))
            for tx in block.transactions:
                self.conn.execute("DELETE FROM transactions WHERE txid = ?", (tx.txid,))
            self.conn.execute("UPDATE blocks SET in_main = 0 WHERE hash = ?", (block.hash,))
            parent_hash = block.header.prev_hash
            parent_height = block.header.height - 1
            self.conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_block_hash', ?)",
                (parent_hash,),
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_height', ?)",
                (str(parent_height),),
            )

    def _path_to_genesis(self, block_hash: str) -> List[str]:
        path = []
        current = block_hash
        while current and current != "0" * 64:
            path.append(current)
            block = self._get_block_by_hash_unlocked(current)
            if not block:
                break
            if block.header.height == 0:
                break
            current = block.header.prev_hash
        path.reverse()
        return path

    def _reorg_to(self, new_tip_hash: str) -> Tuple[bool, str]:
        old_tip = self._best_block_unlocked()
        if old_tip is None:
            return False, "no current tip"
        old_path = self._path_to_genesis(old_tip.hash)
        new_path = self._path_to_genesis(new_tip_hash)
        fork = 0
        while fork < len(old_path) and fork < len(new_path) and old_path[fork] == new_path[fork]:
            fork += 1
        # Disconnect old unique suffix (tip first)
        for h in reversed(old_path[fork:]):
            block = self._get_block_by_hash_unlocked(h)
            if block:
                self._disconnect_block(block)
        # Connect new unique suffix
        for h in new_path[fork:]:
            block = self._get_block_by_hash_unlocked(h)
            if not block:
                return False, "missing block during reorg"
            ancestor_headers = self._headers_ending_at(block.header.prev_hash, 32) if block.header.height else [block.header]
            parent = self._get_block_by_hash_unlocked(block.header.prev_hash) if block.header.height else None

            def get_utxo(txid: str, vout: int):
                cur = self.conn.execute(
                    "SELECT txid, vout, amount, recipient FROM utxos WHERE txid = ? AND vout = ?",
                    (txid, vout),
                )
                row = cur.fetchone()
                return dict(row) if row else None

            ok, err = validate_block(
                block,
                parent=parent,
                get_utxo=get_utxo,
                ancestor_headers=ancestor_headers,
            )
            if not ok:
                return False, f"reorg validation failed: {err}"
            self._connect_block(block)
        return True, "reorganized"

    def get_utxos_for_address(self, address: str) -> List[Dict]:
        with self.lock:
            cur = self.conn.execute(
                "SELECT txid, vout, amount, recipient FROM utxos WHERE recipient = ?",
                (address,),
            )
            return [dict(row) for row in cur.fetchall()]

    def get_balance(self, address: str) -> int:
        with self.lock:
            cur = self.conn.execute(
                "SELECT SUM(amount) as balance FROM utxos WHERE recipient = ?",
                (address,),
            )
            row = cur.fetchone()
            return row["balance"] if row and row["balance"] is not None else 0

    def get_recent_blocks(self, limit: int = 15) -> List[Dict]:
        with self.lock:
            cur = self.conn.execute("""
                SELECT height, hash, prev_hash, timestamp, tx_count, target, nonce
                FROM blocks WHERE in_main = 1 ORDER BY height DESC LIMIT ?
            """, (limit,))
            return [dict(row) for row in cur.fetchall()]

    def get_transaction(self, txid: str) -> Optional[Transaction]:
        with self.lock:
            cur = self.conn.execute(
                "SELECT raw_json FROM transactions WHERE txid = ?", (txid,)
            )
            row = cur.fetchone()
            if not row:
                return None
            return Transaction.from_dict(json.loads(row["raw_json"]))

    def get_past_headers(self, count: int = 15) -> List:
        with self.lock:
            cur = self.conn.execute("""
                SELECT raw_json FROM blocks
                WHERE in_main = 1
                ORDER BY height DESC LIMIT ?
            """, (count,))
            rows = cur.fetchall()
            blocks = [Block.from_dict(json.loads(r["raw_json"])) for r in reversed(rows)]
            return [b.header for b in blocks]
