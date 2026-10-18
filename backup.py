"""
Ur Coin (URC) - Safe Live Backup Utility
Takes a live snapshot of the active blockchain database, wallet, and code,
and packages it into a timestamped ZIP archive on your Desktop.
"""

import os
import sys
import shutil
import sqlite3
import zipfile
import datetime

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

def make_backup():
    desktop = os.path.join(os.path.expanduser("~"), "Desktop", "UrCoin_Backups")
    os.makedirs(desktop, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    zip_path = os.path.join(desktop, f"UrCoin_Backup_{timestamp}.zip")

    print("==================================================================")
    print("         UR COIN (URC) - LIVE AUTOMATED PROJECT BACKUP")
    print("==================================================================")
    print(f"Creating backup archive at:\n  -> {zip_path}\n")

    temp_db = "urcoin_data_snapshot.db"
    has_db = os.path.exists("urcoin_data.db")
    if has_db:
        print("[1/3] Creating live snapshot of active blockchain database...")
        src_conn = sqlite3.connect("urcoin_data.db")
        dst_conn = sqlite3.connect(temp_db)
        src_conn.backup(dst_conn)
        dst_conn.close()
        src_conn.close()

    print("[2/3] Compressing project source code, wallet keys, and data...")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk("."):
            if any(p in root for p in [".git", "__pycache__", "UrCoin_Backups"]):
                continue
            for file in files:
                filepath = os.path.join(root, file)
                relpath = os.path.relpath(filepath, ".")
                if file == "urcoin_data.db" and has_db:
                    zipf.write(temp_db, "urcoin_data.db")
                elif file != temp_db and not file.endswith(".zip"):
                    zipf.write(filepath, relpath)

    if os.path.exists(temp_db):
        os.remove(temp_db)

    size_kb = os.path.getsize(zip_path) / 1024
    print(f"[3/3] Done! Total Archive Size: {size_kb:.1f} KB")
    print("==================================================================")
    print("[OK] BACKUP COMPLETED SUCCESSFULLY!")
    print(f"[OK] Saved on your Desktop in folder: Desktop\\UrCoin_Backups")
    print("==================================================================")

if __name__ == "__main__":
    make_backup()
