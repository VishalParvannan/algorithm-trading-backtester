@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\restart-app.ps1" %*
exit /b %errorlevel%
