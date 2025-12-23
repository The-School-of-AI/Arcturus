import random
import asyncio
import httpx
from typing import List
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse
from playwright.async_api import async_playwright
import sys

# MCP Protocol Safety: Redirect print to stderr
def print(*args, **kwargs):
    sys.stderr.write(" ".join(map(str, args)) + "\n")
    sys.stderr.flush()

SEARCH_ENGINES = [
    "duck_http",
    "duck_playwright",
    "bing_playwright",
    "yahoo_playwright",
    "ecosia_playwright",
    "mojeek_playwright"
]

class RateLimiter:
    def __init__(self, cooldown_seconds=2):
        self.cooldown = timedelta(seconds=cooldown_seconds)
        self.last_called = {}

    async def acquire(self, key: str):
        now = datetime.now()
        last = self.last_called.get(key)
        if last and (now - last) < self.cooldown:
            wait = (self.cooldown - (now - last)).total_seconds()
            print(f"Rate limiting {key}, sleeping for {wait:.1f}s")
            await asyncio.sleep(wait)
        self.last_called[key] = now

rate_limiter = RateLimiter(cooldown_seconds=2)

def get_random_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/122.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 Chrome/113.0.5672.92 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_2) AppleWebKit/605.1.15 Version/16.3 Safari/605.1.15",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
        "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
        "Mozilla/5.0 (Linux; Android 13; Pixel 6) AppleWebKit/537.36 Chrome/117.0.5938.132 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; SAMSUNG SM-G998B) AppleWebKit/537.36 Chrome/92.0.4515.159 Mobile Safari/537.36 SamsungBrowser/15.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1",
        "Mozilla/5.0 (iPad; CPU OS 16_6 like Mac OS X) AppleWebKit/605.1.15 Version/16.6 Mobile Safari/604.1"
    ]
    return {"User-Agent": random.choice(user_agents)}

async def use_duckduckgo_http(query: str) -> List[str]:
    await rate_limiter.acquire("duck_http")
    url = "https://html.duckduckgo.com/html"
    headers = get_random_headers()
    data = {"q": query}

    async with httpx.AsyncClient() as client:
        r = await client.post(url, data=data, headers=headers, timeout=30.0)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        links = []

        for a in soup.select("a.result__a"):
            href = a.get("href", "")
            if not href:
                continue
            if "uddg=" in href:
                parts = href.split("uddg=")
                if len(parts) > 1:
                    href = urllib.parse.unquote(parts[1].split("&")[0])
            if href.startswith("http") and href not in links:
                links.append(href)

        if not links:
            print("[duck_http] No links found in results")

        return links

async def use_playwright_search(query: str, engine: str) -> List[str]:
    await rate_limiter.acquire(engine)
    urls = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True) # changed to headless=True for stability
        page = await browser.new_page()

        try:
            engine_url_map = {
                "duck_playwright": "https://html.duckduckgo.com/html",
                "bing_playwright": "https://www.bing.com/search",
                "yahoo_playwright": "https://search.yahoo.com/search",
                "ecosia_playwright": "https://www.ecosia.org/search",
                "mojeek_playwright": "https://www.mojeek.com/search"
            }

            search_url = f"{engine_url_map[engine]}?q={query.replace(' ', '+')}"
            print(f"🔗 Navigating to {search_url}")
            await page.goto(search_url)
            await asyncio.sleep(3)

            if engine == "duck_playwright":
                await page.wait_for_selector("a.result__a", timeout=10000)
                results = await page.query_selector_all("a.result__a")

            elif engine == "bing_playwright":
                results = await page.query_selector_all("li.b_algo h2 a")

            elif engine == "yahoo_playwright":
                results = await page.query_selector_all("div.compTitle h3.title a")

            elif engine == "ecosia_playwright":
                await page.wait_for_selector("a.result__link", timeout=10000)
                results = await page.query_selector_all("a.result__link")

            elif engine == "mojeek_playwright":
                await page.wait_for_selector("a.title", timeout=10000)
                results = await page.query_selector_all("a.title")

            else:
                print("Unknown engine")
                return []

            if not results:
                print(f"[{engine}] No URLs found — possibly blocked or CAPTCHA.")
                print("Please solve CAPTCHA or wait for results. We'll retry in 20 seconds...")
                await asyncio.sleep(5)
                # Retry logic
                if engine == "duck_playwright":
                    results = await page.query_selector_all("a.result__a")
                elif engine == "bing_playwright":
                    results = await page.query_selector_all("li.b_algo h2 a")
                elif engine == "yahoo_playwright":
                    results = await page.query_selector_all("div.compTitle h3.title a")
                elif engine == "ecosia_playwright":
                    results = await page.query_selector_all("a.result__link")
                elif engine == "mojeek_playwright":
                    results = await page.query_selector_all("div.result_title a")

            for r in results:
                try:
                    href = await r.get_attribute("href")
                    if not href:
                        continue
                    if "uddg=" in href:
                        parts = href.split("uddg=")
                        if len(parts) > 1:
                            href = urllib.parse.unquote(parts[1].split("&")[0])
                    if href.startswith("http") and href not in urls:
                        urls.append(href)
                except Exception as e:
                    print(f"Skipped a bad link: {e}")
        except Exception as e:
            print(f"Error while processing {engine}: {e}")
        finally:
            await browser.close()

    if not urls:
        print(f"Still no URLs found for {engine} after retry.")

    return urls

async def smart_search(query: str, limit: int = 5) -> List[str]:
    # random.shuffle(SEARCH_ENGINES) # Disable shuffle to prioritize duck_http

    for engine in SEARCH_ENGINES:
        print(f"Trying engine: {engine}")
        try:
            if engine == "duck_http":
                # Only use duck_http for first attempt if query likely to succeed
                results = await use_duckduckgo_http(query)
            else:
                results = await use_playwright_search(query, engine)
            if results:
                return results[:limit]
            else:
                print(f"No results from {engine}. Trying next...")
        except Exception as e:
            print(f"Engine {engine} failed: {e}. Trying next...")

    print("All engines failed.")
    return []

if __name__ == "__main__":
    query = "Model Context Protocol"
    results = asyncio.run(smart_search(query))
    print("\n[URLs]:")
    for url in results:
        print("-", url)
