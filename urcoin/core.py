"""
Ur Coin (URC) Core Blockchain Architecture:
- UTXO Model (TxIn, TxOut, Transaction)
- Block & BlockHeader with UrHash PoW Verification
- Dynamic Difficulty Adjustment (Rolling EMA / Digishield)
- Genesis Block Specification
"""

import json
import time
import struct
import hashlib
from typing import List, Optional
from urcoin.crypto import (
    KeyPair, hash160, urhash_cpu_verify, DEFAULT_DAG_ITEMS, DEFAULT_ROUNDS
)

# -------------------------------------------------------------
# Consensus Constants
# -------------------------------------------------------------
COIN_NAME = "Ur Coin"
COIN_SYMBOL = "URC"
DECIMALS = 8
COIN = 100_000_000 # 1 URC = 10^8 atomic units

INITIAL_BLOCK_REWARD = 50 * COIN
HALVING_INTERVAL = 210_000 # Halves every 210,000 blocks (~2.4 months at 30s)
TARGET_BLOCK_TIME = 30     # 30 seconds per block
DIFFICULTY_WINDOW = 5      # Retarget adjustment rolling window
MAX_DIFFICULTY_ADJUSTMENT = 4 # Maximum 4x change per window

# Initial mining target (accessible enough for instant local mining test)
INITIAL_TARGET_HEX = "0000ffff00000000000000000000000000000000000000000000000000000000"
INITIAL_TARGET = int(INITIAL_TARGET_HEX, 16)
MAX_TARGET = int("0000ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff", 16)

EPOCH_LENGTH = 10_000 # 10,000 blocks per DAG epoch (~3.5 days)

def calculate_block_reward(height: int) -> int:
    """Calculates block reward considering halving schedule."""
    halvings = height // HALVING_INTERVAL
    if halvings >= 64:
        return 0
    return INITIAL_BLOCK_REWARD >> halvings

def get_epoch_seed(epoch_number: int) -> bytes:
    """Derive deterministic 32-byte epoch seed for DAG."""
    seed = b"urcoin_epoch_seed_init_v1"
    for _ in range(epoch_number + 1):
        seed = hashlib.sha256(seed).digest()
    return seed

