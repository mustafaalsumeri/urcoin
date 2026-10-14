@echo off
title Ur Coin (URC) - GPU OpenCL Miner
echo ==================================================================
echo         Starting Ur Coin (URC) Standalone GPU Miner...
echo ==================================================================
python -c "from urcoin.wallet import Wallet; w=Wallet.create_or_load(); print(w.address)" > temp_addr.txt
set /p MINER_ADDR=<temp_addr.txt
del temp_addr.txt
echo Mining payout address: %MINER_ADDR%
python urcoin_miner.py --address %MINER_ADDR%
pause
