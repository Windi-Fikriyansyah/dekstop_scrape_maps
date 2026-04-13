import os
import sys

# PENTING: Paksa Playwright menggunakan lokasi browser global (WAJIB paling atas)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

import csv
import re
import threading
import time
import tkinter as tk
import urllib.parse
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

# Import database components
try:
    from sqlalchemy.orm import Session
    import models
    from database import engine, SessionLocal, Base
    # Create tables if not exist
    Base.metadata.create_all(bind=engine)
except ImportError:
    print("Database components not fully accessible. Ensure SQLAlchemy is installed.")

import customtkinter as ctk
import pandas as pd
from playwright.sync_api import sync_playwright

def check_playwright_browser():
    """Checks if chromium is installed for playwright."""
    try:
        with sync_playwright() as p:
            p.chromium.launch(headless=True).close()
        return True
    except Exception:
        return False

# ─── Constants ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
EXCLUDED_DOMAINS = ["google.com", "facebook.com", "instagram.com"]

# ─── Color Palette ────────────────────────────────────────────────────────────
COLORS = {
    "bg_dark":      "#0f0f1a",
    "bg_card":      "#1a1a2e",
    "bg_input":     "#16213e",
    "accent":       "#6c63ff",
    "accent_hover": "#5a52d5",
    "accent_light": "#8b83ff",
    "success":      "#00c896",
    "warning":      "#ffb84d",
    "danger":       "#ff6b6b",
    "text_primary": "#e8e8f0",
    "text_secondary":"#8888a8",
    "text_muted":   "#555577",
    "border":       "#2a2a4a",
    "table_row_1":  "#1a1a2e",
    "table_row_2":  "#141428",
    "table_header": "#252545",
}


class ScraperEngine:
    def __init__(self, callback_log=None, callback_result=None, callback_progress=None, callback_done=None):
        self.callback_log = callback_log or (lambda msg: None)
        self.callback_result = callback_result or (lambda row: None)
        self.callback_progress = callback_progress or (lambda val, total: None)
        self.callback_done = callback_done or (lambda: None)
        self.is_running = False
        self.results = []

    def stop(self):
        self.is_running = False

    def run(self, keyword: str, location: str, max_results: int):
        self.is_running = True
        self.results = []
        final_query = f"{keyword} in {location}"

        self.callback_log(f"🚀 Memulai: \"{final_query}\"")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(
                    viewport={"width": 1280, "height": 720},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                )
                page = context.new_page()

                encoded_query = urllib.parse.quote(final_query)
                url = f"https://www.google.com/maps/search/{encoded_query}"
                page.goto(url, timeout=30000)

                # Handle consent
                try:
                    consent = page.query_selector("button[aria-label*='Accept'], button[aria-label*='agree']")
                    if consent: consent.click()
                except Exception: pass

                # Scroll
                attempts = 0
                while attempts < 20:
                    if not self.is_running: break
                    current = len(page.query_selector_all("a.hfpxzc"))
                    if current >= max_results: break
                    
                    results_panel = page.query_selector("div[role='feed']")
                    if results_panel:
                        results_panel.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                    else:
                        page.mouse.wheel(0, 3000)
                    
                    time.sleep(1.5)
                    if len(page.query_selector_all("a.hfpxzc")) == current: attempts += 1
                    else: attempts = 0

                links = page.query_selector_all("a.hfpxzc")
                urls = [link.get_attribute("href") for link in links[:max_results]]
                total = len(urls)

                for idx, detail_url in enumerate(urls):
                    if not self.is_running: break

                    try:
                        page.goto(detail_url, timeout=10000)
                        page.wait_for_selector("h1.DUwDvf", timeout=5000)

                        name = self._safe_text(page, "h1.DUwDvf")
                        category = self._safe_text(page, "button.DkEaL")
                        address = self._safe_text(page, "button[data-item-id='address']").strip()
                        phone = ""
                        try:
                            # Ambil langsung dari atribut ID tombol agar tidak ada ikon nyangkut
                            phone_node = page.query_selector("button[data-item-id*='phone:tel:']")
                            if phone_node:
                                raw_phone = phone_node.get_attribute("data-item-id")
                                if raw_phone:
                                    phone = raw_phone.replace("phone:tel:", "").strip()
                            # Jika atribut tidak ketemu, ambil teksnya dan bersihkan dari karakter aneh
                            if not phone:
                                phone = self._safe_text(page, "button[data-item-id*='phone:tel:']").strip()
                                phone = re.sub(r'[^\d\s\+\-\(\)]', '', phone)
                        except Exception: pass
                        rating = self._safe_text(page, "div.F7nice span span[aria-hidden='true']")

                        website = ""
                        try:
                            web_node = page.query_selector("a[data-item-id='authority']")
                            if web_node:
                                href = web_node.get_attribute("href")
                                if href and not any(d in href.lower() for d in EXCLUDED_DOMAINS):
                                    website = href.split("?")[0].rstrip("/")
                        except Exception: pass

                        email = ""
                        if website:
                            try:
                                wp = context.new_page()
                                wp.route("**/*.{png,jpg,jpeg,gif,webp,svg,css,woff,woff2}", lambda r: r.abort())
                                wp.goto(website, timeout=5000)
                                m = EMAIL_RE.search(wp.content())
                                if m: email = m.group(0).lower()
                                wp.close()
                            except Exception: pass

                        row = {
                            "No": idx + 1,
                            "Nama": name,
                            "Kategori": category,
                            "Alamat": address,
                            "Telepon": phone,
                            "Website": website,
                            "Email": email,
                            "Rating": rating,
                            "Maps URL": detail_url,
                        }
                        self.results.append(row)
                        self.callback_result(row)
                        self.callback_progress(idx + 1, total)
                        self.callback_log(f"✅ Captured: {name}")

                    except Exception as e:
                        self.callback_progress(idx + 1, total)
                        continue

                browser.close()

        except Exception as e:
            self.callback_log(f"❌ Error: {str(e)}")

        self.is_running = False
        self.callback_done()

    @staticmethod
    def _safe_text(page, selector):
        try:
            node = page.query_selector(selector)
            return node.inner_text() if node else ""
        except Exception: return ""


class ModernApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ─── Window Setup ─────────────────────────────────────────────────
        self.title("Maps Lead Scraper")
        # Start with a more minimalist size
        self.geometry("1000x650")
        self.minsize(800, 550)
        self.configure(fg_color=COLORS["bg_dark"])

        self.engine = None
        self.current_results = []

        # ─── Layout ───────────────────────────────────────────────────────
        self.tabview = ctk.CTkTabview(self, fg_color=COLORS["bg_dark"], segmented_button_selected_color=COLORS["accent"])
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)

        self.tab_scraper = self.tabview.add("Scraper ✨")
        self.tab_saved = self.tabview.add("Data Tersimpan 📁")

        self._setup_scraper_tab()
        self._setup_saved_tab()
        self._setup_styles()
        
        # Check for browser on a separate thread to not freeze UI immediately
        threading.Thread(target=self._initialize_system, daemon=True).start()

    def _initialize_system(self):
        """Perform first-run checks and browser installation."""
        import subprocess
        
        self._log("🌐 Mengecek sistem browser...")
        self.btn_start.configure(state="disabled", text="Initializing...")
        
        if not check_playwright_browser():
            self._log("🛠️ Mengunduh browser Chromium (wajib)...")
            self._log("Mohon tunggu, ini mungkin memakan waktu 1-3 menit.")
            try:
                # Menggunakan subprocess agar lebih aman terhadap ModuleNotFoundError
                # creationflags=0x08000000 (CREATE_NO_WINDOW) agar tidak muncul jendela hitam
                subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    check=True,
                    capture_output=True,
                    text=True,
                    creationflags=0x08000000 if os.name == 'nt' else 0
                )
                
                if check_playwright_browser():
                    self._log("✅ Browser berhasil diinstal!")
                else:
                    self._log("❌ Instalasi selesai tapi browser belum terdeteksi.")
            except Exception as e:
                self._log(f"❌ Gagal menginstal browser: {str(e)}")
                messagebox.showerror("Error Browser", f"Gagal mengunduh browser: {str(e)}")
        else:
            self._log("✅ Sistem browser siap!")
            
        self.after(500, lambda: self.btn_start.configure(state="normal", text="Mulai Scraping"))

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use("clam")
        
        # Pengaturan utama Treeview
        style.configure("Custom.Treeview", 
            background=COLORS["bg_card"], 
            foreground=COLORS["text_primary"], 
            fieldbackground=COLORS["bg_card"], 
            borderwidth=0, 
            font=("Segoe UI", 10), 
            rowheight=35 # Lebih tinggi agar tidak sesak
        )
        
        # Pengaturan Header
        style.configure("Custom.Treeview.Heading", 
            background=COLORS["table_header"], 
            foreground=COLORS["accent_light"], 
            font=("Segoe UI Semibold", 10), 
            borderwidth=0,
            padding=8 # Ruang ekstra untuk teks header
        )
        
        # Warna saat baris diklik
        style.map("Custom.Treeview", background=[("selected", COLORS["accent"])])
        
        # Menghilangkan garis pembatas horizontal/vertikal standar agar lebih clean
        style.layout("Custom.Treeview", [('Custom.Treeview.treearea', {'sticky': 'nswe'})]) 

        # Tambahkan konfigurasi tag untuk zebra striping (diatur langsung ke widget nanti)
        # Note: Tag warna akan diatur di konstruktor / saat tambah data.

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 1: SCRAPER
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_scraper_tab(self):
        # Left sidebar for controls
        sidebar = ctk.CTkFrame(self.tab_scraper, width=280, fg_color=COLORS["bg_card"], corner_radius=15)
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)
        sidebar.pack_propagate(False)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkLabel(inner, text="PENGATURAN", font=("Segoe UI Semibold", 14), text_color=COLORS["text_primary"]).pack(pady=(0,15))

        self.entry_keyword = self._add_field(inner, "🔍 Keyword", "Contoh: Restoran")
        self.entry_location = self._add_field(inner, "📍 Lokasi", "Contoh: Jakarta")
        self.entry_max = self._add_field(inner, "📊 Jumlah Data", "10")

        self.btn_start = ctk.CTkButton(inner, text="Mulai Scraping", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_scraping, height=40)
        self.btn_start.pack(fill="x", pady=(15, 5))

        self.btn_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_scraping)
        self.btn_stop.pack(fill="x", pady=5)

        self.btn_save_db = ctk.CTkButton(inner, text="Simpan ke Database", fg_color=COLORS["success"], state="disabled", command=self._save_to_db)
        self.btn_save_db.pack(fill="x", pady=5)

        self.progress_bar = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["accent"])
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=15)

        self.log_text = ctk.CTkTextbox(inner, height=120, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color="white")
        self.log_text.pack(fill="x")

        # Main table area
        main_area = ctk.CTkFrame(self.tab_scraper, fg_color=COLORS["bg_card"], corner_radius=15)
        main_area.pack(side="right", fill="both", expand=True)

        self.tree = self._create_tree(main_area)

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 2: SAVED DATA
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_saved_tab(self):
        top_bar = ctk.CTkFrame(self.tab_saved, fg_color="transparent", height=50)
        top_bar.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(top_bar, text="Data Tersimpan", font=("Segoe UI Semibold", 16)).pack(side="left")

        # Tombol aksi Data Tersimpan
        self.btn_select_all = ctk.CTkButton(top_bar, text="Pilih Semua", width=100, command=self._select_all_saved)
        self.btn_select_all.pack(side="left", padx=(15, 5))
        
        self.btn_delete_selected = ctk.CTkButton(top_bar, text="Hapus Terpilih", width=100, fg_color=COLORS["danger"], hover_color="#cc0000", command=self._delete_selected_data)
        self.btn_delete_selected.pack(side="left", padx=5)

        ctk.CTkButton(top_bar, text="Refresh", width=80, command=self._load_saved_data).pack(side="right", padx=5)
        ctk.CTkButton(top_bar, text="Export CSV", fg_color=COLORS["success"], width=100, command=self._export_saved_to_csv).pack(side="right", padx=5)
        ctk.CTkButton(top_bar, text="Export Excel", fg_color="#107c41", width=100, command=self._export_saved_to_excel).pack(side="right", padx=5)

        self.tree_saved = self._create_tree(self.tab_saved, checkbox=True)
        self.select_all_state = False
        self._load_saved_data()

    # ═══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════════════
    def _add_field(self, parent, label, placeholder):
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, fg_color=COLORS["bg_input"], border_color=COLORS["border"], text_color="white")
        entry.pack(fill="x", pady=(0, 10))
        return entry

    def _create_tree(self, parent, checkbox=False):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=10, pady=10)

        if checkbox:
            cols = ("select", "no", "nama", "kategori", "alamat", "telepon", "email", "website", "rating")
        else:
            cols = ("no", "nama", "kategori", "alamat", "telepon", "email", "website", "rating")

        tree = ttk.Treeview(container, columns=cols, show="headings", style="Custom.Treeview")
        
        if checkbox:
            tree.heading("select", text="Pilih")
            tree.column("select", width=40, anchor="center")

        tree.heading("no", text="No")
        tree.column("no", width=30, anchor="center")
        tree.heading("nama", text="Nama Bisnis")
        tree.column("nama", width=150)
        tree.heading("kategori", text="Kategori")
        tree.column("kategori", width=100)
        tree.heading("alamat", text="Alamat")
        tree.column("alamat", width=250)
        tree.heading("telepon", text="Telepon")
        tree.column("telepon", width=100)
        tree.heading("email", text="Email")
        tree.column("email", width=120)
        tree.heading("website", text="Website")
        tree.column("website", width=120)
        tree.heading("rating", text="⭐")
        tree.column("rating", width=40, anchor="center")

        ysb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
        tree.configure(yscroll=ysb.set)
        
        # Zebra Striping Konfig
        tree.tag_configure("odd", background=COLORS["table_row_1"])
        tree.tag_configure("even", background=COLORS["table_row_2"])

        tree.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        if checkbox:
            def toggle_check(event):
                region = tree.identify("region", event.x, event.y)
                if region == "cell":
                    column = tree.identify_column(event.x)
                    if column == "#1":  # Kolom pertama adalah checkbox
                        item = tree.identify_row(event.y)
                        vals = list(tree.item(item, "values"))
                        if vals:
                            vals[0] = "☑" if vals[0] == "☐" else "☐"
                            tree.item(item, values=vals)
            tree.bind("<ButtonRelease-1>", toggle_check)

        return tree

    # ═══════════════════════════════════════════════════════════════════════
    #  LOGIC
    # ═══════════════════════════════════════════════════════════════════════
    def _start_scraping(self):
        kw = self.entry_keyword.get().strip()
        loc = self.entry_location.get().strip()
        try: limit = int(self.entry_max.get() or 10)
        except: limit = 10

        if not kw or not loc:
            messagebox.showwarning("Input Kosong", "Keyword dan Lokasi harus diisi!")
            return

        for item in self.tree.get_children(): self.tree.delete(item)
        self.current_results = []
        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.btn_save_db.configure(state="disabled")

        self.engine = ScraperEngine(
            callback_log=self._log,
            callback_result=self._add_row,
            callback_progress=lambda c, t: self.after(0, lambda: self.progress_bar.set(c/t)),
            callback_done=self._on_finish
        )
        threading.Thread(target=self.engine.run, args=(kw, loc, limit), daemon=True).start()

    def _log(self, msg):
        self.after(0, lambda: (self.log_text.insert("end", f"{msg}\n"), self.log_text.see("end")))

    def _add_row(self, row):
        def _do():
            tag = "even" if len(self.tree.get_children()) % 2 == 0 else "odd"
            self.tree.insert("", "end", values=(row["No"], row["Nama"], row["Kategori"], row["Alamat"], row["Telepon"], row["Email"], row["Website"], row["Rating"]), tags=(tag,))
            self.current_results.append(row)
        self.after(0, _do)

    def _on_finish(self):
        self.after(0, lambda: (
            self.btn_start.configure(state="normal"),
            self.btn_stop.configure(state="disabled"),
            self.btn_save_db.configure(state="normal") if self.current_results else None,
            self._log("🏁 Scraping Selesai.")
        ))

    def _stop_scraping(self):
        if self.engine: self.engine.stop()

    def _save_to_db(self):
        if not self.current_results: return
        
        db = SessionLocal()
        count = 0
        seen_keys = set() # Untuk melacak duplikat dari data yang baru saja ditarik (dalam satu sesi ini)
        
        try:
            for r in self.current_results:
                url = r["Maps URL"]
                name_addr = (r["Nama"], r["Alamat"])
                
                # Jika dalam 1 tarikan (scrape) ini ada data ganda, CUKUP AMBIL 1 SAJA
                if url in seen_keys or name_addr in seen_keys:
                    continue
                    
                seen_keys.add(url)
                seen_keys.add(name_addr)

                from sqlalchemy import or_
                # Cari data lama (berdasarkan URL Maps ATAU kombinasi Nama & Alamat)
                exists = db.query(models.Lead).filter(
                    or_(
                        models.Lead.google_place_id == url,
                        (models.Lead.name == r["Nama"]) & (models.Lead.address == r["Alamat"])
                    )
                ).first()
                
                new_rating = float(r["Rating"].replace(",",".")) if r["Rating"] and r["Rating"] != "0" else 0.0
                
                # Jika ada, PERBARUI datanya (Update)
                if exists:
                    exists.name = r["Nama"]
                    exists.category = r["Kategori"]
                    exists.address = r["Alamat"]
                    exists.phone = r["Telepon"]
                    exists.website = r["Website"]
                    exists.rating = new_rating
                    exists.google_place_id = url
                    db.flush() # Segarkan sesi saat ini agar database menyadari perubahan
                    count += 1
                else:
                    # Masukkan data baru
                    lead = models.Lead(
                        name=r["Nama"],
                        category=r["Kategori"],
                        address=r["Alamat"],
                        phone=r["Telepon"],
                        website=r["Website"],
                        rating=new_rating,
                        google_place_id=url 
                    )
                    db.add(lead)
                    db.flush() # Paksa masuk ke sesi agar tidak bertabrakan dengan data berikutnya
                    count += 1
            db.commit()
            messagebox.showinfo("Berhasil", f"{count} data baru berhasil disimpan ke database!")
            self._load_saved_data()
        except Exception as e:
            db.rollback()
            messagebox.showerror("Error DB", f"Gagal menyimpan: {str(e)}")
        finally:
            db.close()

    def _load_saved_data(self):
        for item in self.tree_saved.get_children(): self.tree_saved.delete(item)
        db = SessionLocal()
        try:
            leads = db.query(models.Lead).order_by(models.Lead.id.desc()).all()
            for i, l in enumerate(leads):
                tag = "even" if i % 2 == 0 else "odd"
                # Simpan l.id di atribut 'iid' tabel, ini kunci utama untuk hapus data nanti
                self.tree_saved.insert("", "end", iid=str(l.id), values=("☐", i+1, l.name, l.category, l.address, l.phone, "", l.website, l.rating), tags=(tag,))
        finally:
            db.close()
            
        # Reset tombol pilih semua setiap kali data di-load ulang
        if hasattr(self, 'select_all_state'):
            self.select_all_state = False
            self.btn_select_all.configure(text="Pilih Semua")

    def _select_all_saved(self):
        self.select_all_state = not getattr(self, 'select_all_state', False)
        char = "☑" if self.select_all_state else "☐"
        self.btn_select_all.configure(text="Batal Pilih Semua" if self.select_all_state else "Pilih Semua")
        
        for item in self.tree_saved.get_children():
            vals = list(self.tree_saved.item(item, "values"))
            vals[0] = char
            self.tree_saved.item(item, values=vals)

    def _delete_selected_data(self):
        selected_ids = []
        for item in self.tree_saved.get_children():
            vals = self.tree_saved.item(item, "values")
            if vals and vals[0] == "☑":
                selected_ids.append(int(item)) # `item` adalah id database karena kita simpan di format iid=str(l.id)
        
        if not selected_ids:
            messagebox.showwarning("Pilih Data", "Harap centang data yang ingin dihapus pada kolom 'Pilih'!")
            return
            
        if messagebox.askyesno("Konfirmasi Hapus", f"Yakin ingin menghapus {len(selected_ids)} data secara permanen?"):
            db = SessionLocal()
            try:
                db.query(models.Lead).filter(models.Lead.id.in_(selected_ids)).delete(synchronize_session=False)
                db.commit()
                messagebox.showinfo("Berhasil", f"{len(selected_ids)} data berhasil dihapus.")
                self._load_saved_data()
            except Exception as e:
                db.rollback()
                messagebox.showerror("Error", f"Gagal menghapus data: {str(e)}")
            finally:
                db.close()

    def _export_saved_to_csv(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV File", "*.csv")])
        if not path: return
        
        db = SessionLocal()
        try:
            leads = db.query(models.Lead).all()
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                w.writerow(["ID", "Nama", "Kategori", "Alamat", "Telepon", "Website", "Rating"])
                for l in leads:
                    w.writerow([l.id, l.name, l.category, l.address, l.phone, l.website, l.rating])
            messagebox.showinfo("Export Berhasil", f"Data diexport ke {path}")
        finally:
            db.close()
    def _export_saved_to_excel(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel File", "*.xlsx")])
        if not path: return
        
        db = SessionLocal()
        try:
            leads = db.query(models.Lead).all()
            data = []
            for l in leads:
                data.append({
                    "ID": l.id,
                    "Nama": l.name,
                    "Kategori": l.category,
                    "Alamat": l.address,
                    "Telepon": l.phone,
                    "Website": l.website,
                    "Rating": l.rating
                })
            
            df = pd.DataFrame(data)
            df.to_excel(path, index=False)
            messagebox.showinfo("Export Berhasil", f"Data diexport ke {path}")
        except Exception as e:
            messagebox.showerror("Error Excel", f"Gagal export Excel: {str(e)}")
        finally:
            db.close()

if __name__ == "__main__":
    app = ModernApp()
    app.mainloop()
