import asyncio
import os
import random
import time
from typing import Optional, Dict, List, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle
import logging
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phantom-controller")

class BrowserController:
    """
    Core engine for browser lifecycle management and page interaction.
    Supports stealth mode, multi-profile management, and human-like behavior.
    """
    
    def __init__(self, headless: bool = True, user_data_dir: Optional[str] = None):
        self.pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.headless = headless
        self.user_data_dir = user_data_dir or os.path.join(os.getcwd(), "data", "browser_profiles", "default")
        os.makedirs(os.path.dirname(self.user_data_dir), exist_ok=True)
        
        # Stealth settings
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]

    async def start(self):
        """Initialize Playwright and launch the browser."""
        if self.pw:
            return
            
        self.pw = await async_playwright().start()
        
        # Stealth mode: Launch with specific arguments
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--window-position=0,0",
            "--ignore-certificate-errors",
            "--ignore-certificate-errors-spki-list",
            "--disable-dev-shm-usage"
        ]
        
        # Use persistent context to support profiles/sessions
        self.context = await self.pw.chromium.launch_persistent_context(
            user_data_dir=self.user_data_dir,
            headless=self.headless,
            args=launch_args,
            user_agent=random.choice(self.user_agents),
            viewport={"width": 1280, "height": 720},
            ignore_https_errors=True
        )
        
        # Additional stealth: Remove navigator.webdriver
        await self.context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        self.page = await self.context.new_page() if not self.context.pages else self.context.pages[0]
        logger.info(f"Browser started (headless={self.headless}) with profile: {self.user_data_dir}")

    async def stop(self):
        """Gracefully shut down the browser."""
        if self.context:
            await self.context.close()
        if self.pw:
            await self.pw.stop()
        self.pw = None
        self.context = None
        self.page = None
        logger.info("Browser stopped")

    async def navigate(self, url: str, wait_until: str = "networkidle"):
        """Navigate to a URL with human-like timing."""
        if not self.page:
            await self.start()
            
        # Human-like delay before navigation
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        logger.info(f"Navigating to {url}...")
        await self.page.goto(url, wait_until=wait_until)
        
    async def click(self, selector: str):
        """Click an element with human-like interaction."""
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)
        
        # Move mouse to element first
        box = await self.page.locator(selector).bounding_box()
        if box:
            await self.page.mouse.move(
                box['x'] + box['width'] / 2 + random.uniform(-5, 5),
                box['y'] + box['height'] / 2 + random.uniform(-5, 5),
                steps=random.randint(5, 15)
            )
            
        await asyncio.sleep(random.uniform(0.1, 0.4))
        await self.page.click(selector)
        logger.info(f"Clicked {selector}")

    async def type(self, selector: str, text: str, delay: int = 100):
        """Type text into an element with a per-character delay."""
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)
        await self.page.focus(selector)
        
        # Human-like typing
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(delay/1000, (delay+50)/1000))
            
        logger.info(f"Typed into {selector}")

    async def select_option(self, selector: str, value: str):
        """Select an option from a dropdown."""
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)
        await self.page.select_option(selector, value)
        logger.info(f"Selected {value} in {selector}")

    async def scroll(self, direction: str = "down", amount: int = 500):
        """Scroll the page."""
        if direction == "down":
            await self.page.mouse.wheel(0, amount)
        elif direction == "up":
            await self.page.mouse.wheel(0, -amount)
        logger.info(f"Scrolled {direction} by {amount}")

    async def get_screenshot(self, name: Optional[str] = None) -> str:
        """Capture a screenshot and return the file path."""
        if not name:
            name = f"ss_{int(time.time())}.png"
            
        path = os.path.join(os.getcwd(), "data", "screenshots", name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        await self.page.screenshot(path=path)
        logger.info(f"Screenshot saved to {path}")
        return path

    async def get_page_content(self) -> str:
        """Get the full raw HTML content of the page."""
        return await self.page.content()

# Implementation for Stealth Mode and Human-like interaction included above.
