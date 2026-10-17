"""
Ur Coin (URC) - Core Blockchain Structures & UTXO Engine
Professional Adaptive Difficulty Version (Dynamic UrHash-v1 Retargeting)
"""

import time
import hashlib
from typing import List

# إعدادات الصعوبة والشبكة الأساسية المعرفة في مواصفات العملة
TARGET_BLOCK_TIME = 30       # زمن الكتلة المستهدف (30 ثانية)
DIFFICULTY_WINDOW = 10       # يتم إعادة ضبط الصعوبة كل 10 كتل تلقائياً

# قيم الحدود القصوى والدنيا للصعوبة لضمان عدم حدوث تجمّد للشبكة
MAX_TARGET = 0x000000FFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF
MIN_TARGET = 0x0000000000000000000000000000000000000000000000000000000000000001
INITIAL_DIFFICULTY_BITS = 0x1e0ffff0  # الصعوبة الأولية للشبكة

def bits_to_target(bits: int) -> int:
    """تحويل قيمة الـ Bits المضغوطة في رأس الكتلة إلى الرقم العشري المستهدف للصعوبة"""
    exponent = (bits >> 24) & 0xff
    coefficient = bits & 0xffffff
    return coefficient * (256 ** (exponent - 3))

def target_to_bits(target: int) -> int:
    """تحويل الرقم المستهدف العشري إلى صيغة Bits مضغوطة لتخزينها في الهيدر بأقل مساحة"""
    if target == 0:
        return 0
    target_bytes = []
    temp = target
    while temp > 0:
        target_bytes.insert(0, temp & 0xff)
        temp >>= 8
        
    if target_bytes[0] > 0x7f:
        target_bytes.insert(0, 0x00)
        
    exponent = len(target_bytes)
    coefficient = 0
    for i in range(min(3, len(target_bytes))):
        coefficient = (coefficient << 8) | target_bytes[i]
        
    if len(target_bytes) > 3:
        # إذا كانت المصفوفة أطول، نقوم بعملية زحزحة البتات للتوافق
        pass
        
    return (exponent << 24) | coefficient

class BlockHeader:
    def __init__(self, version: int, previous_hash: str, merkle_root: str, timestamp: int, bits: int, nonce: int, height: int):
        self.version = version
        self.previous_hash = previous_hash
        self.merkle_root = merkle_root
        self.timestamp = timestamp
        self.bits = bits          # تخزين قيمة الصعوبة الحالية المتغيرة
        self.nonce = nonce
        self.height = height

class Block:
    def __init__(self, header: BlockHeader, transactions: list):
        self.header = header
        self.transactions = transactions
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str:
        """حساب الهاش الفريد للكتلة بناءً على البيانات الأساسية الممررة في الهيدر"""
        header_string = f"{self.header.version}{self.header.previous_hash}{self.header.merkle_root}{self.header.timestamp}{self.header.bits}{self.header.nonce}{self.header.height}"
        return hashlib.sha256(hashlib.sha256(header_string.encode('utf-8')).digest()).hexdigest()

    def verify_pow(self) -> bool:
        """التحقق من أن الهاش المنتج من كارت الشاشة يطابق شرط الصعوبة المستهدفة فعلياً"""
        target = bits_to_target(self.header.bits)
        block_int = int(self.hash, 16)
        return block_int <= target


# 🟥 الخوارزمية الاحترافية المطورة لحساب الصعوبة التكيفية ديناميكياً
def calculate_next_difficulty(storage, current_block: Block) -> int:
    """
    تحسب وتضبط قيمة الصعوبة للكتلة القادمة بناءً على أداء الشبكة الحقيقي.
    تعتمد على قراءة آخر 10 كتل من الـ Storage وحساب الوقت المستغرق الفعلي.
    """
    next_height = current_block.header.height + 1
    
    # إذا كانت الشبكة في البداية ولم تصل للكتلة رقم 10، نلتزم بالصعوبة الأولية الافتراضية
    if next_height < DIFFICULTY_WINDOW or next_height % DIFFICULTY_WINDOW != 0:
        return current_block.header.bits

    # جلب الكتلة التي تقف عند بداية نافذة القياس (الكتلة الحالية - 10) بأمان من قاعدة البيانات
    first_block_height = next_height - DIFFICULTY_WINDOW
    first_block = storage.get_block_by_height(first_block_height)
    
    if not first_block:
        return current_block.header.bits

    # حساب الوقت الفعلي المستغرق لإنتاج الكتل العشرة الأخيرة بالفارق الزمني للـ Timestamps
    actual_timespan = current_block.header.timestamp - first_block.header.timestamp
    target_timespan = DIFFICULTY_WINDOW * TARGET_BLOCK_TIME  # المستهدف الصارم (300 ثانية)

    # حماية معمارية لمنع القفزات الجنونية في الصعوبة الناتجة عن تلاعب التوقيت (Timewarp Attack)
    # لا نسمح بزيادة الصعوبة أو خفضها بأكثر من 4 أضعاف في المرة الواحدة
    if actual_timespan < target_timespan // 4:
        actual_timespan = target_timespan // 4
    if actual_timespan > target_timespan * 4:
        actual_timespan = target_timespan * 4

    # معادلة التعديل الحسابية للـ Target العشري
    current_target = bits_to_target(current_block.header.bits)
    new_target = current_target * actual_timespan // target_timespan

    # التأكد من أن الهدف الجديد لا يتجاوز الحدود القصوى المسموح بها في معمارية البلوكشين
    if new_target > MAX_TARGET:
        new_target = MAX_TARGET
    if new_target < MIN_TARGET:
        new_target = MIN_TARGET

    return target_to_bits(new_target)
