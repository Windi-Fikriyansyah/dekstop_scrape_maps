import asyncio
import re
import os
import pandas as pd
from playwright.async_api import async_playwright
import urllib.parse
import random
from datetime import datetime

class SocialEngine:
    def __init__(self, callback_log=None, callback_result=None, callback_progress=None, callback_done=None):
        self.callback_log = callback_log or (lambda msg: None)
        self.callback_result = callback_result or (lambda row: None)
        self.callback_progress = callback_progress or (lambda val, total: None)
        self.callback_done = callback_done or (lambda: None)
        self.is_running = False
        self.shutdown = False

    def _extract_numbers(self, text, country_code):
        found = []
        # Pattern to match numbers starting with +, or digits
        # This is a bit more flexible to handle different formats in snippets
        phone_pattern = r'(?:\+?[' + country_code + r'|0])[0-9\-\.\s]{8,15}'
        wa_pattern = r'wa\.me/([0-9]+)'
        
        matches = re.finditer(phone_pattern, text)
        for m in matches:
            raw = m.group(0).strip()
            clean = re.sub(r'\D', '', raw)
            
            # Normalize to international format
            if clean.startswith('0'):
                clean = country_code + clean[1:]
            elif not clean.startswith(country_code) and len(clean) >= 9:
                # If it doesn't start with country code, maybe it's missing it
                clean = country_code + clean
                
            if 10 <= len(clean) <= 15:
                found.append('+' + clean)
        
        wa_matches = re.findall(wa_pattern, text)
        for wa in wa_matches:
            if 10 <= len(wa) <= 15:
                found.append('+' + wa if not wa.startswith('+') else wa)
                
        return list(set(found))

    async def run(self, platform, keyword, country_code, limit_pages=5, headless=False):
        self.is_running = True
        self.shutdown = False
        contacts_count = 0
        seen_numbers = set()
        
        if platform.lower() == "facebook":
            platform_site = "facebook.com"
        elif platform.lower() == "instagram":
            platform_site = "instagram.com"
        else:
            platform_site = "linkedin.com"
            
        query = f"+{country_code} {keyword} site:{platform_site}/"
        
        self.callback_log(f"🚀 Memulai pencarian {platform} untuk: {keyword}")
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=headless, args=["--disable-blink-features=AutomationControlled"])
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                    viewport={'width': 1280, 'height': 800}
                )
                page = await context.new_page()

                search_query = urllib.parse.quote(query)
                url = f"https://www.google.com/search?q={search_query}"
                
                await page.goto(url, wait_until="domcontentloaded")

                # Handle cookie consent
                try:
                    consent_btn = page.locator('button:has-text("Accept all"), button:has-text("Setuju"), button:has-text("I agree"), button:has-text("Terima semua")')
                    if await consent_btn.is_visible(timeout=3000):
                        await consent_btn.click()
                except:
                    pass

                for i in range(limit_pages):
                    if self.shutdown: break
                    
                    self.callback_log(f"📄 Scraping Halaman {i+1}...")
                    await page.wait_for_timeout(random.randint(3000, 5000))
                    
                    # Check for CAPTCHA
                    if "captcha" in (await page.content()).lower() or "google.com/sorry" in page.url:
                        self.callback_log("⚠️ CAPTCHA terdeteksi! Silakan selesaikan di browser.")
                        try:
                            await page.wait_for_selector("div#search, .g", timeout=60000)
                        except:
                            self.callback_log("❌ Gagal melewati CAPTCHA. Melewati halaman.")
                            continue

                    # Strategy 1: Result Blocks
                    selectors = [".g", "div[data-hveid]", "div.tF2Cxc"]
                    results = []
                    for selector in selectors:
                        try:
                            found = await page.locator(selector).all()
                            if len(found) > 1:
                                results = found
                                break
                        except:
                            continue
                    
                    if results:
                        for res in results:
                            if self.shutdown: break
                            try:
                                text = await res.inner_text()
                                if not text: continue
                                
                                nums = self._extract_numbers(text, country_code)
                                for num in nums:
                                    if num not in seen_numbers:
                                        contacts_count += 1
                                        row = {
                                            "No": contacts_count,
                                            "Platform": platform.capitalize(),
                                            "Phone Number": num,
                                            "Keyword": keyword
                                        }
                                        seen_numbers.add(num)
                                        self.callback_result(row)
                            except:
                                continue
                    
                    # Strategy 2: Deep Scan
                    if not self.shutdown:
                        all_divs = await page.locator("div").all()
                        for div in all_divs[:200]: 
                            if self.shutdown: break
                            try:
                                d_text = await div.inner_text()
                                if 10 < len(d_text) < 500: 
                                    nums = self._extract_numbers(d_text, country_code)
                                    for num in nums:
                                        if num not in seen_numbers:
                                            contacts_count += 1
                                            row = {
                                                "No": contacts_count,
                                                "Platform": platform.capitalize(),
                                                "Phone Number": num,
                                                "Keyword": keyword
                                            }
                                            seen_numbers.add(num)
                                            self.callback_result(row)
                            except:
                                continue

                    self.callback_progress(i + 1, limit_pages)

                    # Next Page
                    next_button = page.locator('a#pnnext, a:has-text("Next"), a:has-text("Berikutnya")')
                    if await next_button.count() > 0 and await next_button.is_visible():
                        try:
                            await next_button.scroll_into_view_if_needed()
                            await next_button.click(timeout=5000)
                        except:
                            # Fallback click via JS if regular click fails
                            await page.evaluate('el => el.click()', await next_button.element_handle())
                    else:
                        self.callback_log("🏁 Tidak ada halaman lagi.")
                        break

                await browser.close()

        except Exception as e:
            self.callback_log(f"❌ Error: {str(e)}")
        finally:
            self.is_running = False
            self.callback_done()
