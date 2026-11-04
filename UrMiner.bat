@echo off
title UrMiner Pro - Kryptex GPU Mining Suite
cd /d "%~dp0"
echo ==================================================================
echo   Starting UrMiner Pro - Kryptex GPU Mining Suite for Ur Coin (URC)
echo   Hardware Accelerated PoW (NVIDIA / AMD / Intel / CPU)
echo ==================================================================
python urminer_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An error occurred while launching UrMiner GUI.
    echo Press any key to exit...
    pause >nul
)
