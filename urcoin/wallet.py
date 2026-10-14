"""
Ur Coin Wallet Engine:
- Wallet generation, recovery via 12-word mnemonic or private key
- Local encrypted/JSON wallet storage
- UTXO coin selection and transaction creation & signing
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from urcoin.crypto import KeyPair, generate_mnemonic, mnemonic_to_seed
from urcoin.core import Transaction, TxIn, TxOut, COIN

DEFAULT_WALLET_PATH = "urcoin_wallet.json"

class Wallet:
    def __init__(self, keypair: Optional[KeyPair] = None, mnemonic: Optional[str] = None):
        if keypair is None:
            if mnemonic:
                seed = mnemonic_to_seed(mnemonic)
                self.keypair = KeyPair.from_seed(seed)
                self.mnemonic = mnemonic
            else:
                self.mnemonic = generate_mnemonic(12)
                seed = mnemonic_to_seed(self.mnemonic)
                self.keypair = KeyPair.from_seed(seed)
        else:
            self.keypair = keypair
            self.mnemonic = mnemonic if mnemonic else ""

        self.address = self.keypair.get_address()

    def save_to_file(self, filepath: str = DEFAULT_WALLET_PATH):
        """Save wallet keys to a local JSON file."""
        data = {
            "address": self.address,
            "private_key_hex": self.keypair.get_private_hex(),
            "public_key_hex": self.keypair.get_public_hex(),
            "mnemonic": self.mnemonic
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"[Wallet] Saved wallet to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str = DEFAULT_WALLET_PATH) -> "Wallet":
        """Load an existing wallet from JSON file."""
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Wallet file {filepath} not found.")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        kp = KeyPair.from_private_hex(data["private_key_hex"])
        return cls(keypair=kp, mnemonic=data.get("mnemonic", ""))

    @classmethod
    def create_or_load(cls, filepath: str = DEFAULT_WALLET_PATH) -> "Wallet":
        """Load wallet if exists, or create and save a new one."""
        if os.path.exists(filepath):
            return cls.load_from_file(filepath)
        w = cls()
        w.save_to_file(filepath)
        return w

    def create_transaction(self, recipient: str, amount_atomic: int,
                           utxos: List[Dict], fee_atomic: int = 10_000) -> Transaction:
        """
        Build and sign a transaction spending unspent outputs.
        `amount_atomic` is in atomic units (1 URC = 10^8 units).
        """
        total_required = amount_atomic + fee_atomic
        selected_utxos = []
        accumulated = 0

        # Greedy coin selection
        for u in utxos:
            selected_utxos.append(u)
            accumulated += u["amount"]
            if accumulated >= total_required:
                break

        if accumulated < total_required:
            raise ValueError(
                f"Insufficient funds: Have {accumulated / COIN:.4f} URC, "
                f"need {total_required / COIN:.4f} URC (including {fee_atomic / COIN:.4f} fee)."
            )

        # Build Inputs
        inputs = [
            TxIn(txid=u["txid"], vout=u["vout"], signature="", pubkey=self.keypair.get_public_hex())
            for u in selected_utxos
        ]

        # Build Outputs
        outputs = [TxOut(amount=amount_atomic, recipient=recipient)]

        # Add change output back to wallet
        change = accumulated - total_required
        if change > 0:
            outputs.append(TxOut(amount=change, recipient=self.address))

        # Construct unsigned transaction
        tx = Transaction(inputs=inputs, outputs=outputs)

        # Sign each input
        for idx in range(len(tx.inputs)):
            signing_hash = tx.get_signing_hash(idx)
            sig_bytes = self.keypair.sign(signing_hash)
            tx.inputs[idx].signature = sig_bytes.hex()

        return tx
