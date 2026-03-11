import asyncio
import os
import random
import time
from typing import Optional, Dict, List, Any, Callable
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("phantom-controller")

class BrowserController:
    """
    Core engine for browser lifecycle management and page interaction.
    Supports stealth mode, multi-profile management, and human-like behavior.
    
    Integrates with:
    - P05 Chronicle: Event emission for action trace logging
    - P08 Legion: Cost tracking for tool invocation
    - P12 Aegis: URL validation and content sanitization
    """
    
    def __init__(self, headless: bool = True, user_data_dir: Optional[str] = None, task_id: Optional[str] = None):
        self.pw = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cdp_session = None
        self.headless = headless
        self.task_id = task_id or "default"
        
        # Profile isolation: each task gets its own directory
        base_dir = user_data_dir or os.path.join(os.getcwd(), "data", "browser_profiles")
        self.user_data_dir = os.path.join(base_dir, self.task_id)
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        # P05 Chronicle: Event emission
        self.event_listeners: List[Callable] = []
        self.step_counter = 0
        self.session_start_time = datetime.utcnow().isoformat()
        
        # P08 Legion: Cost tracking
        self.cost_tracker = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost_usd": 0.0,
        }
        
        # P12 Aegis: Safety validation
        self.safety_enabled = True
        self.safety_errors: List[str] = []
        
        # Stealth settings
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
        ]

    # ===== P05 Chronicle: Event Emission =====
    
    def register_event_listener(self, listener: Callable[[Dict[str, Any]], None]) -> None:
        """
        Register a listener for browser events (P05 Chronicle integration).
        
        Listener signature: async def listener(event: Dict[str, Any]) -> None
        """
        self.event_listeners.append(listener)
    
    async def emit_event(self, event_type: str, **kwargs) -> None:
        """
        Emit an event to all registered listeners (for action trace logging).
        
        Args:
            event_type: Type of event (navigate, click, type, etc.)
            **kwargs: Event-specific data
        """
        self.step_counter += 1
        
        event = {
            "step": self.step_counter,
            "type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": self.task_id,
            **kwargs
        }
        
        for listener in self.event_listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                logger.warning(f"Event listener error: {e}")
    
    def get_step_counter(self) -> int:
        """Get current step counter (for P05 Chronicle)."""
        return self.step_counter
    
    def reset_step_counter(self) -> None:
        """Reset step counter for new action sequence."""
        self.step_counter = 0
    
    # ===== P08 Legion: Cost Tracking =====
    
    def set_cost(self, input_tokens: int = 0, output_tokens: int = 0, total_cost_usd: float = 0.0) -> None:
        """
        Set cost metrics for Legion tool invocation.
        
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            total_cost_usd: Total cost in USD
        """
        self.cost_tracker["input_tokens"] = input_tokens
        self.cost_tracker["output_tokens"] = output_tokens
        self.cost_tracker["total_cost_usd"] = total_cost_usd
    
    def get_cost(self) -> Dict[str, float]:
        """Get cost metrics (for P08 Legion)."""
        return self.cost_tracker.copy()
    
    def add_cost(self, input_tokens: int = 0, output_tokens: int = 0, usd: float = 0.0) -> None:
        """Accumulate cost metrics."""
        self.cost_tracker["input_tokens"] += input_tokens
        self.cost_tracker["output_tokens"] += output_tokens
        self.cost_tracker["total_cost_usd"] += usd
    
    # ===== P12 Aegis: Safety Control =====
    
    def set_safety_enabled(self, enabled: bool) -> None:
        """Enable/disable safety validation."""
        self.safety_enabled = enabled
    
    def get_safety_errors(self) -> List[str]:
        """Get list of safety errors."""
        return self.safety_errors.copy()
    
    def clear_safety_errors(self) -> None:
        """Clear safety error log."""
        self.safety_errors.clear()

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
        
        from playwright_stealth import Stealth
        
        self.page = await self.context.new_page() if not self.context.pages else self.context.pages[0]
        
        # Apply stealth to the page
        stealth = Stealth()
        await stealth.apply_stealth_async(self.page)
        
        # Initialize CDP Session for low-level control
        self.cdp_session = await self.context.new_cdp_session(self.page)
        
        logger.info(f"Browser started (headless={self.headless}) with profile: {self.user_data_dir}")

    async def get_cdp_session(self):
        """Get the active CDP session, initializing if necessary."""
        if not self.cdp_session and self.page:
            self.cdp_session = await self.context.new_cdp_session(self.page)
        return self.cdp_session

    async def stop(self):
        """Gracefully shut down the browser."""
        if self.cdp_session:
            # CDP session doesn't have a close(), it's tied to the page/context
            self.cdp_session = None
        if self.context:
            await self.context.close()
        if self.pw:
            await self.pw.stop()
        self.pw = None
        self.context = None
        self.page = None
        logger.info("Browser stopped")

    async def navigate(self, url: str, wait_until: str = "networkidle"):
        """Navigate to a URL with human-like timing.
        
        Emits events for P05 Chronicle and validates with P12 Aegis.
        """
        if not self.page:
            await self.start()
        
        # P12 Aegis: Validate URL if safety enabled
        if self.safety_enabled:
            from browser.safety import URLValidator
            is_valid, error = URLValidator.validate(url)
            if not is_valid:
                self.safety_errors.append(f"URL validation failed: {error}")
                logger.error(f"Navigation blocked: {error}")
                return
        
        # Human-like delay before navigation
        await asyncio.sleep(random.uniform(0.5, 1.5))
        
        logger.info(f"Navigating to {url}...")
        nav_start = datetime.utcnow()
        await self.page.goto(url, wait_until=wait_until)
        nav_duration = (datetime.utcnow() - nav_start).total_seconds() * 1000
        
        # P05 Chronicle: Emit navigation event
        await self.emit_event(
            "navigate",
            url=url,
            duration_ms=nav_duration,
            wait_until=wait_until
        )
        
    async def click(self, selector: str):
        """Click an element with human-like interaction.
        
        Emits events for P05 Chronicle.
        """
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
        click_start = datetime.utcnow()
        await self.page.click(selector)
        click_duration = (datetime.utcnow() - click_start).total_seconds() * 1000
        
        logger.info(f"Clicked {selector}")
        
        # P05 Chronicle: Emit click event
        await self.emit_event(
            "click",
            selector=selector,
            duration_ms=click_duration
        )

    async def type(self, selector: str, text: str, delay: int = 100):
        """Type text into an element with a per-character delay.
        
        Emits events for P05 Chronicle.
        """
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)
        await self.page.focus(selector)
        
        type_start = datetime.utcnow()
        
        # Human-like typing
        for char in text:
            await self.page.keyboard.type(char)
            await asyncio.sleep(random.uniform(delay/1000, (delay+50)/1000))
        
        type_duration = (datetime.utcnow() - type_start).total_seconds() * 1000
        logger.info(f"Typed into {selector}")
        
        # P05 Chronicle: Emit type event
        await self.emit_event(
            "type",
            selector=selector,
            text_length=len(text),
            duration_ms=type_duration
        )

    async def select_option(self, selector: str, value: str):
        """Select an option from a dropdown."""
        await self.page.wait_for_selector(selector, state="visible", timeout=10000)
        await self.page.select_option(selector, value)
        logger.info(f"Selected {value} in {selector}")

    async def scroll(self, direction: str = "down", amount: int = 500):
        """Scroll the page.
        
        Emits events for P05 Chronicle.
        """
        scroll_start = datetime.utcnow()
        
        if direction == "down":
            await self.page.mouse.wheel(0, amount)
        elif direction == "up":
            await self.page.mouse.wheel(0, -amount)
        
        scroll_duration = (datetime.utcnow() - scroll_start).total_seconds() * 1000
        logger.info(f"Scrolled {direction} by {amount}")
        
        # P05 Chronicle: Emit scroll event
        await self.emit_event(
            "scroll",
            direction=direction,
            amount=amount,
            duration_ms=scroll_duration
        )

    async def setup_download_listener(self, download_dir: Optional[str] = None):
        """Set up a listener to automatically capture and save downloads."""
        if not self.page:
            await self.start()
            
        final_dir = download_dir or os.path.join(os.getcwd(), "data", "downloads", self.task_id)
        os.makedirs(final_dir, exist_ok=True)
        
        async def handle_download(download):
            path = os.path.join(final_dir, download.suggested_filename)
            await download.save_as(path)
            logger.info(f"File downloaded and saved to: {path}")
            
        self.page.on("download", handle_download)
        logger.info(f"Download listener active for directory: {final_dir}")

    async def monitor_selector(self, selector: str, timeout: int = 30000, check_interval: float = 1.0):
        """
        Watch a specific selector for content changes.
        Returns the new content when it changes.
        """
        if not self.page:
            return None
            
        logger.info(f"Monitoring selector: {selector}")
        initial_content = await self.page.inner_text(selector) if await self.page.query_selector(selector) else ""
        
        start_time = time.time()
        while time.time() - start_time < timeout / 1000:
            await asyncio.sleep(check_interval)
            current_content = await self.page.inner_text(selector) if await self.page.query_selector(selector) else ""
            if current_content != initial_content:
                logger.info(f"Change detected in {selector}")
                return current_content
                
        logger.warning(f"Monitoring timeout for {selector}")
        return None

    async def switch_tab(self, index: int):
        """Switch to a different tab/page by index."""
        pages = self.context.pages
        if 0 <= index < len(pages):
            self.page = pages[index]
            await self.page.bring_to_front()
            logger.info(f"Switched to tab {index}: {self.page.url}")
        else:
            logger.error(f"Invalid tab index: {index}")

    async def close_tab(self, index: int):
        """Close a specific tab."""
        pages = self.context.pages
        if 0 <= index < len(pages):
            await pages[index].close()
            logger.info(f"Closed tab {index}")
            # Reset active page if the current one was closed
            if len(self.context.pages) > 0:
                self.page = self.context.pages[-1]
        else:
            logger.error(f"Invalid tab index: {index}")

    async def drag_and_drop(self, source_selector: str, target_selector: str):
        """Perform a drag-and-drop operation from source to target."""
        if not self.page:
            return
        await self.page.drag_and_drop(source_selector, target_selector)
        logger.info(f"Dragged {source_selector} to {target_selector}")

    async def upload_file(self, selector: str, file_paths: List[str]):
        """Upload one or more files to an input element."""
        if not self.page:
            return
        await self.page.set_input_files(selector, file_paths)
        logger.info(f"Uploaded {len(file_paths)} files to {selector}")

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
