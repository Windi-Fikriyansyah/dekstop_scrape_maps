@echo off
REM ============================================================
REM WAMaps - Install Dependencies Script
REM Untuk Windows (PowerShell atau Command Prompt)
REM ============================================================

setlocal enabledelayedexpansion

echo.
echo ============================================================
echo WAMaps - Dependency Installation
echo ============================================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python tidak terdeteksi!
    echo Pastikan Python 3.8+ sudah diinstall dan ditambahkan ke PATH
    echo.
    echo Download Python dari: https://www.python.org/downloads/
    echo Saat instalasi, pastikan CENTANG "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('python --version') do set PYTHON_VERSION=%%i
echo [OK] %PYTHON_VERSION% terdeteksi

echo.
echo [1/3] Membuat virtual environment (.venv)...
python -m venv .venv
if %errorlevel% neq 0 (
    echo [ERROR] Gagal membuat virtual environment
    pause
    exit /b 1
)
echo [OK] Virtual environment created

echo.
echo [2/3] Mengaktifkan virtual environment...
call .venv\Scripts\activate.bat
echo [OK] Virtual environment activated

echo.
echo [3/3] Menginstall dependencies dari requirements.txt...
echo      (Ini mungkin memakan waktu 2-5 menit)
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo [WARNING] Ada error saat instalasi pip packages
    echo Coba manual install dengan: pip install -r requirements.txt
    pause
    exit /b 1
)

echo.
echo [OK] Menginstall Playwright browser (Chromium)...
python -m playwright install chromium
if %errorlevel% neq 0 (
    echo [WARNING] Playwright browser install mungkin ada warning, tapi tidak fatal
)

echo.
echo ============================================================
echo INSTALASI SELESAI!
echo ============================================================
echo.
echo Untuk menjalankan aplikasi, gunakan:
echo   1. Double-click: run_app.bat
echo   2. Atau manual: .venv\Scripts\activate.bat && python desktop_app.py
echo.
pause
