"""
Single validation path used by miner, P2P, RPC, and tests.
A block is accepted only if every check below passes.
"""

from typing import Callable, Dict, Optional, Tuple
import time

from urcoin.core import (
    GENESIS_HASH,
    MAX_FUTURE_DRIFT,
    MAX_TARGET,
    Block,
    Transaction,
    calculate_block_reward,
    calculate_next_target,
)
from urcoin.crypto import KeyPair, is_valid_address

Utxo = Dict[str, object]
GetUtxo = Callable[[str, int], Optional[Utxo]]


def validate_transaction(
    tx: Transaction,
    get_utxo: GetUtxo,
    *,
    is_coinbase: bool = False,
    height: int = 0,
) -> Tuple[bool, str, int]:
    """
    Returns (ok, error, fee_atomic).
    fee_atomic is 0 for coinbase.
    """
    if tx.txid != tx.calculate_hash():
        return False, "txid does not match transaction contents", 0

    if is_coinbase:
        if not tx.is_coinbase():
            return False, "first transaction must be coinbase", 0
        if len(tx.outputs) != 1:
            return False, "coinbase must have exactly one output", 0
        if tx.outputs[0].amount <= 0:
            return False, "coinbase amount must be positive", 0
        # Genesis uses a placeholder address; later coinbases must be valid.
        if height > 0 and not is_valid_address(tx.outputs[0].recipient):
            return False, "coinbase recipient address is invalid", 0
        return True, "ok", 0

    if tx.is_coinbase():
        return False, "coinbase is only allowed as the first transaction", 0
    if not tx.inputs or not tx.outputs:
        return False, "transaction must have inputs and outputs", 0

    seen = set()
    total_in = 0
    for i, tx_in in enumerate(tx.inputs):
        outpoint = (tx_in.txid, tx_in.vout)
        if outpoint in seen:
            return False, "duplicate inputs within transaction", 0
        seen.add(outpoint)

        utxo = get_utxo(tx_in.txid, tx_in.vout)
        if not utxo:
            return False, f"input {tx_in.txid}:{tx_in.vout} is not an unspent output", 0

        total_in += int(utxo["amount"])

        if not tx_in.pubkey or not tx_in.signature:
            return False, "missing signature or public key", 0
        try:
            pubkey_bytes = bytes.fromhex(tx_in.pubkey)
            sig_bytes = bytes.fromhex(tx_in.signature)
        except ValueError:
            return False, "signature or public key is not valid hex", 0

        derived = KeyPair.pubkey_to_address(pubkey_bytes)
        if derived != utxo["recipient"]:
            return False, "signer does not own this output", 0
        if not KeyPair.verify(pubkey_bytes, tx.get_signing_hash(i), sig_bytes):
            return False, f"invalid signature on input {i}", 0

    total_out = 0
    for tx_out in tx.outputs:
        if tx_out.amount <= 0:
            return False, "output amount must be positive", 0
        if not is_valid_address(tx_out.recipient):
            return False, f"invalid recipient address {tx_out.recipient}", 0
        total_out += tx_out.amount

    if total_out > total_in:
        return False, "outputs exceed inputs", 0
    return True, "ok", total_in - total_out


def validate_block(
    block: Block,
    *,
    parent: Optional[Block],
    get_utxo: GetUtxo,
    ancestor_headers: list,
    now: Optional[int] = None,
    skip_utxo: bool = False,
) -> Tuple[bool, str]:
    header = block.header
    now = int(time.time()) if now is None else now

    if header.height == 0:
        if block.hash != GENESIS_HASH and block.calculate_hash() != GENESIS_HASH:
            return False, "genesis hash mismatch"
        if header.prev_hash != "0" * 64:
            return False, "genesis prev_hash must be zero"
        return True, "ok"

    if parent is None:
        return False, "parent block not found"

    if header.prev_hash != parent.hash:
        return False, "prev_hash does not match parent"
    if header.height != parent.header.height + 1:
        return False, "height must be parent height + 1"
    if header.epoch != header.height // 10_000:
        return False, "epoch does not match height"

    expected_target = calculate_next_target(ancestor_headers, now=header.timestamp)
    if header.target != expected_target:
        return False, "difficulty target does not match consensus"

    if header.target > MAX_TARGET:
        return False, "target above maximum"
    if header.timestamp > now + MAX_FUTURE_DRIFT:
        return False, "timestamp too far in the future"
    if header.timestamp < parent.header.timestamp:
        return False, "timestamp is earlier than parent"

    if not block.verify_pow():
        return False, "invalid proof of work"

    if block.calculate_merkle_root() != header.merkle_root:
        return False, "merkle root mismatch"

    if not block.transactions:
        return False, "block has no transactions"
    if not block.transactions[0].is_coinbase():
        return False, "first transaction must be coinbase"
    if any(tx.is_coinbase() for tx in block.transactions[1:]):
        return False, "only the first transaction may be coinbase"

    if skip_utxo:
        return True, "ok"

    overlay: Dict[Tuple[str, int], Optional[Utxo]] = {}

    def view(txid: str, vout: int) -> Optional[Utxo]:
        key = (txid, vout)
        if key in overlay:
            return overlay[key]
        return get_utxo(txid, vout)

    fees = 0
    for idx, tx in enumerate(block.transactions):
        ok, err, fee = validate_transaction(
            tx, view, is_coinbase=(idx == 0), height=header.height
        )
        if not ok:
            return False, err
        fees += fee
        if not tx.is_coinbase():
            for tx_in in tx.inputs:
                overlay[(tx_in.txid, tx_in.vout)] = None
        for vout, tx_out in enumerate(tx.outputs):
            overlay[(tx.txid, vout)] = {
                "txid": tx.txid,
                "vout": vout,
                "amount": tx_out.amount,
                "recipient": tx_out.recipient,
            }

    subsidy = calculate_block_reward(header.height)
    coinbase_out = block.transactions[0].outputs[0].amount
    if coinbase_out > subsidy + fees:
        return False, "coinbase claims more than subsidy plus fees"

    return True, "ok"
