@echo off
REM Start Backtest Lab and open the browser when the server is ready.
title Backtest Lab
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart-app.ps1" -OpenBrowser %*
if errorlevel 1 (
    echo.
    echo Backtest Lab could not start. Read the error above.
    pause
)
