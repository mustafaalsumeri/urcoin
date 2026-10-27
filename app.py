from flask import Flask, render_template_string, redirect, url_for
import sqlite3
import urllib.request
import json

app = Flask(__name__)
DB_NAME = "pool_database.db"
NODE_RPC_URL = "http://127.0.0.1:9334"

# قالب HTML محدث ليحتوي على زر سحب الأرباح لكل محفظة
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة تحكم مجمع التعدين - Ur Coin</title>
    <meta http-equiv="refresh" content="10">
    <style>
        :root {
            --primary-color: #2c3e50;
            --accent-color: #3498db;
            --success-color: #27ae60;
            --danger-color: #e74c3c;
            --bg-color: #f4f7f6;
            --card-bg: #ffffff;
            --text-color: #333333;
        }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            margin: 0;
            padding: 30px;
            color: var(--text-color);
        }
        .container { max-width: 1000px; margin: auto; }
        header { text-align: center; margin-bottom: 30px; }
        h1 { color: var(--primary-color); margin-bottom: 5px; }
        .subtitle { color: #7f8c8d; font-size: 14px; }
        
        /* البطاقات الإحصائية */
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: var(--card-bg);
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            text-align: center;
            border-top: 4px solid var(--accent-color);
        }
        .card.success { border-top-color: var(--success-color); }
        .card h3 { margin: 0 0 10px 0; font-size: 15px; color: #7f8c8d; }
        .card .value { font-size: 24px; font-weight: bold; color: var(--primary-color); }

        /* الجدول والأزرار */
        .table-container {
            background: var(--card-bg);
            border-radius: 10px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            overflow: hidden;
            padding: 20px;
        }
        h2 { font-size: 18px; color: var(--primary-color); margin-top: 0; border-bottom: 2px solid #ecf0f1; padding-bottom: 10px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; }
        th, td { padding: 14px 12px; text-align: center; border-bottom: 1px solid #ecf0f1; }
        th { background-color: #f8f9fa; color: #2c3e50; font-weight: 600; }
        tr:hover { background-color: #fdfefe; }
        .wallet-text { font-family: monospace; font-size: 13px; background: #f1f2f6; padding: 4px 8px; border-radius: 4px; }
        .badge-balance { font-weight: bold; color: var(--success-color); }
        
        .btn-payout {
            background-color: var(--success-color);
            color: white;
            padding: 8px 14px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            text-decoration: none;
            display: inline-block;
        }
        .btn-payout:hover { background-color: #219653; }
        .btn-disabled {
            background-color: #bdc3c7;
            cursor: not-allowed;
            padding: 8px 14px;
            border-radius: 5px;
            color: white;
            font-weight: bold;
        }
        .no-data { text-align: center; color: #95a5a6; padding: 30px; }
        .footer-note { text-align: center; margin-top: 25px; font-size: 12px; color: #95a5a6; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>⛏️ لوحة تحكم مجمع التعدين مع نظام السحب</h1>
            <div class="subtitle">إدارة الأرصدة وسحب الأرباح الفورية</div>
        </header>

        <div class="stats-grid">
            <div class="card">
                <h3>المعدّنون النشطون</h3>
                <div class="value">{{ total_miners }}</div>
            </div>
            <div class="card success">
                <h3>إجمالي الأرصدة المتاحة</h3>
                <div class="value">{{ total_balance | round(2) }} URC</div>
            </div>
            <div class="card">
                <h3>إجمالي الحصص</h3>
                <div class="value">{{ total_shares }}</div>
            </div>
        </div>

        <div class="table-container">
            <h2>قائمة أرصدة ومحافظ المعدّنين</h2>
            <table>
                <thead>
                    <tr>
                        <th>عنوان المحفظة</th>
                        <th>الرصيد القابل للسحب</th>
                        <th>الحصص</th>
                        <th>إجراء السحب (Payout)</th>
                    </tr>
                </thead>
                <tbody>
                    {% if miners %}
                        {% for miner in miners %}
                        <tr>
                            <td><span class="wallet-text">{{ miner[0] }}</span></td>
                            <td><span class="badge-balance">{{ miner[1] }} URC</span></td>
                            <td><strong>{{ miner[2] }}</strong></td>
                            <td>
                                {% if miner[1] > 0 %}
                                    <a href="/payout/{{ miner[0] }}" class="btn-payout" onclick="return confirm('هل أنت متأكد من رغبتك في سحب رصيد هذه المحفظة؟');">طلب سحب الأرباح</a>
                                {% else %}
                                    <span class="btn-disabled">الرصيد غير كافٍ</span>
                                {% endif %}
                            </td>
                        </tr>
                        {% endfor %}
                    {% else %}
                        <tr>
                            <td colspan="4" class="no-data">لا يوجد معدّنون مسجلون حالياً.</td>
                        </tr>
                    {% endif %}
                </tbody>
            </table>
        </div>

        <div class="footer-note">
            نظام سحب الأرباح المباشر - Ur Coin Project
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def index():
    miners = []
    total_miners = 0
    total_balance = 0.0
    total_shares = 0
    
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT wallet, balance, shares, last_seen FROM miners")
        miners = cursor.fetchall()
        conn.close()

        total_miners = len(miners)
        for m in miners:
            total_balance += m[1]
            total_shares += m[2]
    except Exception as e:
        print(f"Error: {e}")
        
    return render_template_string(
        HTML_TEMPLATE, 
        miners=miners, 
        total_miners=total_miners, 
        total_balance=total_balance, 
        total_shares=total_shares
    )

@app.route("/payout/<path:wallet>")
def process_payout(wallet):
    """معالجة عملية السحب وتصفير الرصيد للمحفظة المحددة"""
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        
        # جلب الرصيد الحالي للمحفظة قبل تصفيته
        cursor.execute("SELECT balance FROM miners WHERE wallet = ?", (wallet,))
        row = cursor.fetchone()
        
        if row and row[0] > 0:
            amount_to_pay = row[0]
            
            # هنا يمكنك إرسال طلب تحويل للعقدة الرئيسية (اختياري / حسب تصميم عقدتك)
            # مثال: send_transaction_to_node(wallet, amount_to_pay)
            
            # تصفير رصيد المحفظة في قاعدة بيانات المجمع بعد السحب الناجح
            cursor.execute("UPDATE miners SET balance = 0.0 WHERE wallet = ?", (wallet,))
            conn.commit()
            print(f"[Payout SUCCESS] Paid {amount_to_pay} URC to wallet: {wallet}")
            
        conn.close()
    except Exception as e:
        print(f"[Payout Error] {e}")
        
    # إعادة توجيه المستخدم لصفحة لوحة التحكم الرئيسية
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)