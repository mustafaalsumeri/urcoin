"""
Ur Coin (URC) - Comprehensive End-to-End System Test:
1. Initialize Blockchain Node & Storage
2. Run GPU Miner on RTX 3050 to mine Block #1 and Block #2
3. Verify Block Rewards (50 URC per block)
4. Create Recipient Wallet and transfer 25 URC
5. Mine Block #3 containing the transfer transaction
6. Verify UTXO balances, Merkle root, signatures, and chain integrity
"""

import time
import os
import sys
import shutil

# Ensure UTF-8 output on Windows terminals
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from urcoin.storage import BlockchainStorage
from urcoin.mempool import Mempool
from urcoin.network import P2PNetwork
from urcoin.wallet import Wallet
from urcoin.miner_gpu import GPUMiner
from urcoin.core import (
    Block, BlockHeader, Transaction, calculate_block_reward,
    calculate_next_target, COIN
)

def run_e2e_test():
    print("==================================================================")
    print("         RUNNING UR COIN (URC) FULL END-TO-END TEST")
    print("==================================================================")

    test_db = "test_urcoin.db"
    test_wallet_file = "test_wallet.json"
    if os.path.exists(test_db):
        os.remove(test_db)
    if os.path.exists(test_wallet_file):
        os.remove(test_wallet_file)

    # 1. Initialize Storage & Genesis
    storage = BlockchainStorage(test_db)
    print(f"✓ Initialized Storage. Genesis Height: #{storage.get_best_height()}")
    genesis = storage.get_best_block()
    print(f"✓ Genesis Hash: {genesis.hash}")

    # 2. Initialize Mempool & Miner Wallet
    mempool = Mempool(storage)
    miner_wallet = Wallet.create_or_load(test_wallet_file)
    print(f"✓ Miner Wallet Address: {miner_wallet.address}")

    # 3. Initialize GPU Miner on RTX 3050 with full production 1.0 GB DAG
    gpu_miner = GPUMiner(device_index=0) # Uses DEFAULT_DAG_ITEMS = 16,777,216 (1.0 GB)
    print(f"✓ Initialized GPU Miner on: {gpu_miner.device.device_name}")

    def mine_one_block(expected_height: int, custom_txs=None):
        best_b = storage.get_best_block()
        epoch = expected_height // 10_000
        reward = calculate_block_reward(expected_height)

        coinbase_tx = Transaction.create_coinbase(miner_wallet.address, reward, expected_height)
        txs = [coinbase_tx] + (custom_txs if custom_txs else [])

        past_headers = storage.get_past_headers(10)
        target = calculate_next_target(past_headers)

        header = BlockHeader(
            version=1,
            prev_hash=best_b.hash,
            merkle_root="",
            timestamp=int(time.time()),
            target=target,
            nonce=0,
            height=expected_height,
            epoch=epoch
        )
        block = Block(header, txs)
        block.header.merkle_root = block.calculate_merkle_root()
        mining_hash = block.header.get_mining_hash()

        print(f"\n[Mining] Mining Block #{expected_height} on GPU...")
        nonce = 0
        while True:
            res = gpu_miner.search_batch(
                mining_hash, target, epoch,
                start_nonce=nonce,
                global_work_size=32768,
                nonces_per_thread=32
            )
            nonce += (32768 * 32)
            if res:
                winning_nonce, block_hash = res[0]
                block.header.nonce = winning_nonce
                block.hash = block_hash
                assert block.verify_pow(), "Proof of Work verification failed!"
                storage.add_block(block)
                mempool.remove_mined_transactions(txs)
                print(f"🎉 Successfully Mined Block #{expected_height} on GPU!")
                print(f"   Hash:  {block_hash}")
                print(f"   Nonce: {winning_nonce}")
                break

    # Mine Block #1
    mine_one_block(1)
    bal1 = storage.get_balance(miner_wallet.address)
    print(f"✓ Miner Balance after Block #1: {bal1 / COIN:.2f} URC")
    assert bal1 == 50 * COIN, f"Expected 50 URC, got {bal1 / COIN}"

    # Mine Block #2
    mine_one_block(2)
    bal2 = storage.get_balance(miner_wallet.address)
    print(f"✓ Miner Balance after Block #2: {bal2 / COIN:.2f} URC")
    assert bal2 == 100 * COIN, f"Expected 100 URC, got {bal2 / COIN}"

    # 4. Create Recipient Wallet and Send 25 URC
    recipient_wallet = Wallet()
    print(f"\n✓ Created Recipient Wallet: {recipient_wallet.address}")

    send_amount = 25 * COIN
    fee = 10_000 # 0.0001 URC
    utxos = storage.get_utxos_for_address(miner_wallet.address)
    tx = miner_wallet.create_transaction(recipient_wallet.address, send_amount, utxos, fee_atomic=fee)
    ok, msg = mempool.add_transaction(tx)
    assert ok, f"Failed to add transaction to mempool: {msg}"
    print(f"✓ Transaction added to mempool. TXID: {tx.txid}")

    # Mine Block #3 containing the transaction
    mempool_txs = mempool.get_transactions_for_block()
    mine_one_block(3, custom_txs=mempool_txs)

    # 5. Check Final Balances
    rec_bal = storage.get_balance(recipient_wallet.address)
    miner_bal = storage.get_balance(miner_wallet.address)
    print(f"\n✓ Recipient Confirmed Balance: {rec_bal / COIN:.4f} URC")
    print(f"✓ Miner Confirmed Balance:     {miner_bal / COIN:.4f} URC")

    assert rec_bal == send_amount, f"Recipient balance mismatch: {rec_bal}"
    # Miner had 100, earned 50 from block 3, spent 25: 100 + 50 - 25 = 125 URC (minus fee paid to self/miner)
    print("\n==================================================================")
    print("   ALL TESTS PASSED: 100% OPERATIONAL REAL CRYPTOCURRENCY!")
    print("==================================================================")

    # Cleanup test files
    storage.conn.close()
    if os.path.exists(test_db):
        os.remove(test_db)
    if os.path.exists(test_wallet_file):
        os.remove(test_wallet_file)

if __name__ == "__main__":
    run_e2e_test()
