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
from urcoin.auth import RPC_COOKIE_HEADER, read_rpc_cookie

DEFAULT_NODE_URL = "http://127.0.0.1:9334"

def rpc(endpoint: str, data: dict = None, node_url: str = DEFAULT_NODE_URL) -> dict:
    url = f"{node_url.rstrip('/')}{endpoint}"
    headers = {}
    cookie = read_rpc_cookie()
    if cookie:
        headers[RPC_COOKIE_HEADER] = cookie
    if data is not None:
        payload = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=payload, headers=headers)
    else:
        req = urllib.request.Request(url, headers=headers)
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

    # Command: ticker
    subparsers.add_parser("ticker", help="Get live URC/USDT market price and 24h statistics")

    # Command: orderbook
    subparsers.add_parser("orderbook", help="View current market depth (Bids & Asks)")

    # Command: trade
    p_trade = subparsers.add_parser("trade", help="Place a Buy or Sell order on UrDEX")
    p_trade.add_argument("side", choices=["buy", "sell", "BUY", "SELL"], help="BUY or SELL")
    p_trade.add_argument("price", type=float, help="Price in USDT")
    p_trade.add_argument("amount", type=float, help="Amount in URC")

    # Command: swap
    p_swap = subparsers.add_parser("swap", help="Instant market swap between URC and USDT")
    p_swap.add_argument("from_asset", choices=["urc", "usdt", "URC", "USDT"], help="Asset to pay")
    p_swap.add_argument("amount", type=float, help="Amount to swap")

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

    elif args.command == "ticker":
        res = rpc("/api/exchange/ticker", node_url=args.node)
        print("--- UrDEX Market Ticker (URC/USDT) ---")
        print(f"Last Price:       ${res['last_price']:.4f} USDT")
        print(f"24h Change:       {res['change_24h_pct']:+.2f}%")
        print(f"24h High / Low:   ${res['high_24h']:.4f} / ${res['low_24h']:.4f}")
        print(f"24h Volume (URC): {res['volume_urc_24h']:,.2f} URC")
        print(f"24h Volume (USD): ${res['volume_usdt_24h']:,.2f}")

    elif args.command == "orderbook":
        res = rpc("/api/exchange/orderbook", node_url=args.node)
        print("=== UrDEX LIVE ORDER BOOK (URC/USDT) ===")
        print("\n--- ASKS (SELL ORDERS) ---")
        print(f"{'Price (USDT)':<14} {'Amount (URC)':<14} {'Total (USDT)':<14}")
        print("-" * 42)
        for a in reversed(res.get("asks", [])[:5]):
            print(f"${a['price']:<13.4f} {a['amount']:<14.2f} ${a['total']:<13.2f}")

        print("\n--- BIDS (BUY ORDERS) ---")
        print(f"{'Price (USDT)':<14} {'Amount (URC)':<14} {'Total (USDT)':<14}")
        print("-" * 42)
        for b in res.get("bids", [])[:5]:
            print(f"${b['price']:<13.4f} {b['amount']:<14.2f} ${b['total']:<13.2f}")

    elif args.command == "trade":
        wallet = Wallet.create_or_load(args.wallet)
        side = args.side.upper()
        res = rpc("/api/exchange/order", {
            "side": side,
            "price": args.price,
            "amount": args.amount,
            "creator_address": wallet.address
        }, node_url=args.node)
        if res.get("success"):
            order = res["order"]
            print(f"✓ Placed {side} Order #{order['order_id'][:8]} successfully!")
            print(f"  Price:  ${order['price']:.4f} USDT")
            print(f"  Amount: {order['amount']:.2f} URC")
            print(f"  Filled: {order['filled']:.2f} URC (Status: {order['status']})")
        else:
            print(f"Order failed: {res.get('error')}")

    elif args.command == "swap":
        wallet = Wallet.create_or_load(args.wallet)
        from_asset = args.from_asset.upper()
        to_asset = "USDT" if from_asset == "URC" else "URC"
        res = rpc("/api/exchange/swap", {
            "from_asset": from_asset,
            "to_asset": to_asset,
            "amount_in": args.amount,
            "creator_address": wallet.address
        }, node_url=args.node)
        if res.get("success"):
            s = res["swap"]
            print(f"🎉 Swap executed! Converted {s['amount_in']:.4f} {from_asset} -> {s['amount_out']:.4f} {to_asset} (Effective Price: ${s['effective_price']:.4f})")
        else:
            print(f"Swap failed: {res.get('error')}")

    else:
        parser.print_help()

if __name__ == "__main__":
    main()
