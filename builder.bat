@echo off
cd /d "%~dp0"
pyarmor gen *.py
pyinstaller --onefile --noconsole --uac-admin aimbot.py
pause
