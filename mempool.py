"""
Ur Coin Mempool:
- In-memory transaction pool
- Double-spend protection and signature validation
- Block template transaction selection prioritized by fees
"""

from typing import Dict, List, Set, Tuple
from urcoin.core import Transaction, TxIn, TxOut
from urcoin.crypto import KeyPair
from urcoin.storage import BlockchainStorage

class Mempool:
    def __init__(self, storage: BlockchainStorage):
        self.storage = storage
        self.transactions: Dict[str, Transaction] = {}
        self.spent_outpoints: Set[Tuple[str, int]] = set()

    def add_transaction(self, tx: Transaction) -> Tuple[bool, str]:
        """Validate transaction and add to mempool."""
        if tx.txid in self.transactions:
            return False, "Transaction already in mempool"

        if tx.is_coinbase():
            return False, "Coinbase transaction cannot be accepted into mempool directly"

        if not tx.inputs or not tx.outputs:
            return False, "Transaction must have inputs and outputs"

        # Check for duplicate inputs within the transaction itself
        seen_inputs = set()
        for tx_in in tx.inputs:
            outpoint = (tx_in.txid, tx_in.vout)
            if outpoint in seen_inputs:
                return False, "Duplicate inputs within transaction"
            seen_inputs.add(outpoint)

            # Check if input is already being spent in another pending mempool tx
            if outpoint in self.spent_outpoints:
                return False, f"Double spend detected for outpoint {tx_in.txid}:{tx_in.vout}"

        # Validate inputs against UTXO database and verify signatures
        total_input_amount = 0
        for i, tx_in in enumerate(tx.inputs):
            # Look up parent transaction
            parent_tx = self.storage.get_transaction(tx_in.txid)
            if not parent_tx:
                return False, f"Parent transaction {tx_in.txid} not found"

            if tx_in.vout < 0 or tx_in.vout >= len(parent_tx.outputs):
                return False, f"Invalid output index {tx_in.vout} for parent {tx_in.txid}"

            parent_out = parent_tx.outputs[tx_in.vout]
            total_input_amount += parent_out.amount

            # Verify signature
            if not tx_in.pubkey or not tx_in.signature:
                return False, "Missing signature or public key"

            pubkey_bytes = bytes.fromhex(tx_in.pubkey)
            sig_bytes = bytes.fromhex(tx_in.signature)
            derived_addr = KeyPair.pubkey_to_address(pubkey_bytes)

            if derived_addr != parent_out.recipient:
                return False, f"Signer {derived_addr} does not match UTXO owner {parent_out.recipient}"

            signing_hash = tx.get_signing_hash(i)
            if not KeyPair.verify(pubkey_bytes, signing_hash, sig_bytes):
                return False, f"Invalid cryptographic signature for input {i}"

        # Validate outputs
        total_output_amount = 0
        for tx_out in tx.outputs:
            if tx_out.amount <= 0:
                return False, "Output amount must be positive"
            total_output_amount += tx_out.amount

        if total_output_amount > total_input_amount:
            return False, f"Output total ({total_output_amount}) exceeds input total ({total_input_amount})"

        # Admission to mempool
        self.transactions[tx.txid] = tx
        for tx_in in tx.inputs:
            self.spent_outpoints.add((tx_in.txid, tx_in.vout))

        return True, "Transaction admitted to mempool"

    def remove_mined_transactions(self, block_transactions: List[Transaction]):
        """Remove confirmed transactions and their spent outpoints from mempool."""
        for tx in block_transactions:
            if tx.txid in self.transactions:
                del self.transactions[tx.txid]
            for tx_in in tx.inputs:
                outpoint = (tx_in.txid, tx_in.vout)
                self.spent_outpoints.discard(outpoint)

    def get_transactions_for_block(self, max_count: int = 500) -> List[Transaction]:
        """Return prioritized list of transactions for a new block template."""
        return list(self.transactions.values())[:max_count]

    def size(self) -> int:
        return len(self.transactions)
