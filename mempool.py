"""
Ur Coin (URC) - Memory Pool (Mempool) Engine
Professional Version: Double-Spend Protection & Memory Flooding DoS Defense
"""

import threading
from typing import Dict, Set
from core import Transaction, Block

# فرض قيود صارمة لحماية موارد الخادم السحابي والذاكرة العشوائية
MAX_MEMPOOL_TRANSACTIONS = 5000  # الحد الأقصى للمعاملات المعلقة في الطابور
MAX_TX_SIZE_BYTES = 102400       # الحد الأقصى لحجم المعاملة الواحدة (100 كيلوبايت)

class Mempool:
    def __init__(self, storage):
        self.storage = storage
        self.transactions: Dict[str, Transaction] = {}  # جدول المعاملات المعلقة بمفتاح الـ Hash
        self.mempool_lock = threading.Lock()           # قفل حماية لمنع تداخل عمليات الإضافة والحذف
        
        # 🟥 خط الدفاع الأول: مصفوفة سريعة لتعقب مخارج الـ UTXO الجاري استهلاكها حالياً في الذاكرة
        self.spent_inputs_tracker: Set[str] = set()

    def add_transaction(self, tx: Transaction) -> bool:
        """
        إضافة معاملة جديدة للميمبول بأمان بعد فحصها ضد هجمات الإنفاق المزدوج والإغراق.
        """
        # 1. التحقق من حجم المعاملة لحماية الرام من ملفات البيانات الضخمة
        tx_string = str(tx.__dict__)
        if len(tx_string.encode('utf-8')) > MAX_TX_SIZE_BYTES:
            print(f"[Mempool] Rejected: Transaction {tx.hash[:16]}... size exceeds maximum limit.")
            return False

        with self.mempool_lock:
            # 2. التحقق من السعة القصوى للميمبول
            if len(self.transactions) >= MAX_MEMPOOL_TRANSACTIONS:
                print("[Mempool] Warning: Mempool is full! Rejecting incoming transactions.")
                return False

            # 3. منع التكرار إذا كانت المعاملة موجودة بالفعل
            if tx.hash in self.transactions:
                return True

            # 4. 🟥 فحص الحماية ضد الإنفاق المزدوج المعلق (Double-Spend Audit)
            # نقوم ببناء معرف فريد لكل مدخل لمعاملة للتأكد من عدم وجود معاملة أخرى تطالب به
            temp_spent_set = set()
            for tx_in in tx.inputs:
                input_key = f"{tx_in.txid}:{tx_in.vout}"
                
                # إذا وجدنا أن هذا المدخل محجوز بالفعل لمعاملة معلقة أخرى، نرفض المعاملة فوراً
                if input_key in self.spent_inputs_tracker:
                    print(f"[Mempool] Security Alert: Rejected Double-Spend attempt for input {input_key} in Tx {tx.hash[:16]}...")
                    return False
                temp_spent_set.add(input_key)

            # 5. التحقق من صحة المعاملة من قاعدة بيانات البلوكشين (صلاحية الـ UTXO الحقيقي والتوقيع)
            if not tx.verify(self.storage):
                print(f"[Mempool] Rejected: Signature or UTXO verification failed for Tx {tx.hash[:16]}...")
                return False

            # 6. إذا مرت المعاملة من كل الفحوصات بأمان، نقوم بتسجيلها وحجز مدخلاتها في الذاكرة
            self.transactions[tx.hash] = tx
            self.spent_inputs_tracker.update(temp_spent_set)
            print(f"[Mempool] Accepted Transaction {tx.hash[:16]}... Total pending: {len(self.transactions)}")
            return True

    def remove_mined_transactions(self, block_transactions: list):
        """
        تنظيف الميمبول تلقائياً وحذف المعاملات التي تم تضمينها وتأكيدها بالفعل داخل كتلة جديدة ومقبولة.
        """
        with self.mempool_lock:
            for tx in block_transactions:
                # إذا كانت المعاملة المؤكدة موجودة في الميمبول، نحذفها
                if tx.hash in self.transactions:
                    del self.transactions[tx.hash]
                
                # فك حجز المدخلات المربوطة بها من مصفوفة التتبع لأنها استهلكت رسمياً في البلوكشين
                for tx_in in tx.inputs:
                    input_key = f"{tx_in.txid}:{tx_in.vout}"
                    self.spent_inputs_tracker.discard(input_key)

    def get_pending_transactions(self) -> list:
        """جلب قائمة المعاملات المعلقة لتمريرها للمعدّن عند بناء كتلة جديدة"""
        with self.mempool_lock:
            return list(self.transactions.values())
