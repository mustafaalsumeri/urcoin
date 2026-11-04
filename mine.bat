@echo off
title Ur Coin - Dedicated GPU Miner CLI
cd /d "%~dp0"
echo ==================================================================
echo          Starting Ur Coin Dedicated GPU Miner (CLI Worker)...
echo ==================================================================
python -c "from urcoin.wallet import Wallet; w=Wallet.create_or_load(); print(w.address)" > temp_addr.txt
set /p MINER_ADDR=<temp_addr.txt
del temp_addr.txt
echo Mining Payout Address: %MINER_ADDR%
python urcoin_miner.py --address %MINER_ADDR%
pause
