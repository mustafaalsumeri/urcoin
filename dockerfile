# 1. استخدام نظام تشغيل خفيف مجهز ببايثون 3.11 رسمياً
FROM python:3.11-slim

# 2. تحديد مجلد العمل الداخلي في الخادم
WORKDIR /app

# 3. تثبيت حزم التشفير الأساسية التي تحتاجها عملتك في نظام لينكس
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# 4. تثبيت مكتبة التشفير ecdsa التي قمنا بحقنها لحماية المحفظة
RUN pip install --no-cache-dir ecdsa

# 5. نسخ كافة ملفات عملتك المحدثة من GitHub إلى داخل الصندوق السحابي
COPY . .

# 6. تثبيت مسار البايثون المطلق لحل مشكلة ModuleNotFoundError نهائياً
ENV PYTHONPATH="/app"

# 7. فتح منافذ الشبكة للعامة (9333 للـ P2P و 9334 للمستكشف والـ RPC)
EXPOSE 9333
EXPOSE 9334

# 8. الأمر البرمجي النهائي لتشغيل عملتك فوراً في وضع الأمان العام الثابت
CMD ["python", "urcoind.py", "--public-node"]
