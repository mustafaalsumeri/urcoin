"""
Ur Coin Mempool:
- In-memory transaction pool
- Uses the same transaction rules as block connect
"""

from typing import Dict, List, Set, Tuple
from urcoin.consensus import validate_transaction
from urcoin.core import Transaction
from urcoin.storage import BlockchainStorage


class Mempool:
    def __init__(self, storage: BlockchainStorage):
        self.storage = storage
        self.transactions: Dict[str, Transaction] = {}
        self.spent_outpoints: Set[Tuple[str, int]] = set()

    def add_transaction(self, tx: Transaction) -> Tuple[bool, str]:
        if tx.txid in self.transactions:
            return False, "Transaction already in mempool"

        if tx.is_coinbase():
            return False, "Coinbase transaction cannot be accepted into mempool directly"

        seen_inputs = set()
        for tx_in in tx.inputs:
            outpoint = (tx_in.txid, tx_in.vout)
            if outpoint in seen_inputs:
                return False, "Duplicate inputs within transaction"
            seen_inputs.add(outpoint)
            if outpoint in self.spent_outpoints:
                return False, f"Double spend detected for outpoint {tx_in.txid}:{tx_in.vout}"

        def get_utxo(txid: str, vout: int):
            return self.storage.get_utxo(txid, vout)

        ok, err, _fee = validate_transaction(tx, get_utxo, is_coinbase=False)
        if not ok:
            return False, err

        self.transactions[tx.txid] = tx
        for tx_in in tx.inputs:
            self.spent_outpoints.add((tx_in.txid, tx_in.vout))
        return True, "Transaction admitted to mempool"

    def remove_mined_transactions(self, block_transactions: List[Transaction]):
        for tx in block_transactions:
            if tx.txid in self.transactions:
                del self.transactions[tx.txid]
            for tx_in in tx.inputs:
                self.spent_outpoints.discard((tx_in.txid, tx_in.vout))

    def revalidate(self):
        """Drop transactions that are no longer valid after a reorg."""
        pending = list(self.transactions.values())
        self.transactions.clear()
        self.spent_outpoints.clear()
        for tx in pending:
            self.add_transaction(tx)

    def get_transactions_for_block(self, max_count: int = 500) -> List[Transaction]:
        return list(self.transactions.values())[:max_count]

    def size(self) -> int:
        return len(self.transactions)
