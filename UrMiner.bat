@echo off
title Ur Coin (URC) - Adaptive Miner (Weak/Strong GPUs & CPU)
echo ==================================================================
echo         Starting Ur Coin (URC) Adaptive Miner...
echo         Compatible with Low-End / High-End GPUs and CPUs
echo ==================================================================
python -c "from urcoin.wallet import Wallet; w=Wallet.create_or_load(); print(w.address)" > temp_addr.txt
set /p MINER_ADDR=<temp_addr.txt
del temp_addr.txt
echo Mining payout address: %MINER_ADDR%
python urcoin_miner.py --address %MINER_ADDR% --profile eco
pause