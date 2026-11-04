"""
MezoMiner Pro / UrMiner Forwarder:
Directs legacy launchers to the official UrMiner Pro Kryptex-grade Mining Suite.
"""

import sys
import os

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_DIR)

from urminer_gui import UrMinerApp

def main():
    print("==================================================================")
    print("  Launching UrMiner Pro - Kryptex-Edition GPU Mining Suite...")
    print("==================================================================")
    app = UrMinerApp()
    app.mainloop()

if __name__ == "__main__":
    main()
