@echo off
title Ur Coin Mining Launcher
cd /d "%~dp0"
echo ==================================================================
echo   Ur Coin (URC) - Kryptex-Edition Mining Suite
echo ==================================================================
echo.
echo Select Mining Mode:
echo   [1] Launch UrMiner Pro Desktop GUI (Kryptex Edition - Recommended)
echo   [2] Launch High-Speed Terminal GPU Miner (CLI)
echo.
set /p CHOICE="Enter choice [1 or 2, default is 1]: "
if "%CHOICE%"=="2" (
    call mine.bat
) else (
    call UrMiner.bat
)
