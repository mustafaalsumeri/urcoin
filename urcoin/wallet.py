"""
Ur Coin Wallet Engine:
- Encrypted JSON wallet (scrypt + SHAKE stream + HMAC)
- UTXO coin selection and transaction creation & signing
"""

import hmac
import json
import os
import hashlib
import secrets
from typing import Dict, List, Optional

from urcoin.auth import get_wallet_password
from urcoin.crypto import KeyPair, generate_mnemonic, mnemonic_to_seed, is_valid_address
from urcoin.core import Transaction, TxIn, TxOut, COIN

DEFAULT_WALLET_PATH = "urcoin_wallet.json"


def _derive_keys(password: str, salt: bytes) -> tuple:
    material = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64
    )
    return material[:32], material[32:]


def _xor_stream(key: bytes, nonce: bytes, data: bytes) -> bytes:
    stream = hashlib.shake_256(key + nonce).digest(len(data))
    return bytes(a ^ b for a, b in zip(data, stream))


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

    def save_to_file(self, filepath: str = DEFAULT_WALLET_PATH, password: Optional[str] = None):
        password = password if password is not None else get_wallet_password()
        plaintext = json.dumps({
            "address": self.address,
            "private_key_hex": self.keypair.get_private_hex(),
            "public_key_hex": self.keypair.get_public_hex(),
            "mnemonic": self.mnemonic,
        }).encode("utf-8")
        salt = secrets.token_bytes(16)
        nonce = secrets.token_bytes(16)
        enc_key, mac_key = _derive_keys(password, salt)
        ciphertext = _xor_stream(enc_key, nonce, plaintext)
        tag = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
        data = {
            "version": 2,
            "encrypted": True,
            "kdf": "scrypt",
            "address": self.address,
            "salt_hex": salt.hex(),
            "nonce_hex": nonce.hex(),
            "mac_hex": tag.hex(),
            "ciphertext_hex": ciphertext.hex(),
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        print(f"[Wallet] Saved encrypted wallet to {filepath}")

    @classmethod
    def load_from_file(cls, filepath: str = DEFAULT_WALLET_PATH, password: Optional[str] = None) -> "Wallet":
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Wallet file {filepath} not found.")
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("encrypted"):
            password = password if password is not None else get_wallet_password()
            salt = bytes.fromhex(data["salt_hex"])
            nonce = bytes.fromhex(data["nonce_hex"])
            tag = bytes.fromhex(data["mac_hex"])
            ciphertext = bytes.fromhex(data["ciphertext_hex"])
            enc_key, mac_key = _derive_keys(password, salt)
            expected = hmac.new(mac_key, nonce + ciphertext, hashlib.sha256).digest()
            if not hmac.compare_digest(tag, expected):
                raise ValueError("Wallet password is wrong or the file is corrupted.")
            payload = json.loads(_xor_stream(enc_key, nonce, ciphertext).decode("utf-8"))
            kp = KeyPair.from_private_hex(payload["private_key_hex"])
            return cls(keypair=kp, mnemonic=payload.get("mnemonic", ""))

        # Legacy plaintext wallet: load once, then rewrite encrypted.
        print("[Wallet] Upgrading plaintext wallet to encrypted storage...")
        kp = KeyPair.from_private_hex(data["private_key_hex"])
        wallet = cls(keypair=kp, mnemonic=data.get("mnemonic", ""))
        wallet.save_to_file(filepath, password=password)
        return wallet

    @classmethod
    def create_or_load(cls, filepath: str = DEFAULT_WALLET_PATH) -> "Wallet":
        if os.path.exists(filepath):
            return cls.load_from_file(filepath)
        w = cls()
        w.save_to_file(filepath)
        print("[Wallet] Write down these 12 words and store them offline:")
        print(f"[Wallet] {w.mnemonic}")
        return w

    def create_transaction(self, recipient: str, amount_atomic: int,
                           utxos: List[Dict], fee_atomic: int = 10_000) -> Transaction:
        if not is_valid_address(recipient):
            raise ValueError("Recipient address is not a valid urc1... address.")

        total_required = amount_atomic + fee_atomic
        selected_utxos = []
        accumulated = 0

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

        inputs = [
            TxIn(txid=u["txid"], vout=u["vout"], signature="", pubkey=self.keypair.get_public_hex())
            for u in selected_utxos
        ]
        outputs = [TxOut(amount=amount_atomic, recipient=recipient)]
        change = accumulated - total_required
        if change > 0:
            outputs.append(TxOut(amount=change, recipient=self.address))

        tx = Transaction(inputs=inputs, outputs=outputs)
        for idx in range(len(tx.inputs)):
            signing_hash = tx.get_signing_hash(idx)
            sig_bytes = self.keypair.sign(signing_hash)
            tx.inputs[idx].signature = sig_bytes.hex()
        return tx
