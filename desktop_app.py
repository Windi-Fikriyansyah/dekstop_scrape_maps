import os
import sys
import multiprocessing
import asyncio

# PENTING: Paksa Playwright menggunakan lokasi browser global (WAJIB paling atas)
# PENTING: Paksa Playwright menggunakan lokasi browser lokal agar portable dan stabil
# --- Path Configuration ---
if getattr(sys, 'frozen', False):
    # Lokasi aplikasi (.exe)
    EXE_DIR = os.path.dirname(sys.executable)
    
    # Prioritas 1: Cek folder 'pw-browsers' yang dibundel di dalam folder aplikasi (PORTABLE MODE)
    # PyInstaller 6+ menyimpan data di folder '_internal'
    PORTABLE_BROWSER_DIR = os.path.join(EXE_DIR, "_internal", "pw-browsers")
    if not os.path.exists(PORTABLE_BROWSER_DIR):
        PORTABLE_BROWSER_DIR = os.path.join(EXE_DIR, "pw-browsers")

    if os.path.exists(PORTABLE_BROWSER_DIR):
        BROWSER_DIR = PORTABLE_BROWSER_DIR
        STORAGE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "WAMaps")
    else:
        # Prioritas 2: AppData (Download on demand)
        STORAGE_DIR = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "WAMaps")
        BROWSER_DIR = os.path.join(STORAGE_DIR, "pw-browsers")
else:
    # Jika dijalankan sebagai script python
    STORAGE_DIR = os.getcwd()
    BROWSER_DIR = os.path.join(STORAGE_DIR, "pw-browsers")

os.makedirs(STORAGE_DIR, exist_ok=True)
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = BROWSER_DIR

import csv
import random
import re
import threading
import time
import tkinter as tk
import urllib.parse
import requests
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
# Paksa CustomTkinter ke mode terang (light)
ctk.set_appearance_mode("light")
import pandas as pd
from playwright.sync_api import sync_playwright


try:
    from staffspy import LinkedInAccount
except ImportError:
    LinkedInAccount = None

try:
    from social_engine import SocialEngine
except ImportError:
    SocialEngine = None

try:
    from email_social_engine import EmailSocialEngine
except ImportError:
    EmailSocialEngine = None

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
EXCLUDED_DOMAINS = ["google.com", "facebook.com"]

# ─── Color Palette ────────────────────────────────────────────────────────────
COLORS = {
    "bg_light":     "#f5f7fb",   # Latar umum aplikasi
    "bg_card":      "#ffffff",   # Kartu / panel
    "bg_input":     "#f0f4f8",   # Field input
    "accent":       "#2d6cdf",   # Biru aksen
    "accent_hover": "#2458b8",
    "accent_light": "#6ea8ff",
    "success":      "#28a745",
    "warning":      "#f0ad4e",
    "danger":       "#dc3545",
    "text_primary": "#0f1724",
    "text_secondary":"#4b5563",
    "text_muted":   "#6b7280",
    "border":       "#e5e7eb",
    "table_row_1":  "#ffffff",
    "table_row_2":  "#f8fafc",
    "table_header": "#f1f5f9",
}

# --- Country Codes Data ---
COUNTRY_DATA = [
    ("Afghanistan", "93"), ("Albania", "355"), ("Algeria", "213"), ("Andorra", "376"),
    ("Angola", "244"), ("Argentina", "54"), ("Armenia", "374"), ("Australia", "61"),
    ("Austria", "43"), ("Azerbaijan", "994"), ("Bahamas", "1242"), ("Bahrain", "973"),
    ("Bangladesh", "880"), ("Barbados", "1246"), ("Belarus", "375"), ("Belgium", "32"),
    ("Belize", "501"), ("Benin", "229"), ("Bhutan", "975"), ("Bolivia", "591"),
    ("Bosnia and Herzegovina", "387"), ("Botswana", "267"), ("Brazil", "55"), ("Brunei", "673"),
    ("Bulgaria", "359"), ("Burkina Faso", "226"), ("Burundi", "257"), ("Cambodia", "855"),
    ("Cameroon", "237"), ("Canada", "1"), ("Cape Verde", "238"), ("Central African Republic", "236"),
    ("Chad", "235"), ("Chile", "56"), ("China", "86"), ("Colombia", "57"),
    ("Comoros", "269"), ("Congo", "242"), ("Cook Islands", "682"), ("Costa Rica", "506"),
    ("Croatia", "385"), ("Cuba", "53"), ("Cyprus", "357"), ("Czech Republic", "420"),
    ("Denmark", "45"), ("Djibouti", "253"), ("Dominica", "1767"), ("Dominican Republic", "1809"),
    ("Ecuador", "593"), ("Egypt", "20"), ("El Salvador", "503"), ("Equatorial Guinea", "240"),
    ("Eritrea", "291"), ("Estonia", "372"), ("Ethiopia", "251"), ("Fiji", "679"),
    ("Finland", "358"), ("France", "33"), ("Gabon", "241"), ("Gambia", "220"),
    ("Georgia", "995"), ("Germany", "49"), ("Ghana", "233"), ("Greece", "30"),
    ("Grenada", "1473"), ("Guatemala", "502"), ("Guinea", "224"), ("Guinea-Bissau", "245"),
    ("Guyana", "592"), ("Haiti", "509"), ("Honduras", "504"), ("Hong Kong", "852"),
    ("Hungary", "36"), ("Iceland", "354"), ("India", "91"), ("Indonesia", "62"),
    ("Iran", "98"), ("Iraq", "964"), ("Ireland", "353"), ("Israel", "972"),
    ("Italy", "39"), ("Jamaica", "1876"), ("Japan", "81"), ("Jordan", "962"),
    ("Kazakhstan", "7"), ("Kenya", "254"), ("Kiribati", "686"), ("Kuwait", "965"),
    ("Kyrgyzstan", "996"), ("Laos", "856"), ("Latvia", "371"), ("Lebanon", "961"),
    ("Lesotho", "266"), ("Liberia", "231"), ("Libya", "218"), ("Liechtenstein", "423"),
    ("Lithuania", "370"), ("Luxembourg", "352"), ("Macau", "853"), ("Macedonia", "389"),
    ("Madagascar", "261"), ("Malawi", "265"), ("Malaysia", "60"), ("Maldives", "960"),
    ("Mali", "223"), ("Malta", "356"), ("Marshall Islands", "692"), ("Mauritania", "222"),
    ("Mauritius", "230"), ("Mexico", "52"), ("Micronesia", "691"), ("Moldova", "373"),
    ("Monaco", "377"), ("Mongolia", "976"), ("Montenegro", "382"), ("Montserrat", "1664"),
    ("Morocco", "212"), ("Mozambique", "258"), ("Myanmar", "95"), ("Namibia", "264"),
    ("Nauru", "674"), ("Nepal", "977"), ("Netherlands", "31"), ("New Zealand", "64"),
    ("Nicaragua", "505"), ("Niger", "227"), ("Nigeria", "234"), ("Niue", "683"),
    ("North Korea", "850"), ("Norway", "47"), ("Oman", "968"), ("Pakistan", "92"),
    ("Palau", "680"), ("Panama", "507"), ("Papua New Guinea", "675"), ("Paraguay", "595"),
    ("Peru", "51"), ("Philippines", "63"), ("Poland", "48"), ("Portugal", "351"),
    ("Puerto Rico", "1787"), ("Qatar", "974"), ("Romania", "40"), ("Russia", "7"),
    ("Rwanda", "250"), ("Samoa", "685"), ("San Marino", "378"), ("Saudi Arabia", "966"),
    ("Senegal", "221"), ("Serbia", "381"), ("Seychelles", "248"), ("Sierra Leone", "232"),
    ("Singapore", "65"), ("Slovakia", "421"), ("Slovenia", "386"), ("Solomon Islands", "677"),
    ("Somalia", "252"), ("South Africa", "27"), ("South Korea", "82"), ("Spain", "34"),
    ("Sri Lanka", "94"), ("Sudan", "249"), ("Suriname", "597"), ("Swaziland", "268"),
    ("Sweden", "46"), ("Switzerland", "41"), ("Syria", "963"), ("Taiwan", "886"),
    ("Tajikistan", "992"), ("Tanzania", "255"), ("Thailand", "66"), ("Togo", "228"),
    ("Tonga", "676"), ("Trinidad and Tobago", "1868"), ("Tunisia", "216"), ("Turkey", "90"),
    ("Turkmenistan", "993"), ("Tuvalu", "688"), ("Uganda", "256"), ("Ukraine", "380"),
    ("United Arab Emirates", "971"), ("United Kingdom", "44"), ("United States", "1"),
    ("Uruguay", "598"), ("Uzbekistan", "998"), ("Vanuatu", "678"), ("Venezuela", "58"),
    ("Vietnam", "84"), ("Yemen", "967"), ("Zambia", "260"), ("Zimbabwe", "263")
]



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

    def run(self, contacts, message_template, delay_min=10, delay_max=30, break_every=50, break_duration=10, image_path=None, check_string=None, default_country_code="62"):
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
                data_dir = os.path.join(STORAGE_DIR, "wa_session")
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
                    
                    # Normalisasi Nomor (Mendukung Internasional)
                    phone_raw = str(contact.get('phone', '')).strip()
                    is_international = phone_raw.startswith('+')
                    
                    phone = re.sub(r'[^\d]', '', phone_raw)
                    if not phone or len(phone) < 8:
                        self.callback_log(f"⏭️ [{idx+1}/{total}] Nomor tidak valid, dilewati.")
                        skipped_count += 1
                        self.callback_progress(idx + 1, total)
                        continue
                    
                    if phone.startswith('0'):
                        # Jika diawali 0, ganti dengan kode negara default
                        phone = default_country_code + phone[1:]
                    elif not is_international and not phone.startswith(default_country_code) and len(phone) < 11:
                        # Jika nomor pendek dan tidak diawali kode default, tambahkan default sebagai pengaman
                        phone = default_country_code + phone

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



