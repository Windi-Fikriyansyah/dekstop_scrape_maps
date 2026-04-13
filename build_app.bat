@echo off
echo ==========================================
echo   Building Maps Lead Scraper (Folder Mode)
echo ==========================================
echo.

echo [1/3] Memproses pembersihan folder lama...
rmdir /s /q build dist 2>nul

echo [2/3] Memastikan dependensi terinstal...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo [3/3] Membuat folder aplikasi (INI LEBIH STABIL)...
echo.

:: Menggunakan --onedir agar tidak ada error ekstraksi kompresi
pyinstaller --noconsole --onedir --collect-all customtkinter --name "MapsLeadScraper" --icon=NONE desktop_app.py

echo.
echo ======================================================
echo  BERHASIL! Folder aplikasi ada di: "dist\MapsLeadScraper"
echo.
echo  SELANJUTNYA:
echo  1. Klik kanan file "installer_script.iss"
echo  2. Pilih "Compile" untuk membuat Setup.exe profesional
echo ======================================================
echo.
pause
