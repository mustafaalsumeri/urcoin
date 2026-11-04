"""
Local RPC cookie and wallet-password helpers.
Cookie/password files stay on this computer and are gitignored.
"""

import os
import secrets
from typing import Optional

# Absolute base directory of the Ur Coin installation
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_COOKIE_PATH = os.path.join(BASE_DIR, "urcoin.cookie")
DEFAULT_WALLET_PASS_PATH = os.path.join(BASE_DIR, "urcoin.walletpass")
RPC_COOKIE_HEADER = "X-Urcoin-Rpc-Cookie"


def load_or_create_secret_file(path: str, nbytes: int = 32) -> str:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            token = f.read().strip()
        if token:
            return token
    token = secrets.token_hex(nbytes)
    with open(path, "w", encoding="utf-8") as f:
        f.write(token)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def load_or_create_rpc_cookie(path: str = DEFAULT_COOKIE_PATH) -> str:
    return load_or_create_secret_file(path)


def read_rpc_cookie(path: str = DEFAULT_COOKIE_PATH) -> Optional[str]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        token = f.read().strip()
    return token or None


def get_wallet_password(pass_path: str = DEFAULT_WALLET_PASS_PATH) -> str:
    env = os.environ.get("URCOIN_WALLET_PASSWORD")
    if env:
        return env
    return load_or_create_secret_file(pass_path)
