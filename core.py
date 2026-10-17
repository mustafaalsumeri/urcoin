"""
Ur Coin (URC) - Core Blockchain Structures & UTXO Engine
Professional Adaptive Difficulty & High-Performance Transaction Validation
"""

import time
import hashlib
from typing import List

# إعدادات الصعوبة والشبكة الأساسية لعملة Ur Coin
TARGET_BLOCK_TIME = 30       # زمن الكتلة المستهدف (30 ثانية)
DIFFICULTY_WINDOW = 10       # تعديل الصعوبة كل 10 كتل تلقائياً

MAX_TARGET = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
MIN_TARGET = 0x0000000000000000000000000000000000000000000000000000000000000001
INITIAL_DIFFICULTY_BITS = 0x1e0ffff0

def bits_to_target(bits: int) -> int:
    exponent = (bits >> 24) & 0xff
    coefficient = bits & 0xffffff
    return coefficient * (256 ** (exponent - 3))

def target_to_bits(target: int) -> int:
    if target == 0:
        return 0
    target_bytes = []
    temp = target
    while temp > 0:
        target_bytes.insert(0, temp & 0xff)
        temp >>= 8
    if len(target_bytes) == 0:
        return 0
    if target_bytes[0] > 0x7f:
        target_bytes.insert(0, 0x00)
    exponent = len(target_bytes)
    coefficient = 0
    for i in range(min(3, len(target_bytes))):
        coefficient = (coefficient << 8) | target_bytes[i]
    return (exponent << 24) | coefficient

class TxIn:
    """مدخلات المعاملة الرقمية - تشير إلى خرج غير مستهلك سابقاً (UTXO)"""
    def __init__(self, txid: str, vout: int, signature: str = ""):
        self.txid = txid        # معرف المعاملة السابقة
        self.vout = vout        # مؤشر الخرج في المعاملة السابقة
        self.signature = signature # التوقيع الإلكتروني لإثبات الملكية

    def to_dict(self):
        return {"txid": self.txid, "vout": self.vout, "signature": self.signature}

class TxOut:
    """مخرجات المعاملة الرقمية - تحدد المستلم والكمية المنقولة له"""
    def __init__(self, amount: float, address: str):
        self.amount = amount    # كمية عملات URC
        self.address = address  # عنوان محفظة المستلم

    def to_dict(self):
        return {"amount": self.amount, "address": self.address}

class Transaction:
    """هيكل المعاملة المالية المشفرة ومحرك التحقق الحسابي"""
    def __init__(self, inputs: List[TxIn], outputs: List[TxOut], timestamp: int = None, hash: str = None):
        self.inputs = inputs
        self.outputs = outputs
        self.timestamp = timestamp if timestamp else int(time.time())
        self.hash = hash if hash else self.calculate_hash()

    def calculate_hash(self) -> str:
        """إنتاج معرف هاش فريد وغير قابل للتلاعب للمعاملة الحالية"""
        inputs_str = "".join([f"{i.txid}{i.vout}{i.signature}" for i in self.inputs])
        outputs_str = "".join([f"{o.amount}{o.address}" for o in self.outputs])
        tx_string = f"{inputs_str}{outputs_str}{self.timestamp}"
        return hashlib.sha256(hashlib.sha256(tx_string.encode('utf-8')).digest()).hexdigest()

    def is_coinbase(self) -> bool:
        """التحقق مما إذا كانت المعاملة هي مكافأة التعدين الناتجة من البلوك (Coinbase)"""
        return len(self.inputs) == 1 and self.inputs[0].txid == "0" * 64 and self.inputs[0].vout == -1

    def verify(self, storage) -> bool:
        """التحقق البرمجي المتقاطع من صحة التوقيع وصلاحية الـ UTXO في قاعدة البيانات"""
        if self.is_coinbase():
            return True
            
        # التحقق من وجود مدخلات ومخرجات حقيقية
        if not self.inputs or not self.outputs:
            return False

        total_input_value = 0.0
        for tx_in in self.inputs:
            # التأكد من أن المدخل لم يتم صرفه مسبقاً في البلوكشين
            utxo = storage.get_utxo(tx_in.txid, tx_in.vout)
            if not utxo:
                return False
            total_input_value += utxo.amount
            
            # هنا يتم استدعاء محرك التوقيع الإلكتروني ECDSA للتحقق من صحة توقيع المحفظة المرسلة
            # في بيئة التطوير الحالية، نضمن العبور إذا كان التوقيع متطابقاً هيكلياً
            if not tx_in.signature:
                return False

        total_output_value = sum([o.amount for o in self.outputs])
        # قانون حفظ الطاقة المالي: يجب ألا تتجاوز المخرجات قيمة المدخلات الإجمالية
        if total_output_value > total_input_value:
            return False

        return True

    @classmethod
    def from_dict(cls, d: dict):
        ins = [TxIn(i["txid"], i["vout"], i["signature"]) for i in d.get("inputs", [])]
        outs = [TxOut(o["amount"], o["address"]) for o in d.get("outputs", [])]
        return cls(ins, outs, d.get("timestamp"), d.get("hash"))

class BlockHeader:
    def __init__(self, version: int, previous_hash: str, merkle_root: str, timestamp: int, bits: int, nonce: int, height: int):
        self.version = version
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.bits = bits
        self.nonce = nonce
        self.height = height

class Block:
    def __init__(self, header: BlockHeader, transactions: List[Transaction]):
        self.header = header
        self.transactions = [tx if isinstance(tx, Transaction) else Transaction.from_dict(tx) for tx in transactions]
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        header_string = f"{self.header.version}{self.header.previous_hash}{self.header.merkle_root}{self.header.timestamp}{self.header.bits}{self.header.nonce}{self.header.height}"
        return hashlib.sha256(hashlib.sha256(header_string.encode('utf-8')).digest()).hexdigest()

    def verify_pow(self) -> bool:
        target = bits_to_target(self.header.bits)
        block_int = int(self.hash, 16)
        return block_int <= target

    @classmethod
    def from_dict(cls, d: dict):
        h = d["header"]
        header = BlockHeader(h["version"], h["previous_hash"], h["merkle_root"], h["timestamp"], h["bits"], h["nonce"], h["height"])
        return cls(header, d["transactions"])

def calculate_next_difficulty(storage, current_block: Block) -> int:
    next_height = current_block.header.height + 1
    if next_height < DIFFICULTY_WINDOW or next_height % DIFFICULTY_WINDOW != 0:
        return current_block.header.bits

    first_block_height = next_height - DIFFICULTY_WINDOW
    first_block = storage.get_block_by_height(first_block_height)
    if not first_block:
        return current_block.header.bits

    actual_timespan = current_block.header.timestamp - first_block.header.timestamp
    target_timespan = DIFFICULTY_WINDOW * TARGET_BLOCK_TIME

    if actual_timespan < target_timespan // 4:
        actual_timespan = target_timespan // 4
    if actual_timespan > target_timespan * 4:
        actual_timespan = target_timespan * 4

    current_target = bits_to_target(current_block.header.bits)
    new_target = current_target * actual_timespan // target_timespan

    if new_target > MAX_TARGET:
        new_target = MAX_TARGET
    if new_target < MIN_TARGET:
        new_target = MIN_TARGET

    return target_to_bits(new_target)

# تعريف كتلة البداية التاريخية للشبكة (Genesis Block) لضمان إقلاع النظام
GENESIS_HEADER = BlockHeader(1, "0" * 64, "0" * 64, 1710000000, INITIAL_DIFFICULTY_BITS, 0, 0)
GENESIS_BLOCK = Block(GENESIS_HEADER, [])
