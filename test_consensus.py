"""
CPU-only consensus tests. No GPU required.
Run: python test_consensus.py
"""

import os
import sys
import time
import tempfile

from urcoin.core import (
    GENESIS_BLOCK,
    MAX_TARGET,
    Block,
    BlockHeader,
    Transaction,
    TxOut,
    calculate_next_target,
)
from urcoin.crypto import urhash_cpu_hash, get_epoch_seed
from urcoin.storage import BlockchainStorage
from urcoin.wallet import Wallet


def mine_cpu(block: Block, max_tries: int = 2_000_000) -> Block:
    epoch_seed = get_epoch_seed(block.header.epoch)
    header_hash = block.header.get_mining_hash()
    for nonce in range(max_tries):
        digest = urhash_cpu_hash(header_hash, nonce, epoch_seed)
        if int.from_bytes(digest, "big") <= block.header.target:
            block.header.nonce = nonce
            block.hash = digest.hex()
            return block
    raise RuntimeError("Could not mine a test block; target is too hard")


def make_block(storage: BlockchainStorage, miner_address: str, extra_txs=None) -> Block:
    parent = storage.get_best_block()
    height = parent.header.height + 1
    from urcoin.core import calculate_block_reward
    reward = calculate_block_reward(height)
    coinbase = Transaction.create_coinbase(miner_address, reward, height)
    txs = [coinbase] + (extra_txs or [])
    headers = storage.get_past_headers(10)
    target = calculate_next_target(headers)
    # Tests use an easy target so CPU mining finishes quickly.
    target = MAX_TARGET
    header = BlockHeader(
        version=1,
        prev_hash=parent.hash,
        merkle_root="",
        timestamp=max(int(time.time()), parent.header.timestamp + 1),
        target=target,
        nonce=0,
        height=height,
        epoch=height // 10_000,
    )
    block = Block(header, txs)
    block.header.merkle_root = block.calculate_merkle_root()
    return mine_cpu(block)


def assert_ok(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print(f"  OK  {msg}")


def run():
    print("Running Ur Coin consensus tests (CPU)...")
    tmp = tempfile.mkdtemp(prefix="urc_test_")
    db = os.path.join(tmp, "chain.db")
    wallet_path = os.path.join(tmp, "w.json")
    os.environ["URCOIN_WALLET_PASSWORD"] = "test-password"
    os.environ["URCOIN_TEST_MODE"] = "1"

    storage = BlockchainStorage(db)
    assert_ok(storage.get_best_height() == 0, "genesis is height 0")
    assert_ok(storage.get_best_block().hash == GENESIS_BLOCK.hash, "genesis hash matches")

    miner = Wallet.create_or_load(wallet_path)
    other = Wallet()

    # Valid block
    b1 = make_block(storage, miner.address)
    ok, msg = storage.accept_block(b1)
    assert_ok(ok, f"valid block accepted ({msg})")

    # Wrong merkle
    b_bad = make_block(storage, miner.address)
    b_bad.header.merkle_root = "00" * 32
    ok, msg = storage.accept_block(b_bad)
    assert_ok(not ok, f"wrong merkle rejected: {msg}")

    # Oversized coinbase
    parent = storage.get_best_block()
    height = parent.header.height + 1
    fat = Transaction.create_coinbase(miner.address, 999 * 100_000_000, height)
    header = BlockHeader(
        version=1,
        prev_hash=parent.hash,
        merkle_root="",
        timestamp=parent.header.timestamp + 1,
        target=MAX_TARGET,
        nonce=0,
        height=height,
        epoch=0,
    )
    fat_block = Block(header, [fat])
    fat_block.header.merkle_root = fat_block.calculate_merkle_root()
    fat_block = mine_cpu(fat_block)
    ok, msg = storage.accept_block(fat_block)
    assert_ok(not ok, f"oversize coinbase rejected: {msg}")

    # Spend missing utxo
    fake_tx = other.create_transaction(
        miner.address,
        1,
        [{"txid": "ab" * 32, "vout": 0, "amount": 50 * 100_000_000, "recipient": other.address}],
    )
    # create_transaction signs; the utxo is fake so connect should fail
    ok, msg = storage.accept_block(make_block(storage, miner.address, extra_txs=[fake_tx]))
    assert_ok(not ok, f"fake spend rejected: {msg}")

    # RPC cookie length sanity: unauthorized path is covered in rpc handler
    from urcoin.auth import load_or_create_rpc_cookie
    cookie = load_or_create_rpc_cookie(os.path.join(tmp, "c.cookie"))
    assert_ok(len(cookie) == 64, "rpc cookie created")

    print("\nAll consensus tests passed.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(run())
    except Exception as e:
        print(f"\nFAILED: {e}")
        sys.exit(1)
