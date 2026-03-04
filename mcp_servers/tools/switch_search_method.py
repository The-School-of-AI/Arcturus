import random
import asyncio
import httpx
import os
from typing import List
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import urllib.parse
from playwright.async_api import async_playwright
import sys
from dotenv import load_dotenv

load_dotenv()

# MCP Protocol Safety: Redirect print to stderr
def print(*args, **kwargs):
    sys.stderr.write(" ".join(map(str, args)) + "\n")
    sys.stderr.flush()

SEARCH_ENGINES = [
    "brave_api",
    "google_custom_search",
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

async def use_brave_api(query: str, limit: int = 10, freshness: str = "") -> List[str]:
    """Search using Brave Search API. Returns list of URLs."""
    api_key = os.getenv("BRAVE_API_KEY")
    if not api_key:
        print("[brave_api] BRAVE_API_KEY not set, skipping")
        return []

    await rate_limiter.acquire("brave_api")

    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query, "count": min(limit, 20)}
    if freshness:
        params["freshness"] = freshness

    async with httpx.AsyncClient() as client:
        r = await client.get(url, headers=headers, params=params, timeout=15.0)
        r.raise_for_status()
        data = r.json()

        links = []
        web_results = data.get("web", {}).get("results", [])
        for result in web_results:
            href = result.get("url", "")
            if href and href.startswith("http") and href not in links:
                links.append(href)

        if not links:
            print("[brave_api] No links found in results")

        return links

_FRESHNESS_TO_DATE_RESTRICT = {"pd": "d1", "pw": "w1", "pm": "m1", "py": "y1"}

async def use_google_custom_search(query: str, limit: int = 10, freshness: str = "") -> List[str]:
    """Search using Google Custom Search JSON API. Returns list of URLs."""
    api_key = os.getenv("GOOGLE_CUSTOM_SEARCH_API_KEY")
    engine_id = os.getenv("GOOGLE_CUSTOM_SEARCH_ENGINE_ID")
    if not api_key or not engine_id:
        print("[google_custom_search] API key or engine ID not set, skipping")
        return []

    await rate_limiter.acquire("google_custom_search")

    url = "https://www.googleapis.com/customsearch/v1"
    params = {
        "key": api_key,
        "cx": engine_id,
        "q": query,
        "num": min(limit, 10),
    }
    if freshness and freshness in _FRESHNESS_TO_DATE_RESTRICT:
        params["dateRestrict"] = _FRESHNESS_TO_DATE_RESTRICT[freshness]

    async with httpx.AsyncClient() as client:
        r = await client.get(url, params=params, timeout=15.0)
        r.raise_for_status()
        data = r.json()

        links = []
        for item in data.get("items", []):
            href = item.get("link", "")
            if href and href.startswith("http") and href not in links:
                links.append(href)

        if not links:
            print("[google_custom_search] No links found in results")

        return links

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

async def smart_search(query: str, limit: int = 5, freshness: str = "") -> List[str]:
    for engine in SEARCH_ENGINES:
        print(f"Trying engine: {engine}")
        try:
            if engine == "brave_api":
                results = await use_brave_api(query, limit=limit, freshness=freshness)
            elif engine == "google_custom_search":
                results = await use_google_custom_search(query, limit=limit, freshness=freshness)
            elif engine == "duck_http":
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
