import asyncio
import csv
import json
import logging
import os
import random
import re
import signal
import sys
from datetime import datetime
from typing import TextIO, Set, List, Optional, Dict
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError, Page
from dotenv import load_dotenv
import urllib.parse
import unicodedata

load_dotenv()

# Set up logging
def setup_logging(log_level: str) -> logging.Logger:
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    file_handler = logging.FileHandler('instagram_scraper.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(console_formatter)
    logger = logging.getLogger(__name__)
    logger.setLevel(numeric_level)
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    return logger

# Load config.json
if os.path.exists('config.json'):
    try:
        with open('config.json', 'r', encoding='utf-8') as f:
            CONFIG = json.load(f)
    except Exception as e:
        print(f"Error loading config.json: {e}")
        CONFIG = {}
else:
    CONFIG = {}

logger = setup_logging(CONFIG.get('log_level', 'INFO'))

class InstagramScraper:
    def __init__(self, username=None, password=None, callback_log=None, callback_result=None, callback_progress=None, headless=None):
        self.config = CONFIG
        self.username = username or os.getenv('INSTAGRAM_USERNAME')
        self.password = password or os.getenv('INSTAGRAM_PASSWORD')
        self.callback_log = callback_log or (lambda msg: logger.info(msg))
        self.callback_result = callback_result or (lambda res: None)
        self.callback_progress = callback_progress or (lambda curr, total: None)
        # Ensure we have an absolute path for session data
        base_path = os.path.dirname(os.path.abspath(__file__))
        self.user_data_dir = os.path.join(base_path, self.config.get('user_data_dir', 'user_data'))
        os.makedirs(self.user_data_dir, exist_ok=True)
        self.proxy_server = os.getenv('PROXY_SERVER')
        
        # Priority: constructor arg > config file > .env
        if headless is not None:
            self.headless = headless
        elif 'headless' in self.config:
            self.headless = str(self.config['headless']).lower() == 'true'
        else:
            self.headless = os.getenv('HEADLESS', 'true').lower() == 'true'
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Safari/605.1.15",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
        ]
        self.progress_file = 'scraper_progress.json'
        self.load_progress()
        self.shutdown = False
        self.page = None

    async def setup_page_stealth(self, page: Page):
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            window.navigator.chrome = { runtime: {} };
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
        """)
        await page.context.grant_permissions(['geolocation'])
        await page.evaluate("""
            () => {
                navigator.geolocation.getCurrentPosition = function(success, error, options) {
                    if (typeof success === 'function') {
                        success({
                            coords: {
                                latitude: 48.8566,
                                longitude: 2.3522,
                                accuracy: 1000
                            },
                            timestamp: Date.now()
                        });
                    }
                    else if (typeof error === 'function') {
                        error(new Error('Geolocation success callback is not a function'));
                    }
                };
            }
        """)

    def load_progress(self) -> None:
        try:
            if os.path.exists(self.progress_file):
                with open(self.progress_file, 'r', encoding='utf-8') as f:
                    self.progress = json.load(f)
                    self.progress['processed_profiles'] = list(set(self.progress.get('processed_profiles', [])))  # Ensure uniqueness
            else:
                self.progress = {'processed_profiles': [], 'csv_file': None, 'last_processed': None}
        except Exception as e:
            logger.error(f"Error loading progress: {e}")
            self.progress = {'processed_profiles': [], 'csv_file': None, 'last_processed': None}

    def save_progress(self, last_processed: Optional[str] = None) -> None:
        try:
            self.progress['last_processed'] = last_processed or self.progress.get('last_processed')
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                json.dump(self.progress, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving progress: {e}")

    def load_existing_usernames(self, csv_filename: str) -> Set[str]:
        existing_usernames = set()
        if os.path.exists(csv_filename):
            try:
                with open(csv_filename, mode='r', encoding='utf-8') as file:
                    reader = csv.DictReader(file)
                    for row in reader:
                        if row.get('username'):
                            existing_usernames.add(row['username'])
            except Exception as e:
                logger.error(f"Error reading existing CSV {csv_filename}: {e}")
        return existing_usernames

    def load_profiles_from_csv(self, csv_filename: str = 'profiles.csv') -> List[str]:
        profiles = []
        try:
            with open(csv_filename, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    profile = row.get('profile', '').strip()
                    if profile:
                        profiles.append(profile)
            logger.info(f"Loaded {len(profiles)} profiles from {csv_filename}")
        except FileNotFoundError:
            logger.error(f"CSV file {csv_filename} not found. Please create it with a 'profile' column.")
        except Exception as e:
            logger.error(f"Error loading profiles from CSV: {e}")
        return profiles

    def setup_shutdown_handler(self, browser):
        async def close_browser():
            self.save_progress()
            try:
                await browser.close()
                logger.info("Browser closed successfully")
            except Exception as e:
                logger.error(f"Error closing browser: {e}")

        def signal_handler(sig, frame):
            logger.info("Shutdown signal received, saving progress...")
            self.shutdown = True
            asyncio.create_task(close_browser())
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
        except ValueError:
            # Signal only works in main thread
            pass

    async def random_delay(self, min_delay: float = 1, max_delay: float = 3) -> None:
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def is_logged_in(self, page: Page) -> bool:
        try:
            # Wait a bit to see if we are logged in or at login page
            try:
                # Wait for either home icon (logged in) or login username input (not logged in)
                await page.wait_for_selector('nav[role="navigation"], input[name="username"]', timeout=10000)
            except:
                pass
                
            logged_in_selectors = [
                'nav[role="navigation"]',
                'svg[aria-label="Home"]',
                'svg[aria-label="Explore"]',
                'a[href*="/direct/inbox/"]',
                'img[alt*="profile picture"]'
            ]
            for selector in logged_in_selectors:
                element = await page.query_selector(selector)
                if element and await element.is_visible():
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking login status: {e}")
            return False

    async def handle_login(self, page: Page) -> bool:
        try:
            if await self.is_logged_in(page):
                logger.info("Already logged in")
                return True
            self.callback_log("Attempting login...")
            for attempt in range(3):
                try:
                    await page.goto("https://www.instagram.com/accounts/login/", timeout=60000)
                    await page.wait_for_selector('input[name="username"]', timeout=30000)
                    break
                except Exception as e:
                    if attempt == 2:
                        logger.error(f"Failed to load login page after 3 attempts: {e}")
                        return False
                    await self.random_delay(5, 10)
            if not self.username or not self.password:
                logger.error("Instagram credentials not found in .env")
                return False
            await page.locator('input[name="username"]').fill(self.username)
            await self.random_delay(1, 2)
            await page.locator('input[name="password"]').fill(self.password)
            await self.random_delay(1, 2)
            await page.locator('button[type="submit"]').click()
            await self.random_delay(3, 5)
            try:
                await page.wait_for_selector('nav[role="navigation"], div[role="dialog"]', timeout=30000)
            except:
                if await page.query_selector('xpath=//*[contains(text(), "Suspicious Login Attempt")]'):
                    logger.error("Suspicious login attempt detected")
                    return False
                if await page.query_selector('xpath=//*[contains(text(), "Verify Your Account")]'):
                    logger.error("Account verification required")
                    return False
            dismiss_selectors = [
                'button:has-text("Not Now")',
                'button:has-text("Save Info")',
                'button:has-text("Later")'
            ]
            for selector in dismiss_selectors:
                try:
                    button = await page.wait_for_selector(selector, timeout=5000)
                    if button and await button.is_visible():
                        await button.click()
                        await self.random_delay(2, 4)
                except:
                    continue
            if await self.is_logged_in(page):
                self.callback_log("Login successful")
                return True
            self.callback_log("Login failed", "ERROR")
            return False
        except Exception as e:
            logger.error(f"Login failed: {e}")
            return False

    async def check_for_block(self, page: Page) -> bool:
        block_indicators = [
            'text="Log in to continue"',
            'text="Suspicious activity"',
            'text="Your account has been temporarily blocked"',
            'text="We detected unusual activity"',
            'iframe[src*="captcha"]',
            'text="Try Again Later"',
            'text="Please wait a few minutes"',
            'text="Something went wrong"',
            'text="Please wait a few minutes before you try again"',
            'text="Rate limit exceeded"',
            'text="Challenge required"'
        ]
        for selector in block_indicators:
            if await page.query_selector(selector):
                logger.error(f"Detected block: {selector}")
                await asyncio.sleep(random.uniform(60, 120))
                return True
        return False

    async def count_comments(self, page: Page) -> int:
        try:
            comment_selectors = [
                'ul._a9ym',
                'div._a9zo li',
                'div[class*="x1qjc9v5"] li[class*="x1y1aw1k"]',
                'div[class*="x9f619"] ul li'
            ]
            for selector in comment_selectors:
                for attempt in range(3):
                    try:
                        await page.wait_for_selector(selector, state='visible', timeout=10000)
                        comments = await page.query_selector_all(selector)
                        if comments:
                            count = len([c for c in comments if await c.is_visible()])
                            return count
                        await asyncio.sleep(2 ** attempt)
                    except Exception as e:
                        if attempt == 2:
                            comment_section = await page.query_selector('div._a9zo') or await page.query_selector('ul._a9ym')
                            if comment_section:
                                html = await comment_section.inner_html()
            comment_button = await page.query_selector('div[role="button"] svg[aria-label="Comment"]')
            if comment_button:
                parent = await page.query_selector('xpath=./ancestor::div[contains(@class, "x1i10hfl")]')
                if parent:
                    count_element = await parent.query_selector('span.x1lliihq')
                    if count_element:
                        count_text = await count_element.inner_text()
                        count = self.normalize_number(count_text)
                        return count
            return 0
        except Exception as e:
            logger.error(f"Error counting comments: {e}")
            return 0

    async def get_likes(self, page: Page) -> int:
        try:
            likes_selectors = [
                'span.x193iq5w:has-text("likes")',
                'span.x1vvkbs:has-text("likes")',
                'div[class*="x9f619"] span.x193iq5w:has-text("likes")',
                'div[class*="x9f619"] span.x1vvkbs:has-text("likes")',
            ]
            for selector in likes_selectors:
                for attempt in range(3):
                    try:
                        await page.wait_for_selector(selector, state='visible', timeout=10000)
                        elements = await page.query_selector_all(selector)
                        for element in elements:
                            if not await element.is_visible():
                                continue
                            likes_text = await element.inner_text()
                            if re.search(r'\d+', likes_text) and 'likes' in likes_text.lower():
                                likes = self.normalize_number(likes_text)
                                return likes
                        await asyncio.sleep(2 ** attempt)
                    except:
                        if attempt == 2:
                            engagement_section = await page.query_selector('section.x1qjc9v5') or \
                                            await page.query_selector('div[class*="x9f619"][class*="x78zum5"]')
                            if engagement_section:
                                html = await engagement_section.inner_html()
            return 0
        except Exception as e:
            logger.error(f"Error getting likes: {e}")
            return 0

    async def get_text(self, selector: str, context: Optional[Page] = None, default: str = 'N/A') -> str:
        context = context or self.page
        try:
            element = await context.query_selector(selector)
            if element and await element.is_visible():
                text = await element.inner_text()
                return text.strip() if text else default
        except Exception as e:
            pass
        return default

    async def get_attr(self, selector: str, attr: str, context: Optional[Page] = None, default: str = 'N/A') -> str:
        try:
            context = context or self.page
            element = await context.query_selector(selector)
            if element and await element.is_visible():
                value = await element.get_attribute(attr)
                return value if value else default
            return default
        except Exception as e:
            return default

    def extract_email(self, text: str) -> str:
        if not text or text == 'N/A':
            return 'N/A'
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:\.[a-zA-Z]{2,})?'
        matches = re.findall(email_pattern, text, re.IGNORECASE)
        return matches[0] if matches else 'N/A'

    def extract_whatsapp(self, text: str) -> dict:
        """Extract WhatsApp number and link from text (bio, links, etc)."""
        result = {'number': 'N/A', 'link': 'N/A'}
        if not text or text == 'N/A':
            return result
        
        # Pattern for wa.me links
        wa_link_match = re.search(r'(https?://)?wa\.me/(\+?\d[\d\s.-]+)', text, re.IGNORECASE)
        if wa_link_match:
            full_link = wa_link_match.group(0)
            if not full_link.startswith('http'):
                full_link = 'https://' + full_link
            number = re.sub(r'[^\d+]', '', wa_link_match.group(2))
            result['link'] = full_link
            result['number'] = number
            return result
        
        # Pattern for api.whatsapp.com links
        api_match = re.search(r'(https?://)?api\.whatsapp\.com/send\??[^\s]*phone=(\+?\d[\d\s.-]+)', text, re.IGNORECASE)
        if api_match:
            full_link = api_match.group(0)
            if not full_link.startswith('http'):
                full_link = 'https://' + full_link
            number = re.sub(r'[^\d+]', '', api_match.group(2))
            result['link'] = full_link
            result['number'] = number
            return result
        
        # Pattern for chat.whatsapp.com (group links - just capture link)
        chat_match = re.search(r'(https?://)?chat\.whatsapp\.com/[^\s]+', text, re.IGNORECASE)
        if chat_match:
            full_link = chat_match.group(0)
            if not full_link.startswith('http'):
                full_link = 'https://' + full_link
            result['link'] = full_link
            return result

        # Pattern for standalone phone numbers (Indonesian format)
        phone_match = re.search(r'(?:WA|WhatsApp|Whatsapp|wa)[:\s]*([+]?\d[\d\s.-]{8,})', text, re.IGNORECASE)
        if phone_match:
            number = re.sub(r'[^\d+]', '', phone_match.group(1))
            result['number'] = number
            result['link'] = f'https://wa.me/{number}'
            return result
        
        return result

    def normalize_unicode(self, text: str) -> str:
        """Clean string but preserve emojis and special characters."""
        if not text or text == 'N/A':
            return 'N/A'
        # Normalize but don't strip non-ascii
        text = unicodedata.normalize('NFC', text)
        # Remove only control characters
        text = "".join(ch for ch in text if unicodedata.category(ch)[0] != "C")
        return text.strip() or 'N/A'

    async def navigate_to_profile(self, page: Page, username: str) -> bool:
        logger.info(f"Navigating to profile: {username}")
        for attempt in range(3):
            try:
                profile_url = f"https://www.instagram.com/{username}/"
                await page.goto(profile_url, wait_until="domcontentloaded", timeout=60000)
                
                # Wait for the page body to have content
                await page.wait_for_timeout(3000)
                
                # Check if we landed on a valid page using simple checks
                body_text = await page.inner_text('body')
                if body_text and len(body_text) > 100:
                    # Check for error pages
                    if "Sorry, this page isn't available" in body_text or "Page Not Found" in body_text:
                        self.callback_log(f"   ⚠️ Profil @{username} tidak ditemukan.")
                        return False
                    await page.mouse.move(random.randint(100, 500), random.randint(100, 500))
                    return True
                
                raise Exception("Page body is empty or too short")
            except Exception as e:
                logger.warning(f"Navigation attempt {attempt + 1} failed: {str(e)}")
                if attempt < 2:
                    await self.random_delay(3, 5)
                    continue
                logger.error(f"Failed to navigate to profile: {username}")
                return False

    async def extract_profile_data_js(self, page: Page, username: str) -> Optional[dict]:
        """Extract all profile data using JavaScript for maximum reliability."""
        try:
            data = await page.evaluate("""
                () => {
                    const result = {
                        full_name: 'N/A',
                        posts: 0,
                        followers: 0,
                        following: 0,
                        bio: 'N/A',
                        is_private: false,
                        no_posts: false
                    };
                    
                    // Check private / no posts
                    const bodyText = document.body.innerText || '';
                    if (bodyText.includes('This account is private') || bodyText.includes('This Account is Private')) {
                        result.is_private = true;
                    }
                    if (bodyText.includes('No Posts Yet')) {
                        result.no_posts = true;
                    }
                    
                    // Stats from header ul li
                    const header = document.querySelector('header');
                    if (header) {
                        const headerSection = header.querySelector('section');
                        if (headerSection) {
                            const listItems = header.querySelectorAll('ul li');
                            if (listItems.length >= 3) {
                                const getText = (el) => {
                                    const span = el.querySelector('span span') || el.querySelector('span');
                                    if (span) {
                                        const title = span.getAttribute('title');
                                        if (title) return title;
                                        return span.innerText || '';
                                    }
                                    return el.innerText || '';
                                };
                                result.posts_text = getText(listItems[0]);
                                result.followers_text = getText(listItems[1]);
                                result.following_text = getText(listItems[2]);
                            }
                        }
                    }
                    
                    // === FULL NAME from og:title (most reliable) ===
                    // Format: "DisplayName (@username) ..."
                    const ogTitle = document.querySelector('meta[property="og:title"]');
                    if (ogTitle) {
                        const c = ogTitle.getAttribute('content') || '';
                        const m = c.match(/^(.+?)\\s*\\(@/);
                        if (m && m[1]) result.full_name = m[1].trim();
                    }
                    
                    // Fallback: meta description "... from DisplayName (@username)"
                    if (result.full_name === 'N/A') {
                        const md = document.querySelector('meta[name="description"]');
                        if (md) {
                            const c = md.getAttribute('content') || '';
                            const m = c.match(/from\\s+(.+?)\\s*\\(@/);
                            if (m && m[1]) result.full_name = m[1].trim();
                        }
                    }
                    
                    // Fallback: document title
                    if (result.full_name === 'N/A') {
                        const t = document.title || '';
                        const m = t.match(/^(.+?)\\s*\\(@/);
                        if (m && m[1]) result.full_name = m[1].trim();
                    }
                    
                    // Fallback: h1 or specialized spans in bio section
                    if (result.full_name === 'N/A') {
                        // Instagram often puts full name in a specific span inside the second div of section
                        const section = document.querySelector('header section');
                        if (section) {
                            const spans = section.querySelectorAll('div > span');
                            if (spans.length > 0) {
                                // The first or second span often contains the display name
                                for (let i = 0; i < Math.min(spans.length, 3); i++) {
                                    const t = spans[i].innerText.trim();
                                    if (t && t.length > 2 && !t.includes('@') && !['Follow', 'Following', 'Message'].includes(t)) {
                                        result.full_name = t;
                                        break;
                                    }
                                }
                            }
                        }
                    }
                    
                    // === BIO from meta description ===
                    // Format: "X Followers, X Following, X Posts - bio text. See Instagram..."
                    const md2 = document.querySelector('meta[name="description"]');
                    if (md2) {
                        const c = md2.getAttribute('content') || '';
                        const m = c.match(/[Pp]osts?\\s*[-\\u2013]\\s*(.*?)(?:\\s*See Instagram|$)/);
                        if (m && m[1]) {
                            let bio = m[1].replace(/See Instagram.*$/i, '').trim();
                            if (bio && bio.length > 2) result.bio = bio;
                        }
                    }
                    
                    // Fallback bio from DOM
                    if (result.bio === 'N/A') {
                        const bc = document.querySelector('header + div') || document.querySelector('header section');
                        if (bc) {
                            const spans = bc.querySelectorAll('span');
                            for (const span of spans) {
                                const text = span.innerText.trim();
                                if (text && text.length > 5 && text.length < 500) {
                                    if (!text.match(/^\\d/) && !['Follow', 'Following', 'Message'].includes(text)) {
                                        if (text.includes('@') || text.includes('.') || text.length > 20) {
                                            result.bio = text.replace(/\\n/g, ' | ');
                                            break;
                                        }
                                    }
                                }
                            }
                        }
                    }
                    
                    // === EXTERNAL LINKS + WHATSAPP from bio area ===
                    result.whatsapp_number = 'N/A';
                    result.external_link = 'N/A';
                    
                    const bioArea = document.querySelector('header') || document.querySelector('main');
                    if (bioArea) {
                        const bioLinks = bioArea.querySelectorAll('a[href]');
                        const externalLinks = [];
                        for (const link of bioLinks) {
                            const href = link.getAttribute('href') || '';
                            if (!href || href === '#') continue;
                            if (href.startsWith('/') || (href.includes('instagram.com') && !href.includes('l.instagram.com'))) continue;
                            if (href.startsWith('javascript:') || href.startsWith('mailto:')) continue;
                            
                            let cleanHref = href;
                            if (!cleanHref.startsWith('http')) cleanHref = 'https://' + cleanHref;
                            
                            if (cleanHref.includes('l.instagram.com/')) {
                                try {
                                    const urlObj = new URL(cleanHref);
                                    const actualUrl = urlObj.searchParams.get('u');
                                    if (actualUrl) cleanHref = decodeURIComponent(actualUrl);
                                } catch(e) {}
                            }
                            
                            externalLinks.push(cleanHref);
                            
                            if (result.whatsapp_number === 'N/A') {
                                const waM = cleanHref.match(/wa\\.me\\/(\\+?\\d[\\d\\s.-]+)/);
                                if (waM) result.whatsapp_number = waM[1].replace(/[^\\d+]/g, '');
                                const apiM = cleanHref.match(/api\\.whatsapp\\.com\\/send\\??.*phone=(\\+?\\d[\\d.-]+)/);
                                if (apiM) result.whatsapp_number = apiM[1].replace(/[^\\d+]/g, '');
                            }
                        }
                        if (externalLinks.length > 0) {
                            result.external_link = externalLinks.join(' | ');
                        }
                    }
                    
                    // Check bio text for WA numbers if not found in links
                    if (result.whatsapp_number === 'N/A' && result.bio !== 'N/A') {
                        const bt = result.bio;
                        const waM = bt.match(/wa\\.me\\/(\\+?\\d[\\d\\s.-]+)/i);
                        if (waM) {
                            result.whatsapp_number = waM[1].replace(/[^\\d+]/g, '');
                        } else {
                            const waL = bt.match(/(?:WA|WhatsApp|Whatsapp|wa)[:\\s]*(\\+?\\d[\\d\\s.-]{8,})/i);
                            if (waL) result.whatsapp_number = waL[1].replace(/[^\\d+]/g, '');
                        }
                    }
                    
                    return result;
                }
            """)
            return data
        except Exception as e:
            logger.error(f"Error extracting profile data via JS for {username}: {e}")
            return None

    async def search_profiles_by_keyword(self, keyword: str, limit: int = 50) -> List[str]:
        """Scrape profiles from a hashtag by navigating through posts."""
        tag = keyword.strip('#').replace(' ', '')
        logger.info(f"Scraping hashtag: #{tag}")
        usernames = set()
        
        excluded = ["explore", "reels", "direct", "accounts", "legal", "about", "tags", "emails", "privacy", "help"]
        
        try:
            self.callback_log(f"🏷️ Membuka hashtag: #{tag}...")
            await self.page.goto(f"https://www.instagram.com/explore/tags/{tag}/", wait_until="domcontentloaded")
            await self.random_delay(3, 5)
            
            # Click the first post to open the modal view (more reliable for username extraction)
            first_post = await self.page.query_selector('div._ac7w div._aabd')
            if first_post:
                self.callback_log("🖼️ Membuka postingan pertama...")
                await first_post.click()
                await self.random_delay(2, 3)
                
                # Navigate post-by-post
                for i in range(limit * 2): # Try twice the limit to find enough unique profiles
                    if len(usernames) >= limit or self.shutdown: break
                    
                    # Extract username from current post
                    user_el = await self.page.query_selector('header a[role="link"], header a.x1i10hfl')
                    if user_el:
                        user = await user_el.inner_text()
                        user = user.strip().lower()
                        if user and user not in excluded and user not in usernames:
                            usernames.add(user)
                            self.callback_log(f"✨ [{len(usernames)}/{limit}] Ditemukan: @{user}")
                    
                    # Click 'Next' button
                    next_button = await self.page.query_selector('svg[aria-label="Next"], svg[aria-label="Selanjutnya"]')
                    if next_button:
                        # The button is usually the parent or ancestor
                        parent_button = await self.page.evaluate_handle('el => el.closest("button") || el.parentElement', next_button)
                        if parent_button:
                            await parent_button.click()
                            await asyncio.sleep(random.uniform(1.5, 2.5))
                        else:
                            break
                    else:
                        break
            
            # Fallback to scrolling if modal view failed or wasn't enough
            if len(usernames) < limit and not self.shutdown:
                self.callback_log("📜 Men-scroll halaman hashtag untuk hasil tambahan...")
                for _ in range(5):
                    if len(usernames) >= limit or self.shutdown: break
                    await self.page.evaluate("window.scrollBy(0, 1000)")
                    await asyncio.sleep(2)
                    links = await self.page.evaluate("""
                        () => [...new Set([...document.querySelectorAll('a[href^="/"]')]
                            .map(a => a.getAttribute('href').split('/')[1])
                            .filter(u => u && u.length > 3 && !['reels', 'p', 'explore', 'tags'].includes(u)))]
                    """)
                    for user in links:
                        if user not in excluded and user not in usernames:
                            usernames.add(user.lower())
                            self.callback_log(f"✨ Ditemukan: @{user}")
                            if len(usernames) >= limit: break

        except Exception as e:
            logger.error(f"Error in hashtag scraping: {e}")
            self.callback_log(f"❌ Error hashtag Instagram: {str(e)}")
            
        return list(usernames)[:limit]

    async def scrape_profile(self, page: Page, profile: str, writer: csv.DictWriter, csv_file: TextIO,
                            existing_usernames: Set[str]) -> Optional[dict]:
        username = profile.strip('@').strip()
        if 'instagram.com/' in username:
            username = username.split('instagram.com/')[-1].split('/')[0].split('?')[0]
        
        if username in self.progress['processed_profiles']:
            logger.info(f"Skipping already processed profile: {username}")
            return None
        if username in existing_usernames:
            logger.info(f"Skipping duplicate username: {username}")
            return None

        logger.info(f"Scraping profile: {username}")
        self.callback_log(f"   📥 Membuka profil: @{username}")
        
        if not await self.navigate_to_profile(page, username):
            self.callback_log(f"   ❌ Gagal membuka profil: @{username}")
            self.progress['processed_profiles'].append(username)
            self.save_progress(username)
            return None

        try:
            # Wait for page to fully render
            await page.wait_for_timeout(3000)
            
            # Extract all data at once using JavaScript
            self.callback_log(f"   📊 Mengekstrak data profil...")
            js_data = await self.extract_profile_data_js(page, username)
            
            if not js_data:
                self.callback_log(f"   ⚠️ Tidak bisa membaca data profil @{username}")
                self.progress['processed_profiles'].append(username)
                self.save_progress(username)
                return None
            
            # Check private/no posts
            if js_data.get('is_private'):
                self.callback_log(f"   🔒 @{username} adalah akun privat. Melewati...")
                self.progress['processed_profiles'].append(username)
                self.save_progress(username)
                return None
            
            if js_data.get('no_posts'):
                self.callback_log(f"   📭 @{username} belum memiliki postingan. Melewati...")
                self.progress['processed_profiles'].append(username)
                self.save_progress(username)
                return None
            
            # Parse the stats
            full_name = self.normalize_unicode(js_data.get('full_name', 'N/A')) or 'N/A'
            posts = self.normalize_number(js_data.get('posts_text', '0'))
            followers = self.normalize_number(js_data.get('followers_text', '0'))
            following = self.normalize_number(js_data.get('following_text', '0'))
            bio = js_data.get('bio', 'N/A')
            email = self.extract_email(bio)
            
            # WhatsApp extraction (from JS data first, then Python fallback)
            wa_number = js_data.get('whatsapp_number', 'N/A')
            external_link = js_data.get('external_link', 'N/A')
            
            # Python fallback if JS didn't find WA number
            if wa_number == 'N/A' and bio != 'N/A':
                wa_data = self.extract_whatsapp(bio)
                wa_number = wa_data['number']
            
            self.callback_log(f"   👤 {full_name} | 👥 {followers} followers | 📧 {email} | 📱 WA: {wa_number}")

            profile_data = {
                'full_name': full_name,
                'username': username,
                'post_count': posts,
                'followers': followers,
                'following': following,
                'bio': bio,
                'email': email,
                'whatsapp_number': wa_number,
                'external_link': external_link,
                'instagram_link': f"https://www.instagram.com/{username}/"
            }

            writer.writerow(profile_data)
            csv_file.flush()
            existing_usernames.add(username)
            self.progress['processed_profiles'].append(username)
            self.save_progress(username)
            self.callback_log(f"   ✅ Data @{username} berhasil disimpan.")
            self.callback_result(profile_data)
            return profile_data

        except Exception as e:
            self.callback_log(f"   ⚠️ Error pada @{username}: {str(e)[:80]}")
            logger.error(f"Error scraping profile {username}: {e}")
            self.progress['processed_profiles'].append(username)
            self.save_progress(username)
            return None

    async def run(self, profiles: Optional[List[str]] = None, keyword: Optional[str] = None, limit: int = 100) -> None:
        if keyword:
            self.callback_log(f"Searching for profiles using keyword: {keyword}...")
            # We will search after login
        elif not profiles:
            profiles = self.load_profiles_from_csv()
        
        if not profiles and not keyword:
            self.callback_log("No profiles or keyword to process", "ERROR")
            return

        # total_profiles = len(profiles) # Removed here as it depends on search
        # self.callback_log(f"Starting scrape for {total_profiles} profiles...") # Moved inside login context

        async with async_playwright() as p:
            browser_args = [
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]
            if self.proxy_server:
                browser_args.append(f'--proxy-server={self.proxy_server}')
            browser = await p.chromium.launch_persistent_context(
                self.user_data_dir,
                headless=self.headless,
                viewport=self.config['viewport'],
                locale=self.config.get('locale', 'en-US'),
                timezone_id=self.config['timezone_id'],
                user_agent=random.choice(self.user_agents),
                args=browser_args,
                ignore_https_errors=True
            )
            try:
                self.setup_shutdown_handler(browser)
                self.page = await browser.new_page()
                await self.setup_page_stealth(self.page)
                
                logger.info("Navigating to Instagram...")
                await self.page.goto("https://www.instagram.com/", wait_until="domcontentloaded", timeout=60000)
                await self.page.wait_for_timeout(5000) 
                
                # Check login status
                is_logged = await self.is_logged_in(self.page)
                if is_logged:
                    self.callback_log("✅ Sesi aktif ditemukan, sudah login.")
                else:
                    self.callback_log("⚠️ Sesi tidak ditemukan. Memulai proses login manual...")
                    
                    # Jika saat ini headless=True, kita harus tutup dan buka lagi sebagai headful agar user bisa login
                    if self.headless:
                        await browser.close()
                        self.callback_log("🔄 Membuka jendela browser (Headful) agar Anda bisa login...")
                        browser = await p.chromium.launch_persistent_context(
                            self.user_data_dir,
                            headless=False, # Paksa browser tampil
                            viewport=self.config['viewport'],
                            locale=self.config.get('locale', 'en-US'),
                            timezone_id=self.config['timezone_id'],
                            user_agent=random.choice(self.user_agents),
                            args=browser_args,
                            ignore_https_errors=True
                        )
                        self.setup_shutdown_handler(browser)
                        self.page = await browser.new_page()
                        await self.setup_page_stealth(self.page)
                    
                    # Arahkan ke halaman login
                    await self.page.goto("https://www.instagram.com/accounts/login/")
                    self.callback_log("⏳ Silakan masukkan Username & Password Anda di jendela browser.")
                    self.callback_log("Menunggu hingga Anda berhasil masuk ke Dashboard Instagram...")
                    
                    # Tunggu manual login (cek status setiap 2 detik)
                    logged_in = False
                    for i in range(300): # 10 Menit timeout
                        if await self.is_logged_in(self.page):
                            logged_in = True
                            break
                        if self.shutdown: break
                        await asyncio.sleep(2)
                        
                        if i % 15 == 0: # Ingatkan user setiap 30 detik
                            self._log_status_wait = getattr(self, '_log_status_wait', 0) + 1
                            if self._log_status_wait % 2 == 0:
                                self.callback_log("⏳ Masih menunggu login manual...")
                    
                    if not logged_in:
                        self.callback_log("❌ Login gagal atau waktu habis. Pastikan Anda sudah masuk ke dashboard.", "ERROR")
                        await browser.close()
                        return
                    
                    self.callback_log("✅ Login Berhasil! Sesi telah disimpan.")
                    self.callback_log("Melanjutkan pencarian profil...")

                if keyword:
                    # Reset progress for keyword searches - start fresh
                    self.progress = {'processed_profiles': [], 'csv_file': None, 'last_processed': None}
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    csv_filename = f'instagram_profiles_{timestamp}.csv'
                    self.progress['csv_file'] = csv_filename
                    self.save_progress()
                    existing_usernames = set()
                else:
                    csv_filename = self.progress.get('csv_file')
                    if not csv_filename or not os.path.exists(csv_filename):
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        csv_filename = f'instagram_profiles_{timestamp}.csv'
                        self.progress['csv_file'] = csv_filename
                        self.save_progress()
                    existing_usernames = self.load_existing_usernames(csv_filename)

                with open(csv_filename, mode='a', newline='', encoding='utf-8') as csv_file:
                    fieldnames = [
                        'full_name', 'username', 'post_count', 'followers', 'following', 'bio', 'email',
                        'whatsapp_number', 'external_link', 'instagram_link'
                    ]
                    writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
                    if csv_file.tell() == 0:
                        writer.writeheader()

                    if keyword:
                        profiles = await self.search_profiles_by_keyword(keyword, limit=limit)
                        if not profiles:
                            self.callback_log(f"No profiles found for keyword: {keyword}", "ERROR")
                            return
                        self.callback_log(f"Found {len(profiles)} profiles for keyword: {keyword}")

                    total_profiles = len(profiles)
                    self.callback_log(f"Starting scrape for {total_profiles} profiles...")

                    # Reset resume logic for keyword searches to avoid skipping all results
                    last_processed = self.progress.get('last_processed') if not keyword else None
                    start_processing = False if last_processed else True
                    profile_count = 0
                    skip_count = 0
                    
                    self.callback_log(f"🚀 Memulai scraping {total_profiles} profil...")
                    
                    for profile in profiles:
                        if self.shutdown:
                            logger.info("Shutdown detected, stopping...")
                            break
                        
                        # Extract username from URL or handle @username
                        username = profile.strip('@').strip()
                        if 'instagram.com/' in username:
                            username = username.split('instagram.com/')[-1].split('/')[0].split('?')[0]
                        
                        if not start_processing:
                            if username == last_processed:
                                start_processing = True
                                self.callback_log(f"✅ Melanjutkan dari profil terakhir: @{username}")
                                continue
                            skip_count += 1
                            continue

                        if username in self.progress['processed_profiles']:
                            self.callback_log(f"⏭️ @{username} sudah pernah diproses. Melewati...")
                            continue
                        
                        if username in existing_usernames:
                            self.callback_log(f"⏭️ @{username} sudah ada di CSV. Melewati...")
                            continue

                        # Progress update
                        current_idx = profile_count + 1
                        self.callback_log(f"🔍 [{current_idx}/{total_profiles}] Mengambil data: @{username}")
                        
                        res = await self.scrape_profile(self.page, profile, writer, csv_file, existing_usernames)
                        if res:
                            profile_count += 1
                            self.callback_progress(profile_count, total_profiles)
                            
                        # Save progress every 5 profiles
                        if profile_count > 0 and profile_count % 5 == 0:
                            self.save_progress(username)
                        
                        # Random delay to avoid detection
                        await self.random_delay(5, 10)

                    if skip_count > 0 and not start_processing:  # Handle case where last_processed is last profile
                        logger.info(f"Skipped {skip_count} profiles until last processed: {last_processed}")
                    self.save_progress(username)  # Final save
                logger.info(f"Scraping complete. Total profiles processed: {len(self.progress['processed_profiles'])}")
            except Exception as e:
                logger.error(f"Error during scraping: {e}")
            finally:
                await browser.close()
                logger.info("Browser closed successfully")

    def normalize_number(self, text: str) -> int:
        if not text or text == 'N/A':
            return 0
        text = re.sub(r'\s*likes\s*', '', text, flags=re.IGNORECASE).strip()
        text = re.sub(r'[^\d.km]', '', text.lower(), flags=re.IGNORECASE).strip()
        if not text:
            return 0
        try:
            if text.endswith('k'):
                return int(float(text[:-1]) * 1000)
            elif text.endswith('m'):
                return int(float(text[:-1]) * 1000000)
            else:
                return int(float(text))
        except (ValueError, TypeError) as e:
            logger.warning(f"Failed to normalize number: {text}, error: {str(e)}")
            return 0

if __name__ == "__main__":
    logger.info("Starting Instagram scraper")
    scraper = InstagramScraper()
    asyncio.run(scraper.run())