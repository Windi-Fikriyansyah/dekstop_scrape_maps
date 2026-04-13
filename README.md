# Maps Lead Scraper Desktop 🚀

Akses data bisnis Google Maps dengan satu klik. Aplikasi ini dirancang untuk mudah digunakan oleh user awam tanpa perlu instalasi Python.

## Fitur Utama
- **Scraping Otomatis**: Cukup masukkan keyword dan lokasi.
- **Ekstrak Kontak**: Mengambil Email dan Telepon langsung dari website bisnis.
- **Database Lokal**: Menyimpan data hasil scraping secara otomatis.
- **Export Data**: Simpan hasil ke format CSV atau Excel.
- **Modern UI**: Antarmuka gelap yang minimalis dan responsif.

## Cara Menggunakan (Untuk User)
1. Jalankan `MapsLeadScraper.exe`.
2. Masukkan Keyword (contoh: *Cafe*) dan Lokasi (contoh: *Bandung*).
3. Klik **Mulai Scraping**.
4. Data akan muncul di tabel. Gunakan tab **Data Tersimpan** untuk melihat riwayat.

## Cara Build Menjadi Aplikasi (.EXE)
Jika Anda adalah pengembang yang ingin membungkus kode ini menjadi aplikasi untuk orang lain:

1. Pastikan Python terinstal.
2. Klik dua kali file `build_app.bat`.
3. Tunggu hingga selesai. File aplikasi akan ada di folder `dist/MapsLeadScraper.exe`.

### Membuat Installer (Setup.exe)
Untuk membuat folder instalasi profesional:
1. Instal **Inno Setup** (Gratis).
2. Klik kanan pada `installer_script.iss` di folder ini.
3. Pilih **Compile**.
4. Hasil installer ada di `dist/installer/MapsLeadScraper_Setup.exe`.

## Dependensi Inti
- `CustomTkinter` (UI)
- `Playwright` (Scraping engine)
- `SQLAlchemy` (Database)
- `Pandas` (Export data)

## Lisensi
MIT
