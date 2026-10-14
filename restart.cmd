@echo off
REM Run the safe project restart script from a Windows terminal.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart-app.ps1" %*
exit /b %errorlevel%