class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("WAMaps - Login")
        self.geometry("400x600")
        self.configure(fg_color=COLORS["bg_light"])
        self.resizable(True, True)
        
        # Center the window
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (400 // 2)
        y = (screen_height // 2) - (550 // 2)
        self.geometry(f"400x550+{x}+{y}")
        
        self.login_successful = False
        
        # API Configuration
        # Defaults to localhost for development, but can be changed
        self.api_base_url = os.environ.get("WAMAPS_API_URL", "https://apiwamaps.myxyzz.online")

        # UI Elements
        self.main_frame = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=20)
        self.main_frame.pack(expand=True, fill="both", padx=30, pady=30)
        
        # Logo / Icon placeholder
        self.logo_label = ctk.CTkLabel(
            self.main_frame, 
            text="📍", 
            font=("Segoe UI", 48)
        )
        self.logo_label.pack(pady=(20, 5))
        
        self.title_label = ctk.CTkLabel(
            self.main_frame, 
            text="WAMaps", 
            font=("Segoe UI Bold", 28), 
            text_color=COLORS["accent"]
        )
        self.title_label.pack(pady=(0, 5))
        
        self.subtitle_label = ctk.CTkLabel(
            self.main_frame, 
            text="Lead Generation Solution", 
            font=("Segoe UI", 12), 
            text_color=COLORS["text_secondary"]
        )
        self.subtitle_label.pack(pady=(0, 20))
        
        # Input Fields Container
        self.input_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.input_container.pack(fill="x", padx=30)
        
        # Email Field
        ctk.CTkLabel(self.input_container, text="Email Address", font=("Segoe UI Semibold", 12), text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 5))
        self.entry_email = ctk.CTkEntry(
            self.input_container, 
            placeholder_text="name@example.com", 
            height=45, 
            fg_color=COLORS["bg_input"], 
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.entry_email.pack(fill="x", pady=(0, 15))
        
        # Password Field
        ctk.CTkLabel(self.input_container, text="Password", font=("Segoe UI Semibold", 12), text_color=COLORS["text_primary"]).pack(anchor="w", pady=(0, 5))
        self.entry_password = ctk.CTkEntry(
            self.input_container, 
            placeholder_text="••••••••", 
            show="*", 
            height=45, 
            fg_color=COLORS["bg_input"], 
            border_color=COLORS["border"],
            text_color=COLORS["text_primary"]
        )
        self.entry_password.pack(fill="x", pady=(0, 10))
        
        # Status Label (untuk pesan error)
        self.status_label = ctk.CTkLabel(
            self.main_frame, 
            text="", 
            font=("Segoe UI", 11), 
            text_color=COLORS["danger"],
            wraplength=300
        )
        self.status_label.pack(pady=2)
        
        # --- BUTTON SECTION ---
        self.button_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_container.pack(fill="x", padx=30, pady=(5, 10))
        
        # Main Login Button
        self.btn_login = ctk.CTkButton(
            self.button_container, 
            text="MASUK KE AKUN", 
            command=self._handle_login, 
            height=50, 
            fg_color=COLORS["accent"], 
            hover_color=COLORS["accent_hover"],
            font=("Segoe UI Bold", 14),
            corner_radius=12
        )
        self.btn_login.pack(fill="x", pady=(0, 10))
        
        # Exit Button
        self.btn_exit = ctk.CTkButton(
            self.button_container, 
            text="Keluar Aplikasi", 
            command=self.destroy, 
            height=35, 
            fg_color="transparent", 
            border_width=1,
            border_color=COLORS["border"],
            text_color=COLORS["text_secondary"],
            hover_color=COLORS["bg_input"],
            font=("Segoe UI", 12),
            corner_radius=10
        )
        self.btn_exit.pack(fill="x")
        
        # Version Tag
        self.version_label = ctk.CTkLabel(
            self.main_frame, 
            text="WAMaps v1.0.0", 
            font=("Segoe UI", 10), 
            text_color=COLORS["text_muted"]
        )
        self.version_label.pack(side="bottom", pady=5)
        
        # Bind Enter key untuk login cepat
        self.bind("<Return>", lambda event: self._handle_login())

    def _handle_login(self):
        email = self.entry_email.get().strip()
        password = self.entry_password.get().strip()
        
        if not email or not password:
            self.status_label.configure(text="Email dan password wajib diisi!")
            return
            
        self.btn_login.configure(state="disabled", text="Memverifikasi...")
        self.status_label.configure(text="")
        self.update()
        
        try:
            # Login via API (OAuth2PasswordRequestForm expects form-data)
            login_url = f"{self.api_base_url}/auth/login"
            payload = {
                "username": email,
                "password": password
            }
            
            response = requests.post(login_url, data=payload, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Store token if needed for future authenticated requests
                self.token = data.get("access_token")
                self.login_successful = True
                self.destroy()
            else:
                try:
                    error_msg = response.json().get("detail", "Email atau password salah")
                except:
                    error_msg = "Gagal terhubung ke server login"
                self.status_label.configure(text=error_msg)
                self.btn_login.configure(state="normal", text="Login Sekarang")
        except requests.exceptions.ConnectionError:
            self.status_label.configure(text="Gagal terhubung ke server (Offline)")
            self.btn_login.configure(state="normal", text="Login Sekarang")
        except Exception as e:
            self.status_label.configure(text=f"Error: {str(e)}")
            self.btn_login.configure(state="normal", text="Login Sekarang")


class ModernApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ─── Window Setup ─────────────────────────────────────────────────
        self.title("WAMaps - Admin Dashboard")
        # Start with a more minimalist size
        self.geometry("1000x650")
        self.minsize(800, 550)
        self.configure(fg_color=COLORS["bg_light"]) 

        self.engine = None
        self.current_results = []
        self.current_page = None  # Track active page
        self.page_frames = {}  # Store page frames

        # ─── Layout ───────────────────────────────────────────────────────
        # Header (Admin dashboard style)
        header_bar = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], height=64)
        header_bar.pack(fill="x", padx=10, pady=(10, 6))
        header_bar.pack_propagate(False)
        ctk.CTkLabel(header_bar, text="Admin Dashboard", font=("Segoe UI Bold", 18), text_color=COLORS["text_primary"]).pack(side="left", padx=12)
        ctk.CTkLabel(header_bar, text="👤 Admin", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(side="right", padx=12)

        # Main container (sidebar + content)
        main_container = ctk.CTkFrame(self, fg_color=COLORS["bg_light"])
        main_container.pack(fill="both", expand=True, padx=10, pady=10)

        # ─── SIDEBAR (Left Navigation Menu) ───────────────────────────────
        self.sidebar = ctk.CTkFrame(main_container, width=220, fg_color=COLORS["bg_card"], corner_radius=15)
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        sidebar_inner = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent", scrollbar_fg_color=COLORS["border"])
        sidebar_inner.pack(fill="both", expand=True, padx=10, pady=10)

        # Sidebar menu items
        self.menu_items = {
            "scraper": ("🔍 Scraper", "scraper"),
            "saved": ("📁 Data Tersimpan", "saved"),
            "broadcast": ("💬 Broadcast", "broadcast"),
            "linkedin": ("💼 LinkedIn", "linkedin"),
            "social": ("🌐 Social Media (WA)", "social"),
            "social_email": ("📧 Social Media (Email)", "social_email"),
        }

        self.menu_buttons = {}
        for key, (label, page_id) in self.menu_items.items():
            btn = ctk.CTkButton(
                sidebar_inner, 
                text=label, 
                fg_color=COLORS["bg_input"], 
                hover_color=COLORS["accent"],
                text_color=COLORS["text_primary"],
                command=lambda p=page_id: self._switch_page(p),
                height=45,
                font=("Segoe UI", 11),
                corner_radius=10
            )
            btn.pack(fill="x", pady=5)
            self.menu_buttons[page_id] = btn

        # ─── CONTENT AREA (Right main content) ─────────────────────────────
        self.content_area = ctk.CTkFrame(main_container, fg_color=COLORS["bg_light"], corner_radius=15)
        self.content_area.pack(side="right", fill="both", expand=True)

        # Create page frames (hidden by default)
        self.tab_scraper = self._create_page("scraper")
        self.tab_saved = self._create_page("saved")
        self.tab_broadcast = self._create_page("broadcast")
        self.tab_linkedin = self._create_page("linkedin")
        self.tab_social = self._create_page("social")
        self.tab_social_email = self._create_page("social_email")

        self.broadcast_contacts = []
        self.bc_engine = None
        self.bc_image_path = None # Store attached image path
        self.current_li_results = []
        self.current_social_results = []
        self.social_engine_instance = None
        self.current_social_email_results = []
        self.social_email_engine_instance = None

        self._setup_scraper_tab()
        self._setup_saved_tab()
        self._setup_broadcast_tab()

        self._setup_linkedin_tab()
        self._setup_social_tab()
        self._setup_social_email_tab()
        self._setup_styles()

        # Switch to first page (Scraper)
        self._switch_page("scraper")
        
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
                import playwright
                from pathlib import Path
                
                # Cari lokasi driver playwright yang dibundel
                driver_path = Path(playwright.__file__).parent / "driver"
                # Pada macOS/Linux nama executable-nya adalah 'node', bukan 'node.exe'
                node_name = "node.exe" if os.name == "nt" else "node"
                node_exe = driver_path / node_name
                cli_js = driver_path / "package" / "cli.js"
                
                if getattr(sys, 'frozen', False) and node_exe.exists() and cli_js.exists():
                    self._log(f"📍 Menggunakan driver bundled: {node_exe.name}")
                    cmd = [str(node_exe), str(cli_js), "install", "chromium"]
                else:
                    # Fallback jika tidak frozen atau driver bundled tidak ditemukan
                    if getattr(sys, 'frozen', False):
                        # Jika frozen (EXE/APP) tapi node bundled tidak ditemukan, 
                        # sys.executable adalah binary app itu sendiri yang tidak mendukung flag '-m'.
                        # Kita coba gunakan 'python3' sistem sebagai harapan terakhir.
                        cmd = ["python3", "-m", "playwright", "install", "chromium"]
                    else:
                        cmd = [sys.executable, "-m", "playwright", "install", "chromium"]

                self._log(f"🚀 Memproses instalasi browser...")
                
                # Gunakan STARTUPINFO untuk menyembunyikan jendela console subprocess di Windows (EXE)
                startupinfo = None
                if os.name == 'nt' and getattr(sys, 'frozen', False):
                    startupinfo = subprocess.STARTUPINFO()
                    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    startupinfo.wShowWindow = 0 # SW_HIDE

                process = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    startupinfo=startupinfo,
                    env=os.environ.copy()
                )
                
                if process.returncode == 0:
                    if check_playwright_browser():
                        self._log("✅ Browser berhasil diinstal!")
                    else:
                        self._log("❌ Instalasi selesai tapi browser masih belum terdeteksi.")
                        self._log(f"DEBUG info: {process.stdout}")
                else:
                    error_msg = (process.stderr or "").strip() or (process.stdout or "").strip() or "No output from process."
                    self._log(f"❌ Detail Eror (Code {process.returncode}): {error_msg}")
                    raise Exception(f"Eror {process.returncode}: {error_msg}")
            except Exception as e:
                self._log(f"❌ Gagal menginstal: {str(e)}")
                messagebox.showerror("Error Browser", f"Gagal mengunduh browser:\n\n{str(e)}\n\nPastikan Anda terhubung ke internet.")
        else:
            self._log("✅ Sistem browser siap!")
            
        self.after(500, lambda: self.btn_start.configure(state="normal", text="Mulai Scraping"))

    def _create_page(self, page_id):
        """Buat frame untuk setiap halaman (page)."""
        page_frame = ctk.CTkFrame(self.content_area, fg_color=COLORS["bg_light"], corner_radius=15)
        page_frame.pack(fill="both", expand=True)
        page_frame.pack_forget()  # Hide by default
        self.page_frames[page_id] = page_frame
        return page_frame

    def _switch_page(self, page_id):
        """Switch halaman aktif dan update tombol sidebar."""
        # Hide semua halaman
        for frame in self.page_frames.values():
            frame.pack_forget()
        
        # Show halaman yang dipilih
        if page_id in self.page_frames:
            self.page_frames[page_id].pack(fill="both", expand=True)
            self.current_page = page_id
        
        # Update button styling (highlight tombol aktif)
        for btn_id, btn in self.menu_buttons.items():
            if btn_id == page_id:
                btn.configure(fg_color=COLORS["accent"], text_color="white")
            else:
                btn.configure(fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])

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

        self.log_text = ctk.CTkTextbox(inner, height=120, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
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

        self.var_saved_filter = tk.StringVar(value="Google Maps")
        self.filter_saved = ctk.CTkOptionMenu(
            top_bar, 
            variable=self.var_saved_filter, 
            values=["Google Maps", "Social Media", "Social Email"],
            command=self._on_saved_filter_change,
            width=140
        )
        self.filter_saved.pack(side="left", padx=15)

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
        self.txt_bc_message = ctk.CTkTextbox(inner, height=130, fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"], border_color=COLORS["border"], border_width=1)
        self.txt_bc_message.pack(fill="x", pady=(0, 15))
        self.txt_bc_message.insert("1.0", "Halo {nama},\n\nKami mendapatkan kontak Anda dari Google Maps. Apakah Anda tertarik dengan layanan kami?\n\nSalam.")

        # Safety Settings Grid
        safety_frame = ctk.CTkFrame(inner, fg_color="transparent")
        safety_frame.pack(fill="x", pady=(0, 10))
        
        # Row 1: Delays
        d_label = ctk.CTkLabel(safety_frame, text="⏳ Jeda Acak (detik)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        d_label.grid(row=0, column=0, columnspan=2, sticky="w")
        
        self.entry_delay_min = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Min", fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.entry_delay_min.insert(0, "10")
        self.entry_delay_min.grid(row=1, column=0, sticky="w", pady=(0, 10), padx=(0, 5))
        
        self.entry_delay_max = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Max", fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.entry_delay_max.insert(0, "30")
        self.entry_delay_max.grid(row=1, column=1, sticky="w", pady=(0, 10))

        # Row 2: Breaks
        b_label = ctk.CTkLabel(safety_frame, text="☕ Istirahat (Pesan / Menit)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        b_label.grid(row=2, column=0, columnspan=2, sticky="w")
        
        self.entry_break_every = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Tiap X", fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.entry_break_every.insert(0, "50")
        self.entry_break_every.grid(row=3, column=0, sticky="w", pady=(0, 10), padx=(0, 5))
        
        self.entry_break_duration = ctk.CTkEntry(safety_frame, width=60, placeholder_text="Lama", fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.entry_break_duration.insert(0, "15")
        self.entry_break_duration.grid(row=3, column=1, sticky="w", pady=(0, 10))

        # Premium Extension Features
        ctk.CTkLabel(inner, text="FITUR LANJUTAN", font=("Segoe UI Semibold", 12), text_color=COLORS["accent_light"]).pack(anchor="w", pady=(10, 5))
        
        # Attachment Button
        self.btn_attach = ctk.CTkButton(inner, text="📸 Lampirkan Gambar (Opsional)", fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"], border_width=1, border_color=COLORS["border"], command=self._pick_bc_image)
        self.btn_attach.pack(fill="x", pady=5)
        self.label_image_status = ctk.CTkLabel(inner, text="Tidak ada gambar terpilih", font=("Segoe UI", 10), text_color=COLORS["text_secondary"])
        self.label_image_status.pack(anchor="w", pady=(0, 10))

        # Duplicate Check String
        ctk.CTkLabel(inner, text="🔍 Hindari Duplikat (Cari kata di chat)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.entry_bc_duplicate = ctk.CTkEntry(inner, placeholder_text="Contoh: Kami mendapatkan kontak", fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.entry_bc_duplicate.pack(fill="x", pady=(0, 15))

        # International Settings
        ctk.CTkLabel(inner, text="🌐 Pengaturan Internasional", font=("Segoe UI Semibold", 12), text_color=COLORS["accent_light"]).pack(anchor="w", pady=(5, 5))
        ctk.CTkLabel(inner, text="Pilih Negara (Default)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        
        # Buat list untuk dropdown
        self.country_options = [f"{n} (+{c})" for n, c in COUNTRY_DATA]
        self.combo_country = ctk.CTkComboBox(
            inner, 
            values=self.country_options, 
            fg_color=COLORS["bg_input"], 
            text_color=COLORS["text_primary"], 
            border_color=COLORS["border"],
            dropdown_fg_color=COLORS["bg_card"],
            dropdown_hover_color=COLORS["accent"],
            dropdown_text_color=COLORS["text_primary"],
            button_color=COLORS["accent"],
            height=35
        )
        self.combo_country.set("Indonesia (+62)")
        self.combo_country.pack(fill="x", pady=(0, 15))

        self.btn_bc_start = ctk.CTkButton(inner, text="Mulai Campaign Premium 🚀", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_broadcast, height=45, font=("Segoe UI Bold", 13))
        self.btn_bc_start.pack(fill="x", pady=(15, 5))

        self.btn_bc_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_broadcast)
        self.btn_bc_stop.pack(fill="x", pady=5)

        self.bc_progress = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["success"])
        self.bc_progress.set(0)
        self.bc_progress.pack(fill="x", pady=15)

        self.bc_log = ctk.CTkTextbox(inner, height=120, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
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
    #  TAB 5: LINKEDIN
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_linkedin_tab(self):
        sidebar = ctk.CTkScrollableFrame(self.tab_linkedin, width=300, fg_color=COLORS["bg_card"], corner_radius=15, scrollbar_fg_color="transparent")
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(inner, text="PENGATURAN LINKEDIN", font=("Segoe UI Semibold", 14), text_color=COLORS["text_primary"]).pack(pady=(0,15))

        self.var_li_target_type = tk.StringVar(value="Staff Perusahaan")
        self.opt_li_type = ctk.CTkOptionMenu(
            inner, 
            variable=self.var_li_target_type, 
            values=["Staff Perusahaan", "Cari User (by ID)", "Komentar Posting (Post ID)", "Detail Perusahaan", "Koneksi Saya"],
            command=self._on_li_type_change
        )
        self.opt_li_type.pack(fill="x", pady=(0, 15))

        self.lbl_li_target = ctk.CTkLabel(inner, text="🏢 Target Pencarian", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        self.lbl_li_target.pack(anchor="w")
        self.entry_li_target = ctk.CTkEntry(inner, placeholder_text="Contoh: tokopedia", fg_color=COLORS["bg_input"], border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.entry_li_target.pack(fill="x", pady=(0, 10))

        self.lbl_li_keyword = ctk.CTkLabel(inner, text="🔍 Role / Posisi (Khusus Staff)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        self.lbl_li_keyword.pack(anchor="w")
        self.entry_li_keyword = ctk.CTkEntry(inner, placeholder_text="Contoh: software engineer", fg_color=COLORS["bg_input"], border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.entry_li_keyword.pack(fill="x", pady=(0, 10))

        self.lbl_li_location = ctk.CTkLabel(inner, text="📍 Lokasi (Khusus Staff)", font=("Segoe UI", 11), text_color=COLORS["text_secondary"])
        self.lbl_li_location.pack(anchor="w")
        self.entry_li_location = ctk.CTkEntry(inner, placeholder_text="Contoh: indonesia", fg_color=COLORS["bg_input"], border_color=COLORS["border"], text_color=COLORS["text_primary"])
        self.entry_li_location.pack(fill="x", pady=(0, 10))

        self.entry_li_limit = self._add_field(inner, "📊 Batas Data", "20")
        
        self.var_li_extra = tk.BooleanVar(value=True)
        self.cb_li_extra = ctk.CTkCheckBox(inner, text="Ambil Data Ekstra (Pengalaman, dll)", variable=self.var_li_extra, font=("Segoe UI", 11))
        self.cb_li_extra.pack(anchor="w", pady=(0, 10))

        self.btn_li_start = ctk.CTkButton(inner, text="Mulai Scrape LinkedIn 🚀", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_li_scraping, height=45, font=("Segoe UI Bold", 13))
        self.btn_li_start.pack(fill="x", pady=(15, 5))

        self.btn_li_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_li_scraping)
        self.btn_li_stop.pack(fill="x", pady=5)

        self.li_progress = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["success"])
        self.li_progress.set(0)
        self.li_progress.pack(fill="x", pady=15)

        self.li_log_box = ctk.CTkTextbox(inner, height=150, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.li_log_box.pack(fill="x")

        main_area = ctk.CTkFrame(self.tab_linkedin, fg_color=COLORS["bg_card"], corner_radius=15)
        main_area.pack(side="right", fill="both", expand=True)
        
        header = ctk.CTkFrame(main_area, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Hasil Scrape LinkedIn", font=("Segoe UI Semibold", 14)).pack(side="left")
        ctk.CTkButton(header, text="Export Excel/CSV", fg_color=COLORS["success"], width=130, command=self._export_li_data).pack(side="right", padx=5)

        tree_container = ctk.CTkFrame(main_area, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Dynamic Treeview setup handled by _update_li_table_columns later
        self.tree_li = ttk.Treeview(tree_container, show="headings", style="Custom.Treeview")
        self._update_li_table_columns(
            {"no": "No", "id": "User ID", "name": "Name", "headline": "Headline", "location": "Location", "url": "URL"},
            {"no": 40, "id": 100, "name": 150, "headline": 200, "location": 120, "url": 150}
        )

        ysb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_li.yview)
        xsb = ttk.Scrollbar(tree_container, orient="horizontal", command=self.tree_li.xview)
        self.tree_li.configure(yscroll=ysb.set, xscroll=xsb.set)
        
        self.tree_li.tag_configure("odd", background=COLORS["table_row_1"])
        self.tree_li.tag_configure("even", background=COLORS["table_row_2"])

        self.tree_li.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        xsb.grid(row=1, column=0, sticky="ew")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

    def _on_li_type_change(self, choice):
        if choice == "Staff Perusahaan":
            self.lbl_li_target.configure(text="🏢 Nama Perusahaan")
            self.entry_li_target.configure(placeholder_text="Contoh: tokopedia", state="normal")
            self.entry_li_keyword.configure(state="normal")
            self.entry_li_location.configure(state="normal")
            self.entry_li_limit.configure(state="normal")
            self.cb_li_extra.configure(state="normal")
        elif choice == "Cari User (by ID)":
            self.lbl_li_target.configure(text="👤 User IDs (Pisahkan dengan koma)")
            self.entry_li_target.configure(placeholder_text="Contoh: williamhgates, rbranson", state="normal")
            self.entry_li_keyword.configure(state="disabled")
            self.entry_li_location.configure(state="disabled")
            self.entry_li_limit.configure(state="disabled")
            self.cb_li_extra.configure(state="disabled")
        elif choice == "Komentar Posting (Post ID)":
            self.lbl_li_target.configure(text="📝 Post IDs (Pisahkan dengan koma)")
            self.entry_li_target.configure(placeholder_text="Contoh: 725242195, 725308", state="normal")
            self.entry_li_keyword.configure(state="disabled")
            self.entry_li_location.configure(state="disabled")
            self.entry_li_limit.configure(state="disabled")
            self.cb_li_extra.configure(state="disabled")
        elif choice == "Detail Perusahaan":
            self.lbl_li_target.configure(text="🏢 Nama Perusahaan (Pisahkan koma)")
            self.entry_li_target.configure(placeholder_text="Contoh: tokopedia, google", state="normal")
            self.entry_li_keyword.configure(state="disabled")
            self.entry_li_location.configure(state="disabled")
            self.entry_li_limit.configure(state="disabled")
            self.cb_li_extra.configure(state="disabled")
        elif choice == "Koneksi Saya":
            self.lbl_li_target.configure(text="🤝 Koneksi Saya (Kosongkan saja)")
            self.entry_li_target.configure(placeholder_text="Tidak butuh target", state="disabled")
            self.entry_li_keyword.configure(state="disabled")
            self.entry_li_location.configure(state="disabled")
            self.entry_li_limit.configure(state="normal")
            self.cb_li_extra.configure(state="normal")

    def _update_li_table_columns(self, headings, widths):
        self.tree_li["columns"] = list(headings.keys())
        for c in self.tree_li["columns"]:
            self.tree_li.heading(c, text="") # clear
        for c, h in headings.items():
            self.tree_li.heading(c, text=h)
            self.tree_li.column(c, width=widths.get(c, 100), stretch=False)

    def _li_log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.li_log_box.insert("end", f"[{timestamp}] {msg}\n")
        self.li_log_box.see("end")

    def _start_li_scraping(self):
        target = self.entry_li_target.get().strip()
        kw = self.entry_li_keyword.get().strip()
        loc = self.entry_li_location.get().strip()
        extra_data = self.var_li_extra.get()
        search_type = self.var_li_target_type.get()
        
        try: limit = int(self.entry_li_limit.get() or 20)
        except: limit = 20
        
        if not LinkedInAccount:
            messagebox.showerror("Error", "Modul StaffSpy tidak ditemukan atau gagal di-load. Pastikan semua instalasi dependency lengkap.")
            return

        if not target and search_type not in ["Koneksi Saya"]:
            messagebox.showwarning("Peringatan", "Masukkan target pencarian (Perusahaan/ID).")
            return
            
        self.btn_li_start.configure(state="disabled", text="Scraping...")
        self.btn_li_stop.configure(state="normal")
        self.li_progress.set(0)
        
        for item in self.tree_li.get_children():
            self.tree_li.delete(item)
        self.current_li_results = []
        self._li_stop_flag = False
        
        # update temporary display
        self._update_li_table_columns({"no": "No", "status": "Status"}, {"no": 40, "status": 200})
        self.tree_li.insert("", "end", values=("", "Loading data..."))
        
        def run_scraper():
            try:
                self.after(0, lambda: self._li_log("🚀 Memulai login / menyiapkan session LinkedIn..."))
                account = LinkedInAccount(session_file="li_session.pkl", log_level=1)
                
                df = None
                if search_type == "Staff Perusahaan":
                    self.after(0, lambda: self._li_log(f"🔎 Mencari {kw} di {target} ({loc})..."))
                    df = account.scrape_staff(company_name=target, search_term=kw, location=loc, extra_profile_data=extra_data, max_results=limit)
                elif search_type == "Cari User (by ID)":
                    user_ids = [x.strip() for x in target.split(',') if x.strip()]
                    self.after(0, lambda: self._li_log(f"🔎 Mencari {len(user_ids)} users..."))
                    df = account.scrape_users(user_ids=user_ids)
                elif search_type == "Komentar Posting (Post ID)":
                    post_ids = [x.strip() for x in target.split(',') if x.strip()]
                    self.after(0, lambda: self._li_log(f"🔎 Mengambil komentar dari {len(post_ids)} post..."))
                    df = account.scrape_comments(post_ids=post_ids)
                elif search_type == "Detail Perusahaan":
                    names = [x.strip() for x in target.split(',') if x.strip()]
                    self.after(0, lambda: self._li_log(f"🔎 Mengambil detail dari {len(names)} perusahaan..."))
                    df = account.scrape_companies(company_names=names)
                elif search_type == "Koneksi Saya":
                    self.after(0, lambda: self._li_log(f"🔎 Mengambil list koneksi Anda..."))
                    df = account.scrape_connections(max_results=limit, extra_profile_data=extra_data)

                if self._li_stop_flag:
                    self.after(0, lambda: self._li_log("🛑 Scraping dihentikan."))
                    return
                
                if df is not None and not df.empty:
                    self.after(0, lambda: self._li_log(f"✅ Ditemukan {len(df)} data."))
                    
                    df_cols = list(df.columns)
                    display_cols = {"no": "No"}
                    for c in df_cols:
                        display_cols[c] = c.replace("_", " ").title()
                    
                    widths_map = {"no": 40}
                    for c in df_cols:
                        if c in ["text", "bio", "experiences"]: widths_map[c] = 300
                        elif c in ["headline", "headquarters_address", "schools", "skills"]: widths_map[c] = 200
                        elif "url" in c or "link" in c or "name" in c or "email" in c: widths_map[c] = 160
                        else: widths_map[c] = 100
                        
                    def set_columns(cs, wds):
                        for item in self.tree_li.get_children(): self.tree_li.delete(item)
                        self._update_li_table_columns(cs, wds)
                    
                    self.after(0, lambda c=display_cols, w=widths_map: set_columns(c, w))
                    
                    for idx, row in df.iterrows():
                        r_data = row.to_dict()
                        self.current_li_results.append(r_data)
                        
                        r_data_all = [idx+1]
                        for c in df_cols:
                            val = r_data.get(c, "")
                            v_str = str(val).strip()
                            if v_str in ["nan", "None", "[]", "{}"]: 
                                v_str_neat = "-"
                            else:
                                v_str_neat = v_str.replace('\n', ' ').replace('\r', '')
                                if len(v_str_neat) > 100: 
                                    v_str_neat = v_str_neat[:97] + "..."
                            r_data_all.append(v_str_neat)
                        
                        tag = "even" if (idx+1) % 2 == 0 else "odd"
                        self.after(0, lambda vals=r_data_all, t=tag: self.tree_li.insert("", "end", values=vals, tags=(t,)))
                        progress = min((idx + 1) / len(df), 1.0)
                        self.after(0, lambda p=progress: self.li_progress.set(p))
                else:
                    self.after(0, lambda: (
                        [self.tree_li.delete(i) for i in self.tree_li.get_children()],
                        self._li_log("⚠️ Tidak ada data ditemukan.")
                    ))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda msg=err_msg: self._li_log(f"❌ Error: {msg}"))
            finally:
                self.after(0, self._on_li_done)

        self.li_thread = threading.Thread(target=run_scraper, daemon=True)
        self.li_thread.start()

    def _on_li_done(self):
        self.btn_li_start.configure(state="normal", text="Mulai Scrape LinkedIn 🚀")
        self.btn_li_stop.configure(state="disabled")
        self._li_log("✨ Scraping LinkedIn Selesai!")

    def _stop_li_scraping(self):
        self._li_log("🛑 Permintaan berhenti dikirim (menunggu loop selesai)...")
        self._li_stop_flag = True

    def _export_li_data(self):
        if not hasattr(self, 'current_li_results') or not self.current_li_results:
            messagebox.showwarning("Peringatan", "Tidak ada data untuk diexport.")
            return
        
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx"), ("CSV files", "*.csv")])
        if path:
            try:
                df = pd.DataFrame(self.current_li_results)
                if path.endswith(".xlsx"):
                    df.to_excel(path, index=False)
                else:
                    df.to_csv(path, index=False)
                messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal mengekspor data: {str(e)}")

    # ═══════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ═══════════════════════════════════════════════════════════════════════
    def _add_field(self, parent, label, placeholder):
        ctk.CTkLabel(parent, text=label, font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        entry = ctk.CTkEntry(parent, placeholder_text=placeholder, fg_color=COLORS["bg_input"], border_color=COLORS["border"], text_color=COLORS["text_primary"])
        entry.pack(fill="x", pady=(0, 10))
        return entry

    def _update_tree_columns(self, tree, headings, widths):
        tree["columns"] = list(headings.keys())
        for c in tree["columns"]:
            tree.heading(c, text="") # clear
        for c, h in headings.items():
            tree.heading(c, text=h)
            tree.column(c, width=widths.get(c, 100), anchor="center" if c in ["select", "no", "rating"] else "w")

    def _on_saved_filter_change(self, choice):
        if choice == "Google Maps":
            self._update_tree_columns(self.tree_saved, 
                {"select": "Pilih", "no": "No", "nama": "Nama Bisnis", "kategori": "Kategori", "alamat": "Alamat", "telepon": "Telepon", "email": "Email", "website": "Website", "rating": "⭐"},
                {"select": 40, "no": 30, "nama": 150, "kategori": 100, "alamat": 250, "telepon": 100, "email": 120, "website": 120, "rating": 40}
            )
        elif choice == "Social Media":
            self._update_tree_columns(self.tree_saved, 
                {"select": "Pilih", "no": "No", "platform": "Platform", "telepon": "Nomor HP", "keyword": "Keyword"},
                {"select": 40, "no": 30, "platform": 100, "telepon": 150, "keyword": 150}
            )
        else: # Social Email
            self._update_tree_columns(self.tree_saved, 
                {"select": "Pilih", "no": "No", "platform": "Platform", "email": "Email", "keyword": "Keyword"},
                {"select": 40, "no": 30, "platform": 100, "email": 250, "keyword": 150}
            )
        self._load_saved_data()

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
                    exists.email = r["Email"]
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
                        email=r["Email"],
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
        filter_choice = self.var_saved_filter.get()
        
        source_map = {
            "Google Maps": "google_maps",
            "Social Media": "social_media",
            "Social Email": "social_email"
        }
        target_source = source_map.get(filter_choice, "google_maps")
        
        try:
            leads = db.query(models.Lead).filter(models.Lead.source == target_source).order_by(models.Lead.id.desc()).all()
            for i, l in enumerate(leads):
                tag = "even" if i % 2 == 0 else "odd"
                if target_source == "google_maps":
                    vals = ("☐", i+1, l.name, l.category, l.address, l.phone, l.email or "", l.website, l.rating)
                elif target_source == "social_media":
                    vals = ("☐", i+1, l.platform, l.phone, l.keyword)
                else: # social_email
                    vals = ("☐", i+1, l.platform, l.email, l.keyword)
                    
                self.tree_saved.insert("", "end", iid=str(l.id), values=vals, tags=(tag,))
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
        filter_choice = self.var_saved_filter.get()
        source_map = {"Google Maps": "google_maps", "Social Media": "social_media", "Social Email": "social_email"}
        target_source = source_map.get(filter_choice, "google_maps")
        
        try:
            leads = db.query(models.Lead).filter(models.Lead.source == target_source).all()
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                w = csv.writer(f)
                if target_source == "google_maps":
                    w.writerow(["ID", "Nama", "Kategori", "Alamat", "Telepon", "Email", "Website", "Rating"])
                    for l in leads: w.writerow([l.id, l.name, l.category, l.address, l.phone, l.email, l.website, l.rating])
                elif target_source == "social_media":
                    w.writerow(["ID", "Platform", "Nomor HP", "Keyword"])
                    for l in leads: w.writerow([l.id, l.platform, l.phone, l.keyword])
                else:
                    w.writerow(["ID", "Platform", "Email", "Keyword"])
                    for l in leads: w.writerow([l.id, l.platform, l.email, l.keyword])
            messagebox.showinfo("Export Berhasil", f"Data diexport ke {path}")
        finally:
            db.close()
    def _export_saved_to_excel(self):
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel File", "*.xlsx")])
        if not path: return
        
        db = SessionLocal()
        filter_choice = self.var_saved_filter.get()
        source_map = {"Google Maps": "google_maps", "Social Media": "social_media", "Social Email": "social_email"}
        target_source = source_map.get(filter_choice, "google_maps")
        
        try:
            leads = db.query(models.Lead).filter(models.Lead.source == target_source).all()
            data = []
            for l in leads:
                if target_source == "google_maps":
                    data.append({"ID": l.id, "Nama": l.name, "Kategori": l.category, "Alamat": l.address, "Telepon": l.phone, "Email": l.email, "Website": l.website, "Rating": l.rating})
                elif target_source == "social_media":
                    data.append({"ID": l.id, "Platform": l.platform, "Nomor HP": l.phone, "Keyword": l.keyword})
                else:
                    data.append({"ID": l.id, "Platform": l.platform, "Email": l.email, "Keyword": l.keyword})
            
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
        selected_country = self.combo_country.get()
        # Ambil kode angka saja dari format "Negara (+XX)"
        import re
        match = re.search(r'\+(\d+)', selected_country)
        country_code = match.group(1) if match else "62"
        
        threading.Thread(
            target=self.bc_engine.run, 
            args=(self.broadcast_contacts, msg, d_min, d_max, b_every, b_dur, self.bc_image_path, self.entry_bc_duplicate.get().strip(), country_code), 
            daemon=True
        ).start()

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 6: SOCIAL MEDIA (FB & IG)
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_social_tab(self):
        sidebar = ctk.CTkScrollableFrame(self.tab_social, width=300, fg_color=COLORS["bg_card"], corner_radius=15, scrollbar_fg_color="transparent")
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(inner, text="PENGATURAN SOCIAL MEDIA", font=("Segoe UI Semibold", 14), text_color=COLORS["text_primary"]).pack(pady=(0,15))

        ctk.CTkLabel(inner, text="Platform", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.var_social_platform = tk.StringVar(value="Facebook")
        self.opt_social_platform = ctk.CTkOptionMenu(inner, variable=self.var_social_platform, values=["Facebook", "Instagram", "LinkedIn"])
        self.opt_social_platform.pack(fill="x", pady=(0, 15))

        self.entry_social_keyword = self._add_field(inner, "🔍 Keyword", "Contoh: jual gamis")
        
        ctk.CTkLabel(inner, text="Pilih Negara", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.combo_social_country = ctk.CTkComboBox(
            inner, 
            values=[f"{n} (+{c})" for n, c in COUNTRY_DATA], 
            fg_color=COLORS["bg_input"], 
            text_color=COLORS["text_primary"], 
            border_color=COLORS["border"]
        )
        self.combo_social_country.set("Indonesia (+62)")
        self.combo_social_country.pack(fill="x", pady=(0, 15))

        self.entry_social_limit = self._add_field(inner, "📊 Batas Halaman", "5")

        self.btn_social_start = ctk.CTkButton(inner, text="Mulai Scrape Social Media 🚀", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_social_scraping, height=45, font=("Segoe UI Bold", 13))
        self.btn_social_start.pack(fill="x", pady=(15, 5))

        self.btn_social_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_social_scraping)
        self.btn_social_stop.pack(fill="x", pady=5)

        self.btn_save_social_db = ctk.CTkButton(inner, text="Simpan ke Database", fg_color=COLORS["success"], state="disabled", command=self._save_social_to_db)
        self.btn_save_social_db.pack(fill="x", pady=5)

        self.social_progress = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["success"])
        self.social_progress.set(0)
        self.social_progress.pack(fill="x", pady=15)

        self.social_log_box = ctk.CTkTextbox(inner, height=150, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.social_log_box.pack(fill="x")

        main_area = ctk.CTkFrame(self.tab_social, fg_color=COLORS["bg_card"], corner_radius=15)
        main_area.pack(side="right", fill="both", expand=True)
        
        # Table Header
        header = ctk.CTkFrame(main_area, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Hasil Scrape Kontak Social Media", font=("Segoe UI Semibold", 14)).pack(side="left")
        ctk.CTkButton(header, text="Export CSV", fg_color=COLORS["success"], width=100, command=self._export_social_data).pack(side="right", padx=5)
        ctk.CTkButton(header, text="Export Excel", fg_color="#107c41", width=100, command=self._export_social_to_excel).pack(side="right", padx=5)

        # Treeview
        tree_container = ctk.CTkFrame(main_area, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("no", "platform", "phone", "keyword")
        self.tree_social = ttk.Treeview(tree_container, columns=cols, show="headings", style="Custom.Treeview")
        
        headings = {"no": "No", "platform": "Platform", "phone": "Nomor HP", "keyword": "Keyword"}
        widths = {"no": 40, "platform": 100, "phone": 150, "keyword": 150}

        for c, h in headings.items():
            self.tree_social.heading(c, text=h)
            self.tree_social.column(c, width=widths.get(c, 100))

        ysb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_social.yview)
        self.tree_social.configure(yscroll=ysb.set)
        
        self.tree_social.tag_configure("odd", background=COLORS["table_row_1"])
        self.tree_social.tag_configure("even", background=COLORS["table_row_2"])

        self.tree_social.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

    def _social_log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.social_log_box.insert("end", f"[{timestamp}] {msg}\n")
        self.social_log_box.see("end")

    def _start_social_scraping(self):
        platform = self.var_social_platform.get()
        kw = self.entry_social_keyword.get().strip()
        try: limit = int(self.entry_social_limit.get() or 5)
        except: limit = 5
        
        # Get country code
        selected_country = self.combo_social_country.get()
        match = re.search(r'\+(\d+)', selected_country)
        country_code = match.group(1) if match else "62"

        if not kw:
            messagebox.showwarning("Peringatan", "Masukkan keyword pencarian.")
            return

        self.btn_social_start.configure(state="disabled", text="Scraping...")
        self.btn_social_stop.configure(state="normal")
        self.social_progress.set(0)
        
        for item in self.tree_social.get_children():
            self.tree_social.delete(item)
        self.current_social_results = []
        
        self.social_engine_instance = SocialEngine(
            callback_log=lambda m: self.after(0, lambda: self._social_log(m)),
            callback_result=lambda r: self.after(0, lambda: self._on_social_result(r)),
            callback_progress=lambda c, t: self.after(0, lambda: self.social_progress.set(c/t)),
            callback_done=lambda: self.after(0, self._on_social_done)
        )
        
        def run_social():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.social_engine_instance.run(
                platform=platform,
                keyword=kw,
                country_code=country_code,
                limit_pages=limit,
                headless=False
            ))
            loop.close()

        threading.Thread(target=run_social, daemon=True).start()

    def _on_social_result(self, res):
        idx = len(self.current_social_results) + 1
        self.current_social_results.append(res)
        tag = "even" if idx % 2 == 0 else "odd"
        self.tree_social.insert("", "end", values=(
            idx,
            res.get("Platform", ""),
            res.get("Phone Number", ""),
            res.get("Keyword", "")
        ), tags=(tag,))

    def _on_social_done(self):
        self.btn_social_start.configure(state="normal", text="Mulai Scrape Social Media 🚀")
        self.btn_social_stop.configure(state="disabled")
        if self.current_social_results:
            self.btn_save_social_db.configure(state="normal")
        self._social_log("✅ Scraping Social Media Selesai!")
        messagebox.showinfo("Selesai", "Scraping Social Media telah selesai.")

    def _save_social_to_db(self):
        if not self.current_social_results: return
        
        session = SessionLocal()
        try:
            count = 0
            for res in self.current_social_results:
                # Check duplicate by phone and platform
                exists = session.query(models.Lead).filter(
                    models.Lead.phone == res.get("Phone Number"),
                    models.Lead.platform == res.get("Platform"),
                    models.Lead.source == "social_media"
                ).first()
                
                if not exists:
                    lead = models.Lead(
                        source="social_media",
                        platform=res.get("Platform"),
                        phone=res.get("Phone Number"),
                        keyword=res.get("Keyword")
                    )
                    session.add(lead)
                    count += 1
            session.commit()
            messagebox.showinfo("Sukses", f"Berhasil menyimpan {count} data baru ke database.")
            self.btn_save_social_db.configure(state="disabled")
        except Exception as e:
            session.rollback()
            messagebox.showerror("Error", f"Gagal menyimpan: {str(e)}")
        finally:
            session.close()

    def _stop_social_scraping(self):
        if self.social_engine_instance:
            self.social_engine_instance.shutdown = True
            self._social_log("🛑 Memberhentikan...")

    def _export_social_data(self):
        if not self.current_social_results:
            messagebox.showwarning("Peringatan", "Tidak ada data untuk diexport.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            pd.DataFrame(self.current_social_results).to_csv(path, index=False)
            messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {path}")

    def _export_social_to_excel(self):
        if not self.current_social_results:
            messagebox.showwarning("Peringatan", "Tidak ada data untuk diexport.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if path:
            try:
                pd.DataFrame(self.current_social_results).to_excel(path, index=False)
                messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan file Excel: {str(e)}")

    # ═══════════════════════════════════════════════════════════════════════
    #  TAB 7: SOCIAL EMAIL (FB, IG, LI)
    # ═══════════════════════════════════════════════════════════════════════
    def _setup_social_email_tab(self):
        sidebar = ctk.CTkScrollableFrame(self.tab_social_email, width=300, fg_color=COLORS["bg_card"], corner_radius=15, scrollbar_fg_color="transparent")
        sidebar.pack(side="left", fill="y", padx=(0, 10), pady=0)

        inner = ctk.CTkFrame(sidebar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=5, pady=5)

        ctk.CTkLabel(inner, text="PENGATURAN SOCIAL EMAIL", font=("Segoe UI Semibold", 14), text_color=COLORS["text_primary"]).pack(pady=(0,15))

        ctk.CTkLabel(inner, text="Platform", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.var_social_email_platform = tk.StringVar(value="Facebook")
        self.opt_social_email_platform = ctk.CTkOptionMenu(inner, variable=self.var_social_email_platform, values=["Facebook", "Instagram", "LinkedIn"])
        self.opt_social_email_platform.pack(fill="x", pady=(0, 15))

        self.entry_social_email_keyword = self._add_field(inner, "🔍 Keyword", "Contoh: owner cafe")
        
        ctk.CTkLabel(inner, text="Provider Email", font=("Segoe UI", 11), text_color=COLORS["text_secondary"]).pack(anchor="w")
        self.var_social_email_provider = tk.StringVar(value="Semua")
        self.opt_social_email_provider = ctk.CTkOptionMenu(inner, variable=self.var_social_email_provider, values=["Semua", "@gmail.com", "@yahoo.com", "@outlook.com", "@hotmail.com"])
        self.opt_social_email_provider.pack(fill="x", pady=(0, 15))

        self.entry_social_email_limit = self._add_field(inner, "📊 Batas Halaman", "5")

        self.btn_social_email_start = ctk.CTkButton(inner, text="Mulai Scrape Email Social 🚀", fg_color=COLORS["accent"], hover_color=COLORS["accent_hover"], command=self._start_social_email_scraping, height=45, font=("Segoe UI Bold", 13))
        self.btn_social_email_start.pack(fill="x", pady=(15, 5))

        self.btn_social_email_stop = ctk.CTkButton(inner, text="Stop", fg_color=COLORS["danger"], state="disabled", command=self._stop_social_email_scraping)
        self.btn_social_email_stop.pack(fill="x", pady=5)

        self.btn_save_social_email_db = ctk.CTkButton(inner, text="Simpan ke Database", fg_color=COLORS["success"], state="disabled", command=self._save_social_email_to_db)
        self.btn_save_social_email_db.pack(fill="x", pady=5)

        self.social_email_progress = ctk.CTkProgressBar(inner, fg_color=COLORS["bg_input"], progress_color=COLORS["success"])
        self.social_email_progress.set(0)
        self.social_email_progress.pack(fill="x", pady=15)

        self.social_email_log_box = ctk.CTkTextbox(inner, height=150, font=("Consolas", 10), fg_color=COLORS["bg_input"], text_color=COLORS["text_primary"])
        self.social_email_log_box.pack(fill="x")

        main_area = ctk.CTkFrame(self.tab_social_email, fg_color=COLORS["bg_card"], corner_radius=15)
        main_area.pack(side="right", fill="both", expand=True)
        
        header = ctk.CTkFrame(main_area, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(header, text="Hasil Scrape Email Social Media", font=("Segoe UI Semibold", 14)).pack(side="left")
        ctk.CTkButton(header, text="Export CSV", fg_color=COLORS["success"], width=100, command=self._export_social_email_data).pack(side="right", padx=5)
        ctk.CTkButton(header, text="Export Excel", fg_color="#107c41", width=100, command=self._export_social_email_to_excel).pack(side="right", padx=5)

        tree_container = ctk.CTkFrame(main_area, fg_color="transparent")
        tree_container.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        cols = ("no", "platform", "email", "keyword")
        self.tree_social_email = ttk.Treeview(tree_container, columns=cols, show="headings", style="Custom.Treeview")
        
        headings = {"no": "No", "platform": "Platform", "email": "Email", "keyword": "Keyword"}
        widths = {"no": 40, "platform": 100, "email": 250, "keyword": 150}

        for c, h in headings.items():
            self.tree_social_email.heading(c, text=h)
            self.tree_social_email.column(c, width=widths.get(c, 100))

        ysb = ttk.Scrollbar(tree_container, orient="vertical", command=self.tree_social_email.yview)
        self.tree_social_email.configure(yscroll=ysb.set)
        
        self.tree_social_email.tag_configure("odd", background=COLORS["table_row_1"])
        self.tree_social_email.tag_configure("even", background=COLORS["table_row_2"])

        self.tree_social_email.grid(row=0, column=0, sticky="nsew")
        ysb.grid(row=0, column=1, sticky="ns")
        tree_container.grid_rowconfigure(0, weight=1)
        tree_container.grid_columnconfigure(0, weight=1)

    def _social_email_log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.social_email_log_box.insert("end", f"[{timestamp}] {msg}\n")
        self.social_email_log_box.see("end")

    def _start_social_email_scraping(self):
        platform = self.var_social_email_platform.get()
        kw = self.entry_social_email_keyword.get().strip()
        provider = self.var_social_email_provider.get()
        try: limit = int(self.entry_social_email_limit.get() or 5)
        except: limit = 5
        
        if not kw:
            messagebox.showwarning("Peringatan", "Masukkan keyword pencarian.")
            return

        self.btn_social_email_start.configure(state="disabled", text="Scraping...")
        self.btn_social_email_stop.configure(state="normal")
        self.social_email_progress.set(0)
        
        for item in self.tree_social_email.get_children():
            self.tree_social_email.delete(item)
        self.current_social_email_results = []
        
        self.social_email_engine_instance = EmailSocialEngine(
            callback_log=lambda m: self.after(0, lambda: self._social_email_log(m)),
            callback_result=lambda r: self.after(0, lambda: self._on_social_email_result(r)),
            callback_progress=lambda c, t: self.after(0, lambda: self.social_email_progress.set(c/t)),
            callback_done=lambda: self.after(0, self._on_social_email_done)
        )
        
        def run_social_email():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.social_email_engine_instance.run(
                platform=platform,
                keyword=kw,
                email_provider=provider,
                limit_pages=limit,
                headless=False
            ))
            loop.close()

        threading.Thread(target=run_social_email, daemon=True).start()

    def _on_social_email_result(self, res):
        idx = len(self.current_social_email_results) + 1
        self.current_social_email_results.append(res)
        tag = "even" if idx % 2 == 0 else "odd"
        self.tree_social_email.insert("", "end", values=(
            idx,
            res.get("Platform", ""),
            res.get("Email", ""),
            res.get("Keyword", "")
        ), tags=(tag,))

    def _on_social_email_done(self):
        self.btn_social_email_start.configure(state="normal", text="Mulai Scrape Email Social 🚀")
        self.btn_social_email_stop.configure(state="disabled")
        if self.current_social_email_results:
            self.btn_save_social_email_db.configure(state="normal")
        self._social_email_log("✅ Scraping Email Social Media Selesai!")
        messagebox.showinfo("Selesai", "Scraping Email Social Media telah selesai.")

    def _save_social_email_to_db(self):
        if not self.current_social_email_results: return
        
        session = SessionLocal()
        try:
            count = 0
            for res in self.current_social_email_results:
                # Check duplicate by email and platform
                exists = session.query(models.Lead).filter(
                    models.Lead.email == res.get("Email"),
                    models.Lead.platform == res.get("Platform"),
                    models.Lead.source == "social_email"
                ).first()
                
                if not exists:
                    lead = models.Lead(
                        source="social_email",
                        platform=res.get("Platform"),
                        email=res.get("Email"),
                        keyword=res.get("Keyword")
                    )
                    session.add(lead)
                    count += 1
            session.commit()
            messagebox.showinfo("Sukses", f"Berhasil menyimpan {count} data baru ke database.")
            self.btn_save_social_email_db.configure(state="disabled")
        except Exception as e:
            session.rollback()
            messagebox.showerror("Error", f"Gagal menyimpan: {str(e)}")
        finally:
            session.close()

    def _stop_social_email_scraping(self):
        if self.social_email_engine_instance:
            self.social_email_engine_instance.shutdown = True
            self._social_email_log("🛑 Memberhentikan...")

    def _export_social_email_data(self):
        if not self.current_social_email_results:
            messagebox.showwarning("Peringatan", "Tidak ada data untuk diexport.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files", "*.csv")])
        if path:
            pd.DataFrame(self.current_social_email_results).to_csv(path, index=False)
            messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {path}")

    def _export_social_email_to_excel(self):
        if not self.current_social_email_results:
            messagebox.showwarning("Peringatan", "Tidak ada data untuk diexport.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")])
        if path:
            try:
                pd.DataFrame(self.current_social_email_results).to_excel(path, index=False)
                messagebox.showinfo("Sukses", f"Data berhasil disimpan ke {path}")
            except Exception as e:
                messagebox.showerror("Error", f"Gagal menyimpan file Excel: {str(e)}")


if __name__ == "__main__":
    # Penting untuk aplikasi Windows yang di-package dengan PyInstaller/EXE
    multiprocessing.freeze_support()
    
    # PERBAIKAN KRUCIAL: Jika dipanggil sebagai subprocess untuk install playwright, 
    # jalankan CLI playwright alih-alih membuka jendela GUI baru.
    # Ini mencegah "infinite loop" jendela saat pertama kali aplikasi dijalankan.
    if len(sys.argv) > 2 and sys.argv[1] == "-m" and sys.argv[2] == "playwright":
        try:
            from playwright.__main__ import main
            sys.exit(main())
        except Exception:
            sys.exit(1)
            
    # Show Login Window First
    login_app = LoginWindow()
    login_app.mainloop()
    
    # If login was successful, start the main application
    if hasattr(login_app, 'login_successful') and login_app.login_successful:
        app = ModernApp()
        app.mainloop()
    else:
        # User closed the window or login failed
        sys.exit(0)