# -------------------------------------------------------------
# Transaction Models (UTXO)
# -------------------------------------------------------------
class TxIn:
    def __init__(self, txid: str, vout: int, signature: str = "", pubkey: str = ""):
        self.txid = txid         # 32-byte hex hash of referenced tx
        self.vout = vout         # Output index in referenced tx (-1 for coinbase)
        self.signature = signature # Hex-encoded DER/compact signature
        self.pubkey = pubkey     # Hex-encoded 64-byte public key

    def to_dict(self) -> dict:
        return {
            "txid": self.txid,
            "vout": self.vout,
            "signature": self.signature,
            "pubkey": self.pubkey
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TxIn":
        return cls(d["txid"], d["vout"], d.get("signature", ""), d.get("pubkey", ""))

class TxOut:
    def __init__(self, amount: int, recipient: str):
        self.amount = amount       # In atomic units (1 URC = 10^8)
        self.recipient = recipient # urc1... address

    def to_dict(self) -> dict:
        return {
            "amount": self.amount,
            "recipient": self.recipient
        }

    @classmethod
    def from_dict(cls, d: dict) -> "TxOut":
        return cls(d["amount"], d["recipient"])

class Transaction:
    def __init__(self, inputs: List[TxIn], outputs: List[TxOut], timestamp: Optional[int] = None, txid: Optional[str] = None):
        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = timestamp if timestamp is not None else int(time.time())
        self.txid = txid if txid else self.calculate_hash()

    def calculate_hash(self) -> str:
        """Calculate canonical transaction hash (txid)."""
        data = {
            "inputs": [{"txid": i.txid, "vout": i.vout, "sig": i.signature if (i.vout == -1) else ""} for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs],
            "timestamp": self.timestamp
        }
        encoded = json.dumps(data, sort_keys=True).encode("utf-8")
        return hashlib.sha256(hashlib.sha256(encoded).digest()).hexdigest()

    def get_signing_hash(self, input_index: int) -> bytes:
        """Message hash to be signed for spending input_index."""
        data = {
            "txid": self.calculate_hash(),
            "input_index": input_index
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode("utf-8")).digest()

    def is_coinbase(self) -> bool:
        """Coinbase transactions have 1 input with txid of 64 zeros and vout=-1."""
        return len(self.inputs) == 1 and self.inputs[0].vout == -1 and self.inputs[0].txid == "0" * 64

    def to_dict(self) -> dict:
        return {
            "txid": self.txid,
            "timestamp": self.timestamp,
            "inputs": [i.to_dict() for i in self.inputs],
            "outputs": [o.to_dict() for o in self.outputs]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Transaction":
        inputs = [TxIn.from_dict(i) for i in d["inputs"]]
        outputs = [TxOut.from_dict(o) for o in d["outputs"]]
        return cls(inputs, outputs, d["timestamp"], d.get("txid"))

    @classmethod
    def create_coinbase(cls, recipient_address: str, reward: int, height: int) -> "Transaction":
        """Generate newly minted coinbase transaction for miner reward."""
        coinbase_in = TxIn(
            txid="0" * 64,
            vout=-1,
            signature=f"Coinbase Mined Block #{height} - Ur Coin Decentralized Network".encode().hex(),
            pubkey=""
        )
        coinbase_out = TxOut(amount=reward, recipient=recipient_address)
        return cls([coinbase_in], [coinbase_out])

# -------------------------------------------------------------
# Block & BlockHeader
# -------------------------------------------------------------
class BlockHeader:
    def __init__(self, version: int, prev_hash: str, merkle_root: str,
                 timestamp: int, target: int, nonce: int, height: int, epoch: int):
        self.version = version
        self.prev_hash = prev_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.target = target
        self.nonce = nonce
        self.height = height
        self.epoch = epoch

    def get_mining_hash(self) -> bytes:
        """Computes the 32-byte header hash that is mined against the nonce."""
        payload = (
            self.version.to_bytes(4, "big") +
            bytes.fromhex(self.prev_hash) +
            bytes.fromhex(self.merkle_root) +
            self.timestamp.to_bytes(8, "big") +
            self.target.to_bytes(32, "big") +
            self.height.to_bytes(8, "big") +
            self.epoch.to_bytes(4, "big")
        )
        return hashlib.sha256(payload).digest()

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "prev_hash": self.prev_hash,
            "merkle_root": self.merkle_root,
            "timestamp": self.timestamp,
            "target": hex(self.target),
            "target_int": self.target,
            "nonce": self.nonce,
            "height": self.height,
            "epoch": self.epoch
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BlockHeader":
        target = int(d["target"], 16) if isinstance(d["target"], str) else d["target"]
        return cls(
            version=d["version"],
            prev_hash=d["prev_hash"],
            merkle_root=d["merkle_root"],
            timestamp=d["timestamp"],
            target=target,
            nonce=d["nonce"],
            height=d["height"],
            epoch=d.get("epoch", 0)
        )

class Block:
    def __init__(self, header: BlockHeader, transactions: List[Transaction], block_hash: Optional[str] = None):
        self.header = header
        self.transactions = transactions
        self.hash = block_hash if block_hash else self.calculate_hash()

    def calculate_merkle_root(self) -> str:
        """Compute Merkle Root of all transactions in block."""
        if not self.transactions:
            return "0" * 64
        hashes = [bytes.fromhex(tx.txid) for tx in self.transactions]
        while len(hashes) > 1:
            if len(hashes) % 2 != 0:
                hashes.append(hashes[-1]) # duplicate last item if odd
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashlib.sha256(hashes[i] + hashes[i+1]).digest()
                new_hashes.append(combined)
            hashes = new_hashes
        return hashes[0].hex()

    def calculate_hash(self) -> str:
        """Compute final block hash using UrHash PoW."""
        epoch_seed = get_epoch_seed(self.header.epoch)
        header_hash = self.header.get_mining_hash()
        is_valid, final_hash = urhash_cpu_verify(
            header_hash, self.header.nonce, epoch_seed, self.header.target
        )
        return final_hash

    def verify_pow(self) -> bool:
        """Verify that the block satisfies the target difficulty using UrHash."""
        epoch_seed = get_epoch_seed(self.header.epoch)
        header_hash = self.header.get_mining_hash()
        is_valid, calculated_hash = urhash_cpu_verify(
            header_hash, self.header.nonce, epoch_seed, self.header.target
        )
        if not is_valid:
            return False
        self.hash = calculated_hash
        return True

    def to_dict(self) -> dict:
        return {
            "hash": self.hash,
            "header": self.header.to_dict(),
            "transactions": [tx.to_dict() for tx in self.transactions]
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        header = BlockHeader.from_dict(d["header"])
        transactions = [Transaction.from_dict(t) for t in d["transactions"]]
        return cls(header, transactions, d.get("hash"))

# -------------------------------------------------------------
# Genesis Block Creation
# -------------------------------------------------------------
GENESIS_MESSAGE = "2026-10-15: Ur Coin (URC) - Ancient Mesopotamian Ur Civilization Meets Decentralized GPU PoW"
GENESIS_MINER_ADDRESS = "urc1V1UrCoinFoundationGenesisRewardAddressXXXXXXXX"

def create_genesis_block() -> Block:
    """Generate the immutable Genesis Block for Ur Coin."""
    coinbase_in = TxIn(
        txid="0" * 64,
        vout=-1,
        signature=GENESIS_MESSAGE.encode("utf-8").hex(),
        pubkey=""
    )
    coinbase_out = TxOut(amount=INITIAL_BLOCK_REWARD, recipient=GENESIS_MINER_ADDRESS)
    genesis_tx = Transaction([coinbase_in], [coinbase_out], timestamp=1792015200)

    header = BlockHeader(
        version=1,
        prev_hash="0" * 64,
        merkle_root=genesis_tx.txid,
        timestamp=1792015200,
        target=MAX_TARGET, # Genesis target is open
        nonce=42,
        height=0,
        epoch=0
    )
    genesis_block = Block(header, [genesis_tx])
    genesis_block.header.merkle_root = genesis_block.calculate_merkle_root()
    genesis_block.hash = genesis_block.calculate_hash()
    return genesis_block

GENESIS_BLOCK = create_genesis_block()

# -------------------------------------------------------------
# Difficulty Adjustment (Kimoto / Digishield Algorithm)
# -------------------------------------------------------------
def calculate_next_target(past_blocks: List[BlockHeader]) -> int:
    """
    Adjusts mining target every DIFFICULTY_WINDOW blocks to target 30s block time.
    Uses exponential moving average with damping factors to prevent wild swings.
    """
    if len(past_blocks) < DIFFICULTY_WINDOW:
        return INITIAL_TARGET

    first_block = past_blocks[-DIFFICULTY_WINDOW]
    last_block = past_blocks[-1]

    actual_timespan = last_block.timestamp - first_block.timestamp
    target_timespan = (DIFFICULTY_WINDOW - 1) * TARGET_BLOCK_TIME

    # Bound damping
    if actual_timespan < target_timespan // MAX_DIFFICULTY_ADJUSTMENT:
        actual_timespan = target_timespan // MAX_DIFFICULTY_ADJUSTMENT
    elif actual_timespan > target_timespan * MAX_DIFFICULTY_ADJUSTMENT:
        actual_timespan = target_timespan * MAX_DIFFICULTY_ADJUSTMENT

    current_target = last_block.target
    new_target = (current_target * actual_timespan) // target_timespan

    # Prevent target from exceeding MAX_TARGET
    if new_target > MAX_TARGET:
        new_target = MAX_TARGET
    if new_target <= 0:
        new_target = 1

    return new_target
