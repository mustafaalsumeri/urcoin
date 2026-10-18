"""
Ur Coin (URC) - Command Line Interface (CLI)
Interact with your wallet and the Ur Coin blockchain network.
"""

import sys
import json
import argparse
import urllib.request

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

from urcoin.wallet import Wallet
from urcoin.core import COIN

DEFAULT_NODE_URL = "http://127.0.0.1:9334"

def rpc(endpoint: str, data: dict = None, node_url: str = DEFAULT_NODE_URL) -> dict:
    url = f"{node_url.rstrip('/')}{endpoint}"
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Error] Failed to connect to node at {node_url}: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Ur Coin (URC) Command Line Interface")
    parser.add_argument("--node", type=str, default=DEFAULT_NODE_URL, help="Node RPC URL")
    parser.add_argument("--wallet", type=str, default="urcoin_wallet.json", help="Wallet file path")

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Command: info
    subparsers.add_parser("info", help="Get blockchain node status")

    # Command: balance
    subparsers.add_parser("balance", help="Check wallet balance")

    # Command: address
    subparsers.add_parser("address", help="Show your wallet address")

    # Command: newwallet
    p_new = subparsers.add_parser("newwallet", help="Generate a new wallet with 12-word seed phrase")
    p_new.add_argument("--out", type=str, default="new_urcoin_wallet.json", help="Output file")

    # Command: send
    p_send = subparsers.add_parser("send", help="Send URC to an address")
    p_send.add_argument("recipient", type=str, help="Recipient urc1... address")
    p_send.add_argument("amount", type=float, help="Amount in URC")

    # Command: blocks
    subparsers.add_parser("blocks", help="List recent blocks")

    args = parser.parse_args()

    if args.command == "info":
        res = rpc("/api/info", node_url=args.node)
        print("--- Ur Coin Network Status ---")
        print(f"Current Height:     #{res['height']}")
        print(f"Best Block Hash:    {res['best_hash']}")
        print(f"Circulating Supply: {res['circulating_supply'] / COIN:.2f} URC")
        print(f"Current Reward:     {res['current_reward'] / COIN:.2f} URC")
        print(f"Target:             {res['target']}")
        print(f"Mempool Count:      {res['mempool_size']}")

    elif args.command == "balance":
        wallet = Wallet.create_or_load(args.wallet)
        res = rpc("/api/wallet", node_url=args.node)
        print(f"Wallet Address: {wallet.address}")
        print(f"Balance:        {res['balance'] / COIN:.8f} URC")

    elif args.command == "address":
        wallet = Wallet.create_or_load(args.wallet)
        print(f"Address: {wallet.address}")

    elif args.command == "newwallet":
        w = Wallet()
        w.save_to_file(args.out)
        print("Generated New Wallet:")
        print(f"Address:  {w.address}")
        print(f"Mnemonic: {w.mnemonic}")
        print(f"Saved to: {args.out}")

    elif args.command == "send":
        wallet = Wallet.create_or_load(args.wallet)
        res = rpc("/api/send_tx", {
            "recipient": args.recipient,
            "amount_urc": args.amount
        }, node_url=args.node)
        if res.get("success"):
            print(f"Successfully sent {args.amount} URC to {args.recipient}!")
            print(f"Transaction ID: {res['txid']}")
        else:
            print(f"Failed to send: {res.get('error')}")

    elif args.command == "blocks":
        blocks = rpc("/api/blocks", node_url=args.node)
        print(f"{'Height':<8} {'Block Hash':<48} {'Txs':<6} {'Nonce':<12}")
        print("-" * 76)
        for b in blocks:
            print(f"#{b['height']:<7} {b['hash']:<48} {b['tx_count']:<6} {b['nonce']:<12}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
