@echo off
REM ============================================================
REM WAMaps - Run Application Script
REM Untuk Windows (PowerShell atau Command Prompt)
REM ============================================================

echo Membuka WAMaps Admin Dashboard...
echo.

REM Check if .venv exists
if not exist ".venv" (
    echo [ERROR] Virtual environment tidak ditemukan!
    echo.
    echo Silakan jalankan install_dependencies.bat terlebih dahulu.
    echo.
    pause
    exit /b 1
)

REM Activate venv and run app
call .venv\Scripts\activate.bat
python desktop_app.py

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Aplikasi error dengan code: %errorlevel%
    echo Coba jalankan: pip install -r requirements.txt
    pause
)
