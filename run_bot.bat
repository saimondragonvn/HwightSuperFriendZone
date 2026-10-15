@echo off
chcp 65001 > nul
echo ========================================================
echo     DANG KHOI CHAY DISCORD STORE BOT (24/7)
echo ========================================================
if not exist .venv (
    echo [LOI] Chua tim thay moi truong ao .venv!
    pause
    exit /b
)
.\.venv\Scripts\python.exe bot.py
pause
