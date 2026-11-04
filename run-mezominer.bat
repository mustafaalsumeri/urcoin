@echo off
title UrMiner Pro Desktop Launcher
cd /d "%~dp0"
echo ==================================================================
echo   Starting UrMiner Pro - Kryptex GPU Mining Suite for Ur Coin (URC)
echo ==================================================================
python urminer_gui.py
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] An error occurred while launching UrMiner GUI.
    pause
)
