@echo off
rem Netdoi super Save - double-click to uninstall (your shared files are kept).
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0uninstall.ps1"
echo.
pause
