import os
import sys
import asyncio

# PENTING: Paksa Playwright menggunakan lokasi browser global (WAJIB paling atas)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

import csv
import random
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
try:
    from instagram_engine import InstagramScraper
except ImportError:
    InstagramScraper = None

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

    @staticmethod
    def _name_formatter(name_raw):
        try:
            if not name_raw: return "Pelanggan"
            # Ambil kata pertama, bersihkan underscore, lowercase lalu Title Case
            name = str(name_raw).split()[0]
            return name.replace("_", " ").lower().title()
        except:
            return name_raw


class BroadcastEngine:
    def __init__(self, callback_log=None, callback_progress=None, callback_done=None):
        self.callback_log = callback_log or (lambda msg: None)
        self.callback_progress = callback_progress or (lambda val, total: None)
        self.callback_done = callback_done or (lambda: None)
        self.is_running = False

    def stop(self):
        self.is_running = False

    @staticmethod
    def _name_formatter(name_raw):
        try:
            if not name_raw: return "Pelanggan"
            name = str(name_raw).split()[0]
            return name.replace("_", " ").lower().title()
        except:
            return name_raw

    def _wait_for_wa_ready(self, page, timeout=30):
        """Tunggu WhatsApp Web siap (chat list muncul)."""
        ready_selectors = "div[data-testid='chat-list'], #pane-side, div[aria-label='Chat list']"
        for i in range(timeout):
            try:
                if page.query_selector(ready_selectors):
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def _safe_query(self, page, selector):
        """Query selector yang aman dari context destroyed."""
        try:
            return page.query_selector(selector)
        except Exception:
            return None

    def run(self, contacts, message_template, delay_min=10, delay_max=30, break_every=50, break_duration=10, image_path=None, check_string=None):
        self.is_running = True
        total = len(contacts)
        self.callback_log(f"🚀 Memulai campaign premium ke {total} kontak...")
        sent_count = 0
        failed_count = 0
        skipped_count = 0
        
        duplicate_finder = check_string if check_string else ""

        context = None
        try:
            with sync_playwright() as p:
                data_dir = os.path.join(os.getcwd(), "wa_session")
                os.makedirs(data_dir, exist_ok=True)
                
                # === STEP 1: Buka browser VISIBLE dulu untuk cek login / scan QR ===
                self.callback_log("🔍 Membuka WhatsApp Web...")
                context = p.chromium.launch_persistent_context(
                    data_dir, 
                    headless=False,  # Selalu visible dulu
                    no_viewport=True, 
                    args=[
                        "--start-maximized",
                        "--disable-blink-features=AutomationControlled"
                    ]
                )
                page = context.new_page()
                page.goto("https://web.whatsapp.com", wait_until="domcontentloaded")
                
                # Tunggu: apakah sudah login atau muncul QR
                self.callback_log("⏳ Menunggu WhatsApp Web siap...")
                is_logged_in = False
                
                for i in range(180):  # Tunggu maksimal 4.5 menit
                    if not self.is_running: break
                    try:
                        # Cek apakah chat list sudah muncul (= sudah login)
                        if page.query_selector("div[data-testid='chat-list'], #pane-side, div[aria-label='Chat list']"):
                            is_logged_in = True
                            break
                        # Cek apakah QR code muncul (= belum login)
                        if page.query_selector("canvas, div[data-testid='qrcode']"):
                            if i == 0 or i == 1:
                                self.callback_log("📱 QR Code terdeteksi. Silakan scan dengan HP Anda...")
                    except Exception:
                        pass  # Context bisa destroyed saat navigasi internal WA
                    time.sleep(1.5)
                
                if not is_logged_in:
                    self.callback_log("❌ Gagal login WhatsApp atau waktu habis.")
                    try: context.close()
                    except: pass
                    self.is_running = False
                    self.callback_done()
                    return
                
                self.callback_log("✅ WhatsApp Web siap!")
                time.sleep(2)
                
                # Tutup popup notifikasi jika ada
                try:
                    dismiss_btn = page.query_selector('div[data-testid="popup-controls-ok"], div[role="button"]:has-text("OK")')
                    if dismiss_btn:
                        dismiss_btn.click()
                        time.sleep(1)
                except: pass

                # === STEP 2: Mulai Broadcast (tetap di browser yang sama) ===
                self.callback_log(f"📨 Memulai pengiriman ke {total} kontak...")

                for idx, contact in enumerate(contacts):
                    if not self.is_running: break
                    
                    phone = str(contact.get('phone', '')).strip()
                    phone = re.sub(r'[^\d]', '', phone)
                    if not phone or len(phone) < 8:
                        self.callback_log(f"⏭️ [{idx+1}/{total}] Nomor tidak valid, dilewati.")
                        skipped_count += 1
                        self.callback_progress(idx + 1, total)
                        continue
                    
                    # Normalisasi nomor Indonesia
                    if phone.startswith('0'):
                        phone = '62' + phone[1:]
                    elif not phone.startswith('62'):
                        phone = '62' + phone

                    # --- Cooling Period (Anti-Ban) ---
                    if sent_count > 0 and sent_count % break_every == 0:
                        self.callback_log(f"☕ Istirahat batch (Cooling Period) selama {break_duration} menit...")
                        for m in range(break_duration):
                            for _ in range(60):
                                if not self.is_running: break
                                time.sleep(1)
                            if not self.is_running: break
                            self.callback_log(f"   Sisa: {break_duration - m - 1} menit")
                        if not self.is_running: break

                    name = self._name_formatter(contact.get('name', 'Pelanggan'))
                    final_msg = message_template.replace("{nama}", name)
                    
                    try:
                        self.callback_log(f"📨 [{idx+1}/{total}] Mengirim ke {phone} ({name})...")
                        
                        # --- Metode Direct Link (paling reliabel) ---
                        page.goto(f"https://web.whatsapp.com/send?phone={phone}", wait_until="domcontentloaded")
                        time.sleep(3)
                        
                        # Tunggu halaman chat siap atau muncul "Phone number shared via url is invalid"
                        chat_ready = False
                        for wait_i in range(20):
                            # Cek apakah nomor invalid
                            invalid_el = self._safe_query(page, 'div[data-testid="popup-controls-ok"]')
                            if invalid_el:
                                invalid_el.click()
                                time.sleep(0.5)
                                self.callback_log(f"❌ Nomor {phone} tidak valid (bukan WhatsApp).")
                                failed_count += 1
                                break
                            
                            # Cek apakah chat input sudah muncul
                            msg_input = self._safe_query(page, 'div[contenteditable="true"][data-tab="10"]')
                            if not msg_input:
                                msg_input = self._safe_query(page, 'div[title="Type a message"]')
                            if not msg_input:
                                msg_input = self._safe_query(page, 'div[title="Ketik pesan"]')
                            if msg_input:
                                chat_ready = True
                                break
                            
                            time.sleep(1)
                        
                        if not chat_ready:
                            self.callback_log(f"❌ Gagal membuka chat {phone}.")
                            failed_count += 1
                            self.callback_progress(idx + 1, total)
                            continue
                        
                        # --- Cek Duplikat ---
                        if duplicate_finder:
                            time.sleep(1)
                            try:
                                dup_count = page.locator(f'text="{duplicate_finder}"').count()
                                if dup_count > 0:
                                    self.callback_log(f"⏭️ {name} sudah menerima pesan sebelumnya. Dilewati.")
                                    skipped_count += 1
                                    self.callback_progress(idx + 1, total)
                                    continue
                            except: pass
                        
                        # --- Kirim Pesan ---
                        if image_path and os.path.exists(image_path):
                            self._send_attachment(page, image_path, final_msg)
                        else:
                            # Klik input pesan
                            msg_sel = 'div[contenteditable="true"][data-tab="10"], div[title="Type a message"], div[title="Ketik pesan"]'
                            page.click(msg_sel)
                            time.sleep(0.3)
                            
                            # Gunakan clipboard untuk paste pesan multi-baris sekaligus
                            # (page.type mengirim Enter sebagai "kirim", jadi pesan terpotong)
                            page.evaluate("""(text) => {
                                const el = document.querySelector('div[contenteditable="true"][data-tab="10"]') 
                                         || document.querySelector('div[title="Type a message"]')
                                         || document.querySelector('div[title="Ketik pesan"]');
                                if (el) {
                                    el.focus();
                                    // Gunakan execCommand insertText agar WhatsApp mendeteksi input
                                    const dataTransfer = new DataTransfer();
                                    dataTransfer.setData('text/plain', text);
                                    const event = new ClipboardEvent('paste', {
                                        clipboardData: dataTransfer,
                                        bubbles: true,
                                        cancelable: true
                                    });
                                    el.dispatchEvent(event);
                                }
                            }""", final_msg)
                            time.sleep(random.uniform(1.0, 2.0))
                            
                            # Klik tombol send
                            send_btn = self._safe_query(page, 'span[data-icon="send"]')
                            if send_btn:
                                send_btn.click()
                            else:
                                page.keyboard.press("Enter")
                        
                        # Tunggu pesan terkirim (centang muncul)
                        time.sleep(random.uniform(1.5, 3.0))
                        
                        self.callback_log(f"✅ Berhasil dikirim ke {phone} ({name})")
                        sent_count += 1

                    except Exception as e:
                        self.callback_log(f"⚠️ Gagal pada {phone}: {str(e)}")
                        failed_count += 1
                    
                    self.callback_progress(idx + 1, total)
                    
                    # --- Jeda Acak Anti-Ban ---
                    if idx < total - 1 and self.is_running:
                        wait = random.randint(delay_min, delay_max)
                        self.callback_log(f"⏳ Jeda {wait} detik (anti-ban)...")
                        for _ in range(wait):
                            if not self.is_running: break
                            time.sleep(1)

                # === Ringkasan ===
                self.callback_log(f"\n📊 RINGKASAN BROADCAST:")
                self.callback_log(f"   ✅ Terkirim: {sent_count}")
                self.callback_log(f"   ❌ Gagal: {failed_count}")
                self.callback_log(f"   ⏭️ Dilewati: {skipped_count}")

                try: context.close()
                except: pass
                
        except Exception as e:
            self.callback_log(f"❌ Fatal: {str(e)}")
            try:
                if context: context.close()
            except: pass
        
        self.is_running = False
        self.callback_done()

    def _send_attachment(self, page, file_path, caption):
        """Kirim gambar dengan caption via copy-paste (Optimized by extension logic)"""
        import base64
        try:
            # === STEP 1: Persiapan gambar ===
            with open(file_path, 'rb') as f:
                image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            ext = os.path.splitext(file_path)[1].lower()
            mime_map = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp'}
            mime_type = mime_map.get(ext, 'image/jpeg')
            
            # Fokus chat
            msg_selectors = ['div[contenteditable="true"][data-tab="10"]', 'div[title="Ketik pesan"]', 'div[title="Type a message"]']
            chat_focused = False
            for sel in msg_selectors:
                el = self._safe_query(page, sel)
                if el:
                    el.click()
                    chat_focused = True
                    break
            
            if not chat_focused: raise Exception("Chat input tidak ditemukan")
            time.sleep(0.5)
            
            # === STEP 2: Paste Gambar ===
            self.callback_log("   🖼️ Mengirim gambar via clipboard...")
            page.evaluate("""(data) => {
                const byteChars = atob(data.b64);
                const byteArr = new Uint8Array(byteChars.length);
                for (let i = 0; i < byteChars.length; i++) byteArr[i] = byteChars.charCodeAt(i);
                const file = new File([new Blob([byteArr], { type: data.mime })], 'image.png', { type: data.mime });
                const dt = new DataTransfer();
                dt.items.add(file);
                const target = document.querySelector('div[contenteditable="true"][data-tab="10"]') || document.querySelector('div[role="textbox"]');
                if (target) {
                    target.focus();
                    target.dispatchEvent(new ClipboardEvent('paste', { bubbles: true, cancelable: true, clipboardData: dt }));
                }
            }""", {"b64": image_b64, "mime": mime_type})
            
            # === STEP 3: Isi Caption (Logika dari extensionwhatsapp) ===
            time.sleep(3)
            if caption:
                # Cari field caption di overlay (Strategi dari content.js)
                self.callback_log("   📝 Mengisi keterangan (extension logic)...")
                page.evaluate("""(text) => {
                    function findCaptionInput() {
                        // Priority 1: Dalam media editor container
                        const container = document.querySelector('[data-testid="media-editor"]')
                                       || document.querySelector('[data-testid="image-editor"]')
                                       || document.querySelector('[data-testid="media-preview"]');
                        if (container) {
                            const edit = container.querySelector('div[contenteditable="true"]');
                            if (edit) return edit;
                        }
                        // Priority 2: Global visible contenteditable YANG BUKAN DI FOOTER
                        const all = document.querySelectorAll('div[contenteditable="true"]');
                        for (const el of all) {
                            if (el.closest('footer')) continue; // Lewati input chat utama
                            if (el.offsetParent === null) continue; // Harus visible
                            const label = (el.getAttribute('aria-label') || el.innerText || '').toLowerCase();
                            if (label.includes('pesan') || label.includes('message') || label.includes('keterangan') || label.includes('caption')) {
                                return el;
                            }
                        }
                        // Terakhir: ambil yang terakhir visible (biasanya overlay)
                        const visible = Array.from(all).filter(el => el.offsetParent !== null && !el.closest('footer'));
                        return visible[visible.length - 1];
                    }

                    const input = findCaptionInput();
                    if (input) {
                        input.focus();
                        // Gunakan ClipboardEvent paste (paling stabil untuk multi-line)
                        const dt = new DataTransfer();
                        dt.setData('text/plain', text);
                        input.dispatchEvent(new ClipboardEvent('paste', {
                            clipboardData: dt, bubbles: true, cancelable: true
                        }));
                    }
                }""", caption)
                time.sleep(1)
            
            # === STEP 4: Kirim ===
            # Cek tombol send di preview
            send_btn_sel = [
                '[data-testid="media-editor"] [data-testid="send"]',
                'span[data-icon="send"]',
                'button[aria-label="Send"]',
                'button[aria-label="Kirim"]'
            ]
            clicked = False
            for s in send_btn_sel:
                btn = self._safe_query(page, s)
                if btn:
                    btn.click()
                    clicked = True
                    break
            if not clicked:
                page.keyboard.press("Enter")
            
            time.sleep(2)
            
        except Exception as e:
            self.callback_log(f"   ⚠️ Gagal: {e}. Fallback teks...")
            try:
                page.keyboard.press("Escape")
                time.sleep(1)
                input_sel = 'div[contenteditable="true"][data-tab="10"]'
                page.click(input_sel)
                page.type(input_sel, caption)
                page.keyboard.press("Enter")
            except: pass


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
        self.tab_broadcast = self.tabview.add("Broadcast 💬")
        self.tab_instagram = self.tabview.add("Instagram 📸")

        self.broadcast_contacts = []
        self.bc_engine = None
        self.bc_image_path = None # Store attached image path
        self.current_ig_results = []
        self.ig_scraper_instance = None

        self._setup_scraper_tab()
        self._setup_saved_tab()
        self._setup_broadcast_tab()
        self._setup_instagram_tab()
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
    #  TAB 3: BROADCAST
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_broadcast_tab(self):
        # Sidebar - Menggunakan ScrollableFrame agar bisa di-scroll jika layar kecil
        sidebar = ctk.CTkScrollableFrame(self.tab_broadcast, width=300, fg_color=COLORS["bg_card"], corner_radius=15, scrollbar_fg_color="transparent")
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(inner, text="PENGATURAN BROADCAST", font=("Segoe UI Semibold", 14), text_color=COLORS["text_primary"]).pack(pady=(0,15))

        # Kontrol Sumber Data
        ctk.CTkLabel(inner, text="Sumber Kontak", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        btn_box = ctk.CTkFrame(inner, fg_color="transparent")
        btn_box.pack(fill="x", pady=(0, 15))
        
        ctk.CTkButton(btn_box, text="Daftar Tersimpan", fg_color=COLORS["bg_input"], hover_color=COLORS["border"], command=self._load_contacts_from_db, height=32).pack(side="left", expand=True, padx=(0,5))
        ctk.CTkButton(btn_box, text="Import Excel", fg_color=COLORS["bg_input"], hover_color=COLORS["border"], command=self._import_contacts_excel, height=32).pack(side="left", expand=True, padx=(5,0))

        self.label_total_bc = ctk.CTkLabel(inner, text="Penerima: 0 kontak", font=("Segoe UI", 11, "italic"), text_color=COLORS["accent_light"])
        self.label_total_bc.pack(anchor="w", pady=(0,10))

        # Input Pesan
        ctk.CTkLabel(inner, text="Pesan (Gunakan {nama} untuk variabel)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.txt_bc_message = ctk.CTkTextbox(inner, height=130, fg_color=COLORS["bg_input"], text_color="white", border_color=COLORS["border"], border_width=1)
        self.txt_bc_message.pack(fill="x", pady=(0, 15))
        self.txt_bc_message.insert("1.0", "Halo {nama},\n\nKami mendapatkan kontak Anda dari Google Maps. Apakah Anda tertarik dengan layanan kami?\n\nSalam.")

        # Safety Settings Grid
        safety_frame = ctk.CTkFrame(inner, fg_color="transparent")
        safety_frame.pack(fill="x", pady=(0, 10))
        
        # Row 1: Delays
        d_label = ctk.CTkLabel(safety_frame, text="⏳ Jeda Acak (detik)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        d_label.grid(row=0, column=0, columnspan=2, sticky="w")
        
        self.entry_delay_min = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Min", fg_color=COLORS["bg_input"], text_color="white")
        self.entry_delay_min.insert(0, "10")
        self.entry_delay_min.grid(row=1, column=0, sticky="w", pady=(0, 10), padx=(0, 5))
        
        self.entry_delay_max = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Max", fg_color=COLORS["bg_input"], text_color="white")
        self.entry_delay_max.insert(0, "30")
        self.entry_delay_max.grid(row=1, column=1, sticky="w", pady=(0, 10))

        # Row 2: Breaks
        b_label = ctk.CTkLabel(safety_frame, text="☕ Istirahat (Pesan / Menit)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        b_label.grid(row=2, column=0, columnspan=2, sticky="w")
        
        self.entry_break_every = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Tiap X", fg_color=COLORS["bg_input"], text_color="white")
        self.entry_break_every.insert(0, "50")
        self.entry_break_every.grid(row=3, column=0, sticky="w", pady=(0, 10), padx=(0, 5))
        
        self.entry_break_duration = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Lama", fg_color=COLORS["bg_input"], text_color="white")
        self.entry_break_duration.insert(0, "15")
        self.entry_break_duration.grid(row=3, column=1, sticky="w", pady=(0, 10))

        # Premium Extension Features
        ctk.CTkLabel(inner, text="FITUR LANJUTAN", font=("Segoe UI Semibold", 12), text_color=COLORS["accent_light"]).pack(anchor="w", pady=(10, 5))
        
        # Attachment Button
        self.btn_attach = ctk.CTkButton(inner, text="📸 Lampirkan Gambar (Opsional)", fg_color=COLORS["bg_input"], text_color="white", border_width=1, border_color=COLORS["border"], command=self._pick_bc_image)
        self.btn_attach.pack(fill="x", pady=5)
        self.label_image_status = ctk.CTkLabel(inner, text="Tidak ada gambar terpilih", font=("Segoe UI", 10), text_color=COLORS["text_secondary"])
        self.label_image_status.pack(anchor="w", pady=(0, 10))

        # Duplicate Check String
        ctk.CTkLabel(inner, text="🔍 Hindari Duplikat (Cari kata di chat)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.entry_bc_duplicate = ctk.CTkEntry(inner, placeholder_text="Contoh: Kami mendapatkan kontak", fg_color=COLORS["bg_input"], text_color="white")
        self.entry_bc_duplicate.pack(fill="x", pady=(0, 15))

        self.btn_bc_start = ctk.CTkButton(inner, text="Mulai Campaign Premium 🚀", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_broadcast, height=45, font=("Segoe UI Bold", 13))
        self.btn_bc_start.pack(fill="x", pady=(15, 5))

        self.btn_bc_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_broadcast)
        self.btn_bc_stop.pack(fill="x", pady=5)

        self.bc_progress = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["success"])
        self.bc_progress.set(0)
        self.bc_progress.pack(fill="x", pady=15)

        self.bc_log = ctk.CTkTextbox(inner, height=120, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color="white")
        self.bc_log.pack(fill="x")

        # Main Table
        main_area = ctk.CTkFrame(self.tab_broadcast, fg_color=COLORS["bg_card"], corner_radius=15)
        main_area.pack(side="right", fill="both", expand=True)

        # Header Table
        header = ctk.CTkFrame(main_area, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Daftar Penerima", font=("Segoe UI Semibold", 14)).pack(side="left")
        ctk.CTkButton(header, text="Bersihkan Daftar", width=120, fg_color="transparent", border_width=1, text_color=COLORS["danger"], border_color=COLORS["danger"], command=self._clear_broadcast_list).pack(side="right")

        # Treeview
        tree_container = ctk.CTkFrame(main_area, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.tree_bc = ttk.Treeview(tree_container, columns=("no", "nama", "telepon"), show="headings", style="Custom.Treeview")
        self.tree_bc.heading("no", text="No")
        self.tree_bc.column("no", width=50, anchor="center")
        self.tree_bc.heading("nama", text="Nama/Bisnis")
        self.tree_bc.column("nama", width=200)
        self.tree_bc.heading("telepon", text="Nomor Telepon")
        self.tree_bc.column("telepon", width=150)

        ysb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_bc.yview)
        self.tree_bc.configure(yscroll=ysb.set)
        
        self.tree_bc.tag_configure("odd", background=COLORS["table_row_1"])
        self.tree_bc.tag_configure("even", background=COLORS["table_row_2"])

        self.tree_bc.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 4: INSTAGRAM
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_instagram_tab(self):
        sidebar = ctk.CTkScrollableFrame(self.tab_instagram, width=300, fg_color=COLORS["bg_card"], corner_radius=15, scrollbar_fg_color="transparent")
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(inner, text="PENGATURAN INSTAGRAM", font=("Segoe UI Semibold", 14), text_color=COLORS["text_primary"]).pack(pady=(0,15))

        self.entry_ig_user = self._add_field(inner, "👤 Username", "Instagram Username")
        self.entry_ig_pass = self._add_field(inner, "🔑 Password", "Instagram Password")
        
        # Load from .env if exists
        try:
            from dotenv import load_dotenv
            load_dotenv()
            if os.getenv('INSTAGRAM_USERNAME'):
                self.entry_ig_user.insert(0, os.getenv('INSTAGRAM_USERNAME'))
            if os.getenv('INSTAGRAM_PASSWORD'):
                self.entry_ig_pass.insert(0, os.getenv('INSTAGRAM_PASSWORD'))
        except: pass
        
        # Headless Toggle (Set default to False so browser is visible)
        self.var_ig_headless = tk.BooleanVar(value=False)
        self.cb_ig_headless = ctk.CTkCheckBox(inner, text="Mode Headless (Tanpa Jendela)", variable=self.var_ig_headless, font=("Segoe UI", 11))
        self.cb_ig_headless.pack(anchor="w", pady=(0, 10))

        self.entry_ig_keyword = self._add_field(inner, "🔍 Keyword Pencarian", "Contoh: Jasa Desain")
        self.entry_ig_limit = self._add_field(inner, "📊 Batas Data", "20")

        self.btn_ig_start = ctk.CTkButton(inner, text="Mulai Scrape Instagram 🚀", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_ig_scraping, height=45, font=("Segoe UI Bold", 13))
        self.btn_ig_start.pack(fill="x", pady=(15, 5))

        self.btn_ig_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_ig_scraping)
        self.btn_ig_stop.pack(fill="x", pady=5)

        self.ig_progress = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["success"])
        self.ig_progress.set(0)
        self.ig_progress.pack(fill="x", pady=15)

        self.ig_log_box = ctk.CTkTextbox(inner, height=150, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color="white")
        self.ig_log_box.pack(fill="x")

        main_area = ctk.CTkFrame(self.tab_instagram, fg_color=COLORS["bg_card"], corner_radius=15)
        main_area.pack(side="right", fill="both", expand=True)
        
        # Table Header
        header = ctk.CTkFrame(main_area, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Hasil Scrape Instagram", font=("Segoe UI Semibold", 14)).pack(side="left")
        ctk.CTkButton(header, text="Export CSV", fg_color=COLORS["success"], width=100, command=self._export_ig_to_csv).pack(side="right", padx=5)

        # Treeview
        tree_container = ctk.CTkFrame(main_area, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("no", "full_name", "username", "followers", "following", "posts", "engagement", "email", "link")
        self.tree_ig = ttk.Treeview(tree_container, columns=cols, show="headings", style="Custom.Treeview")
        
        headings = {
            "no": "No", "full_name": "Nama Lengkap", "username": "Username", 
            "followers": "Followers", "following": "Following", "posts": "Posts",
            "engagement": "Engagement", "email": "Email", "link": "Link IG"
        }
        widths = {
            "no": 40, "full_name": 150, "username": 120, 
            "followers": 80, "following": 80, "posts": 60,
            "engagement": 100, "email": 150, "link": 150
        }

        for c, h in headings.items():
            self.tree_ig.heading(c, text=h)
            self.tree_ig.column(c, width=widths.get(c, 100))

        ysb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_ig.yview)
        self.tree_ig.configure(yscroll=ysb.set)
        
        self.tree_ig.tag_configure("odd", background=COLORS["table_row_1"])
        self.tree_ig.tag_configure("even", background=COLORS["table_row_2"])

        self.tree_ig.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

    def _ig_log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.ig_log_box.insert("end", f"[{timestamp}] {msg}\n")
        self.ig_log_box.see("end")

    def _start_ig_scraping(self):
        user = self.entry_ig_user.get().strip()
        pw = self.entry_ig_pass.get().strip()
        kw = self.entry_ig_keyword.get().strip()
        try: limit = int(self.entry_ig_limit.get() or 20)
        except: limit = 20
        
        if not kw:
            messagebox.showwarning("Peringatan", "Masukkan keyword untuk pencarian.")
            return
        
        self.btn_ig_start.configure(state="disabled", text="Scraping...")
        self.btn_ig_stop.configure(state="normal")
        self.ig_progress.set(0)
        # Clear table
        for item in self.tree_ig.get_children():
            self.tree_ig.delete(item)
        self.current_ig_results = []
        
        self.ig_scraper_instance = None
        
        def run_async_scraper():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # Update config with headless preference
            import json
            if os.path.exists('config.json'):
                try:
                    with open('config.json', 'r') as f: config = json.load(f)
                except: config = {}
            else: config = {}
            config['headless'] = self.var_ig_headless.get()
            
            self.ig_scraper_instance = InstagramScraper(
                username=user,
                password=pw,
                callback_log=lambda m, level="INFO": self.after(0, lambda: self._ig_log(f"{m}")),
                callback_result=lambda r: self.after(0, lambda: self._on_ig_result(r)),
                callback_progress=lambda c, t: self.after(0, lambda: self.ig_progress.set(c/t)),
                headless=self.var_ig_headless.get()
            )
            self.ig_scraper_instance.config['headless'] = self.var_ig_headless.get()
            self.ig_scraper_instance.headless = self.var_ig_headless.get()
            
            try:
                loop.run_until_complete(self.ig_scraper_instance.run(keyword=kw, limit=limit))
            except Exception as e:
                self.after(0, lambda: self._ig_log(f"Error: {str(e)}"))
            finally:
                loop.close()
                self.after(0, self._on_ig_done)

        threading.Thread(target=run_async_scraper, daemon=True).start()

    def _on_ig_result(self, res):
        idx = len(self.current_ig_results) + 1
        self.current_ig_results.append(res)
        tag = "even" if idx % 2 == 0 else "odd"
        
        self.tree_ig.insert("", "end", values=(
            idx,
            res.get("full_name", ""),
            res.get("username", ""),
            res.get("followers", 0),
            res.get("following", 0),
            res.get("post_count", 0),
            res.get("total_engagement", 0),
            res.get("email", ""),
            res.get("instagram_link", "")
        ), tags=(tag,))

    def _on_ig_done(self):
        self.btn_ig_start.configure(state="normal", text="Mulai Scrape Instagram 🚀")
        self.btn_ig_stop.configure(state="disabled")
        self._ig_log("✅ Scraping Instagram Selesai!")
        messagebox.showinfo("Selesai", "Scraping Instagram telah selesai.")

    def _stop_ig_scraping(self):
        if hasattr(self, 'ig_scraper_instance') and self.ig_scraper_instance:
            self._ig_log("🛑 Berhenti... (Sedang menutup browser)")
            self.ig_scraper_instance.shutdown = True

    def _export_ig_to_csv(self):
        if not hasattr(self, 'current_ig_results') or not self.current_ig_results:
            messagebox.showwarning("Peringatan", "Tidak ada data untuk diexport.")
            return
        
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            df = pd.DataFrame(self.current_ig_results)
            df.to_csv(path, index=False)
            messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {path}")

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

    # ═══════════════════════════════════════════════════════════════════════
    #  BROADCAST LOGIC
    # ═══════════════════════════════════════════════════════════════════════
    def _load_contacts_from_db(self):
        db = SessionLocal()
        try:
            leads = db.query(models.Lead).filter(models.Lead.phone != "").all()
            if not leads:
                messagebox.showinfo("Info", "Tidak ada data dengan nomor telepon di database.")
                return
            
            for l in leads:
                # Cek duplikat nomor sebelum tambah
                if any(c['phone'] == l.phone for c in self.broadcast_contacts):
                    continue
                self.broadcast_contacts.append({"name": l.name, "phone": l.phone})
            
            self._update_bc_table()
            messagebox.showinfo("Selesai", f"Berhasil menarik {len(leads)} kontak dari database.")
        finally:
            db.close()

    def _import_contacts_excel(self):
        path = filedialog.askopenfilename(filetypes=[("Excel/CSV", "*.xlsx *.csv")])
        if not path: return

        try:
            if path.endswith('.csv'):
                df = pd.read_csv(path)
            else:
                df = pd.read_excel(path)
            
            # Cari kolom yang mirip 'phone' atau 'telepon'
            phone_col = None
            name_col = None
            
            for col in df.columns:
                c_low = str(col).lower()
                if 'phone' in c_low or 'telepon' in c_low or 'no' in c_low and 'hp' in c_low:
                    phone_col = col
                if 'name' in c_low or 'nama' in c_low:
                    name_col = col
            
            if phone_col is None:
                messagebox.showerror("Error", "Gagal menemukan kolom nomor telepon. Pastikan nama kolom berisi kata 'phone' atau 'telepon'.")
                return

            added = 0
            for _, row in df.iterrows():
                phone = str(row[phone_col])
                if phone and phone != 'nan':
                    name = str(row[name_col]) if name_col and str(row[name_col]) != 'nan' else "Pelanggan"
                    self.broadcast_contacts.append({"name": name, "phone": phone})
                    added += 1
            
            self._update_bc_table()
            messagebox.showinfo("Selesai", f"Berhasil mengimport {added} kontak.")
        except Exception as e:
            messagebox.showerror("Error", f"Gagal membaca file: {str(e)}")

    def _update_bc_table(self):
        for item in self.tree_bc.get_children(): self.tree_bc.delete(item)
        for i, c in enumerate(self.broadcast_contacts):
            tag = "even" if i % 2 == 0 else "odd"
            self.tree_bc.insert("", "end", values=(i+1, c['name'], c['phone']), tags=(tag,))
        self.label_total_bc.configure(text=f"Penerima: {len(self.broadcast_contacts)} kontak")

    def _clear_broadcast_list(self):
        self.broadcast_contacts = []
        self._update_bc_table()

    def _start_broadcast(self):
        if not self.broadcast_contacts:
            messagebox.showwarning("Daftar Kosong", "Belum ada kontak penerima.")
            return
        
        msg = self.txt_bc_message.get("1.0", "end-1c").strip()
        if not msg:
            messagebox.showwarning("Pesan Kosong", "Harap isi pesan broadcast.")
            return

        try:
            d_min = int(self.entry_delay_min.get() or 10)
            d_max = int(self.entry_delay_max.get() or 30)
            b_every = int(self.entry_break_every.get() or 50)
            b_dur = int(self.entry_break_duration.get() or 15)
        except:
            d_min, d_max, b_every, b_dur = 10, 30, 50, 15

        self.btn_bc_start.configure(state="disabled")
        self.btn_bc_stop.configure(state="normal")
        
        self.bc_engine = BroadcastEngine(
            callback_log=self._log_bc,
            callback_progress=lambda c, t: self.after(0, lambda: self.bc_progress.set(c/t)),
            callback_done=self._on_finish_bc
        )
        # Menggunakan kwargs agar pemetaan parameter ke fungsi .run() lebih terjamin dan aman
        threading.Thread(
            target=self.bc_engine.run, 
            kwargs={
                "contacts": self.broadcast_contacts,
                "message_template": msg,
                "delay_min": d_min,
                "delay_max": d_max,
                "break_every": b_every,
                "break_duration": b_dur,
                "image_path": self.bc_image_path
            }, 
            daemon=True
        ).start()

    def _log_bc(self, msg):
        self.after(0, lambda: (self.bc_log.insert("end", f"{msg}\n"), self.bc_log.see("end")))

    def _on_finish_bc(self):
        self.after(0, lambda: (
            self.btn_bc_start.configure(state="normal"),
            self.btn_bc_stop.configure(state="disabled"),
            self._log_bc("🏁 Broadcast Selesai.")
        ))

    def _stop_broadcast(self):
        if self.bc_engine: self.bc_engine.stop()

    def _pick_bc_image(self):
        path = filedialog.askopenfilename(filetypes=[("Images", "*.jpg *.jpeg *.png *.webp")])
        if path:
            self.bc_image_path = path
            self.label_image_status.configure(text=f"✅ {os.path.basename(path)}", text_color=COLORS["success"])
        else:
            self.bc_image_path = None
            self.label_image_status.configure(text="Tidak ada gambar terpilih", text_color=COLORS["text_secondary"])

    def _start_broadcast(self):
        if not self.broadcast_contacts:
            messagebox.showwarning("Daftar Kosong", "Belum ada kontak penerima.")
            return
        
        msg = self.txt_bc_message.get("1.0", "end-1c").strip()
        if not msg:
            messagebox.showwarning("Pesan Kosong", "Harap isi pesan broadcast.")
            return

        try:
            d_min = int(self.entry_delay_min.get() or 10)
            d_max = int(self.entry_delay_max.get() or 30)
            b_every = int(self.entry_break_every.get() or 50)
            b_dur = int(self.entry_break_duration.get() or 15)
        except:
            d_min, d_max, b_every, b_dur = 10, 30, 50, 15

        self.btn_bc_start.configure(state="disabled")
        self.btn_bc_stop.configure(state="normal")
        
        self.bc_engine = BroadcastEngine(
            callback_log=self._log_bc,
            callback_progress=lambda c, t: self.after(0, lambda: self.bc_progress.set(c/t)),
            callback_done=self._on_finish_bc
        )
        # Menjalankan broadcast di thread terpisah agar UI tidak membeku
        threading.Thread(
            target=self.bc_engine.run, 
            args=(self.broadcast_contacts, msg, d_min, d_max, b_every, b_dur, self.bc_image_path, self.entry_bc_duplicate.get().strip()), 
            daemon=True
        ).start()

if __name__ == "__main__":
    app = ModernApp()
    app.mainloop()
