"""
Ur Coin Persistent Storage Layer:
- SQLite Database for Blocks, Transactions, and Fast UTXO Index
- Atomic Transactions & Chain State Updates
"""

import sqlite3
import json
import os
from typing import Optional, List, Dict
from urcoin.core import Block, Transaction, TxIn, TxOut, GENESIS_BLOCK

class BlockchainStorage:
    def __init__(self, db_path: str = "urcoin_data.db"):
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.init_db()

    def init_db(self):
        """Create database tables if they do not exist."""
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS blocks (
                    height INTEGER PRIMARY KEY,
                    hash TEXT UNIQUE,
                    prev_hash TEXT,
                    merkle_root TEXT,
                    timestamp INTEGER,
                    target TEXT,
                    nonce INTEGER,
                    epoch INTEGER,
                    tx_count INTEGER,
                    raw_json TEXT
                )
            """)
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
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_utxo_recipient ON utxos(recipient)
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

        # If empty, insert Genesis Block
        if self.get_best_height() == -1:
            self.add_block(GENESIS_BLOCK)

    def get_best_height(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT MAX(height) as max_h FROM blocks")
        row = cur.fetchone()
        if row and row["max_h"] is not None:
            return row["max_h"]
        return -1

    def get_best_block(self) -> Optional[Block]:
        height = self.get_best_height()
        if height == -1:
            return None
        return self.get_block_by_height(height)

    def get_block_by_height(self, height: int) -> Optional[Block]:
        cur = self.conn.cursor()
        cur.execute("SELECT raw_json FROM blocks WHERE height = ?", (height,))
        row = cur.fetchone()
        if not row:
            return None
        return Block.from_dict(json.loads(row["raw_json"]))

    def get_block_by_hash(self, block_hash: str) -> Optional[Block]:
        cur = self.conn.cursor()
        cur.execute("SELECT raw_json FROM blocks WHERE hash = ?", (block_hash,))
        row = cur.fetchone()
        if not row:
            return None
        return Block.from_dict(json.loads(row["raw_json"]))

    def add_block(self, block: Block) -> bool:
        """Atomically persist block, transactions, and update UTXO state."""
        raw_json = json.dumps(block.to_dict())
        with self.conn:
            # 1. Insert Block
            self.conn.execute("""
                INSERT OR REPLACE INTO blocks
                (height, hash, prev_hash, merkle_root, timestamp, target, nonce, epoch, tx_count, raw_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                block.header.height,
                block.hash,
                block.header.prev_hash,
                block.header.merkle_root,
                block.header.timestamp,
                hex(block.header.target),
                block.header.nonce,
                block.header.epoch,
                len(block.transactions),
                raw_json
            ))

            # 2. Process Transactions & UTXOs
            for tx in block.transactions:
                self.conn.execute("""
                    INSERT OR REPLACE INTO transactions (txid, block_hash, block_height, timestamp, raw_json)
                    VALUES (?, ?, ?, ?, ?)
                """, (tx.txid, block.hash, block.header.height, tx.timestamp, json.dumps(tx.to_dict())))

                # Remove spent UTXOs (except for coinbase)
                if not tx.is_coinbase():
                    for tx_in in tx.inputs:
                        self.conn.execute("""
                            DELETE FROM utxos WHERE txid = ? AND vout = ?
                        """, (tx_in.txid, tx_in.vout))

                # Add new UTXOs from outputs
                for vout, tx_out in enumerate(tx.outputs):
                    self.conn.execute("""
                        INSERT OR REPLACE INTO utxos (txid, vout, amount, recipient)
                        VALUES (?, ?, ?, ?)
                    """, (tx.txid, vout, tx_out.amount, tx_out.recipient))

            # 3. Update Chain Metadata
            self.conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_block_hash', ?)", (block.hash,))
            self.conn.execute("INSERT OR REPLACE INTO metadata (key, value) VALUES ('best_height', ?)", (str(block.header.height),))

        return True

    def get_utxos_for_address(self, address: str) -> List[Dict]:
        """Fetch all unspent transaction outputs for an address."""
        cur = self.conn.cursor()
        cur.execute("SELECT txid, vout, amount, recipient FROM utxos WHERE recipient = ?", (address,))
        return [dict(row) for row in cur.fetchall()]

    def get_balance(self, address: str) -> int:
        """Calculate total spendable balance for an address in atomic units."""
        cur = self.conn.cursor()
        cur.execute("SELECT SUM(amount) as balance FROM utxos WHERE recipient = ?", (address,))
        row = cur.fetchone()
        return row["balance"] if row and row["balance"] is not None else 0

    def get_recent_blocks(self, limit: int = 15) -> List[Dict]:
        """Fetch the most recent blocks for explorer/dashboard."""
        cur = self.conn.cursor()
        cur.execute("""
            SELECT height, hash, prev_hash, timestamp, tx_count, target, nonce
            FROM blocks ORDER BY height DESC LIMIT ?
        """, (limit,))
        return [dict(row) for row in cur.fetchall()]

    def get_transaction(self, txid: str) -> Optional[Transaction]:
        cur = self.conn.cursor()
        cur.execute("SELECT raw_json FROM transactions WHERE txid = ?", (txid,))
        row = cur.fetchone()
        if not row:
            return None
        return Transaction.from_dict(json.loads(row["raw_json"]))

    def get_past_headers(self, count: int = 15) -> List:
        """Fetch recent block headers for difficulty adjustment."""
        cur = self.conn.cursor()
        cur.execute("SELECT raw_json FROM blocks ORDER BY height DESC LIMIT ?", (count,))
        rows = cur.fetchall()
        blocks = [Block.from_dict(json.loads(r["raw_json"])) for r in reversed(rows)]
        return [b.header for b in blocks]
