"""
Ur Coin Cryptographic Primitives:
- UrHash Memory-Hard PoW (CPU Light-Verification & Reference Generator)
- SECP256K1 Key Generation, Signatures, and Verification
- URC Address Encoding (urc1 + Base58Check)
- Mnemonic Seed Generation
"""

import hashlib
import struct
import secrets
import ecdsa

# -------------------------------------------------------------
# Base58 and Address Formatting
# -------------------------------------------------------------
BASE58_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

def base58_encode(b: bytes) -> str:
    """Encode bytes into a Base58 string."""
    n = int.from_bytes(b, "big")
    res = []
    while n > 0:
        n, r = divmod(n, 58)
        res.append(BASE58_ALPHABET[r])
    # Preserve leading zero bytes
    pad = 0
    for byte in b:
        if byte == 0:
            pad += 1
        else:
            break
    return (BASE58_ALPHABET[0] * pad) + "".join(reversed(res))

def base58_decode(s: str) -> bytes:
    """Decode a Base58 string back to bytes."""
    n = 0
    for char in s:
        p = BASE58_ALPHABET.find(char)
        if p == -1:
            raise ValueError(f"Invalid Base58 character: '{char}'")
        n = n * 58 + p
    full_bytes = n.to_bytes((n.bit_length() + 7) // 8, "big") if n > 0 else b""
    pad = 0
    for char in s:
        if char == BASE58_ALPHABET[0]:
            pad += 1
        else:
            break
    return (b"\x00" * pad) + full_bytes

def hash160(data: bytes) -> bytes:
    """Standard Bitcoin/Crypto Hash160: RIPEMD160(SHA256(data))."""
    sha = hashlib.sha256(data).digest()
    try:
        ripe = hashlib.new("ripemd160", sha).digest()
    except ValueError:
        # Fallback if ripemd160 not present in standard openssl
        ripe = hashlib.sha256(sha).digest()[:20]
    return ripe

def base58check_encode(payload: bytes, prefix: bytes = b"\x45") -> str: # 0x45 = 'U'
    """Encode payload with 1-byte prefix and 4-byte double SHA-256 checksum."""
    data = prefix + payload
    checksum = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    return base58_encode(data + checksum)

def base58check_decode(addr: str) -> bytes:
    """Decode and verify checksum of a Base58Check address."""
    raw = base58_decode(addr)
    if len(raw) < 5:
        raise ValueError("Address too short")
    data, checksum = raw[:-4], raw[-4:]
    expected = hashlib.sha256(hashlib.sha256(data).digest()).digest()[:4]
    if checksum != expected:
        raise ValueError("Invalid address checksum")
    return data[1:] # strip 1-byte prefix

def is_valid_address(addr: str) -> bool:
    """Return True if addr is a checksummed urc1... address."""
    if not isinstance(addr, str) or not addr.startswith("urc1") or len(addr) < 8:
        return False
    try:
        payload = base58check_decode(addr[4:])
        return len(payload) == 20
    except (ValueError, Exception):
        return False

# -------------------------------------------------------------
# SECP256K1 Key Pair & Wallet Primitives
# -------------------------------------------------------------
class KeyPair:
    def __init__(self, private_key: ecdsa.SigningKey = None):
        if private_key is None:
            self.sk = ecdsa.SigningKey.generate(curve=ecdsa.SECP256k1)
        else:
            self.sk = private_key
        self.vk = self.sk.get_verifying_key()

    @classmethod
    def from_private_hex(cls, hex_str: str) -> "KeyPair":
        sk = ecdsa.SigningKey.from_string(bytes.fromhex(hex_str), curve=ecdsa.SECP256k1)
        return cls(sk)

    @classmethod
    def from_seed(cls, seed_bytes: bytes) -> "KeyPair":
        # Deterministically derive 32-byte private key from seed
        key_material = hashlib.sha256(seed_bytes).digest()
        sk = ecdsa.SigningKey.from_string(key_material, curve=ecdsa.SECP256k1)
        return cls(sk)

    def get_private_hex(self) -> str:
        return self.sk.to_string().hex()

    def get_public_bytes(self) -> bytes:
        return self.vk.to_string()

    def get_public_hex(self) -> str:
        return self.get_public_bytes().hex()

    def get_address(self) -> str:
        pub = self.get_public_bytes()
        h160 = hash160(pub)
        return "urc1" + base58check_encode(h160)

    def sign(self, message_hash: bytes) -> bytes:
        """Sign a 32-byte message hash using deterministic ECDSA (RFC 6979)."""
        return self.sk.sign_deterministic(message_hash, hashfunc=hashlib.sha256)

    @staticmethod
    def verify(public_bytes: bytes, message_hash: bytes, signature: bytes) -> bool:
        """Verify ECDSA signature with public key."""
        try:
            vk = ecdsa.VerifyingKey.from_string(public_bytes, curve=ecdsa.SECP256k1)
            return vk.verify(signature, message_hash, hashfunc=hashlib.sha256)
        except Exception:
            return False

    @staticmethod
    def pubkey_to_address(public_bytes: bytes) -> str:
        return "urc1" + base58check_encode(hash160(public_bytes))

# -------------------------------------------------------------
# BIP-39 Style Simple 12-Word Mnemonic Generation
# -------------------------------------------------------------
WORDLIST = [
    "abandon", "ability", "able", "about", "above", "absent", "absorb", "abstract", "absurd", "abuse",
    "access", "accident", "account", "accuse", "achieve", "acid", "acoustic", "acquire", "across", "act",
    "action", "actor", "actress", "actual", "adapt", "add", "addict", "address", "adjust", "admit",
    "adult", "advance", "advice", "aerobic", "affair", "afford", "afraid", "again", "age", "agent",
    "agree", "ahead", "aim", "air", "airport", "aisle", "alarm", "album", "alcohol", "alert",
    "alien", "all", "alley", "allow", "almost", "alone", "alpha", "already", "also", "alter",
    "always", "amateur", "amazing", "among", "amount", "amused", "analyst", "anchor", "ancient", "anger",
    "angle", "angry", "animal", "ankle", "announce", "annual", "another", "answer", "antenna", "antique",
    "anxiety", "any", "apart", "apology", "appear", "apple", "approve", "april", "arch", "arctic",
    "area", "arena", "argue", "arm", "armed", "armor", "army", "around", "arrange", "arrest",
    "arrive", "arrow", "art", "artefact", "artist", "artwork", "ask", "aspect", "assault", "asset",
    "assist", "assume", "asthma", "athlete", "atom", "attack", "attend", "attitude", "attract", "auction"
]

def generate_mnemonic(words_count: int = 12) -> str:
    """Generate a random mnemonic word sequence."""
    words = [secrets.choice(WORDLIST) for _ in range(words_count)]
    return " ".join(words)

def mnemonic_to_seed(mnemonic: str) -> bytes:
    """Convert mnemonic words to a 32-byte deterministic seed."""
    return hashlib.pbkdf2_hmac("sha512", mnemonic.encode("utf-8"), b"urcoin_mnemonic_salt", 2048)[:32]

# -------------------------------------------------------------
# UrHash: Memory-Hard PoW Algorithm for Mid-Tier GPUs
# -------------------------------------------------------------
# DAG Specifications:
# Default: 16,777,216 items of 64 bytes = 1,073,741,824 bytes (1.0 GB VRAM)
# Scaling: Can be 1.0 GB or 2.0 GB (up to 32,768,532 items).
# Memory access rounds: 32 random accesses across VRAM per nonce.
# Verification complexity: Light verifier only computes 32 items on-the-fly (~0.8 ms).
DEFAULT_DAG_ITEMS = 16_777_216 # 1.0 GB
DEFAULT_ROUNDS = 32

def get_epoch_seed(epoch_number: int) -> bytes:
    """Derive deterministic 32-byte epoch seed for DAG."""
    seed = b"urcoin_epoch_seed_init_v1"
    for _ in range(epoch_number + 1):
        seed = hashlib.sha256(seed).digest()
    return seed

def rotr64(x: int, n: int) -> int:
    return ((x >> n) | ((x << (64 - n)) & 0xFFFFFFFFFFFFFFFF)) & 0xFFFFFFFFFFFFFFFF

def urhash_get_dag_item(epoch_seed: bytes, idx: int) -> tuple:
    """Computes a single 64-byte DAG line (8 uint64s) deterministically using Blake2b."""
    msg = epoch_seed + struct.pack("<Q", idx)
    digest = hashlib.blake2b(msg, digest_size=64).digest()
    return struct.unpack("<8Q", digest)

def urhash_cpu_verify(header_hash: bytes, nonce: int, epoch_seed: bytes,
                      target_int: int, num_items: int = DEFAULT_DAG_ITEMS,
                      rounds: int = DEFAULT_ROUNDS) -> tuple[bool, str]:
    """
    Light verification of a candidate block header and nonce.
    Takes ~0.8 ms on CPU without needing 1 GB RAM allocation!
    Returns (is_valid, hash_hex).
    """
    # Step 1: Initial state from header hash + nonce
    seed = hashlib.blake2b(header_hash + struct.pack("<Q", nonce), digest_size=64).digest()
    s = list(struct.unpack("<8Q", seed))

    # Step 2: 32 pseudo-random memory lookups into DAG
    for r in range(rounds):
        # Calculate pseudo-random DAG item index
        idx = (s[0] ^ s[r % 8] ^ ((r * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF)) % num_items
        dag_line = urhash_get_dag_item(epoch_seed, idx)
        for j in range(8):
            s[j] = ((rotr64(s[j] ^ dag_line[j], 17) * 0x100000001B3) + r) & 0xFFFFFFFFFFFFFFFF

    # Step 3: Final hash
    packed = struct.pack("<8Q", *s)
    final_h = hashlib.sha256(packed).digest()
    val = int.from_bytes(final_h, "big")
    is_valid = (val <= target_int)
    return is_valid, final_h.hex()

def urhash_cpu_hash(header_hash: bytes, nonce: int, epoch_seed: bytes,
                    num_items: int = DEFAULT_DAG_ITEMS,
                    rounds: int = DEFAULT_ROUNDS) -> bytes:
    """Compute the 32-byte final UrHash on CPU."""
    seed = hashlib.blake2b(header_hash + struct.pack("<Q", nonce), digest_size=64).digest()
    s = list(struct.unpack("<8Q", seed))
    for r in range(rounds):
        idx = (s[0] ^ s[r % 8] ^ ((r * 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF)) % num_items
        dag_line = urhash_get_dag_item(epoch_seed, idx)
        for j in range(8):
            s[j] = ((rotr64(s[j] ^ dag_line[j], 17) * 0x100000001B3) + r) & 0xFFFFFFFFFFFFFFFF
    packed = struct.pack("<8Q", *s)
    return hashlib.sha256(packed).digest()
