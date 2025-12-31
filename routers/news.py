from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import requests
import feedparser
from bs4 import BeautifulSoup
import json
from datetime import datetime
import asyncio
from config.settings_loader import settings, save_settings

router = APIRouter(prefix="/news", tags=["news"])

# Default News Sources
DEFAULT_SOURCES = [
    {"id": "hn", "name": "Hacker News", "url": "https://news.ycombinator.com", "type": "api", "enabled": True},
    {"id": "arxiv", "name": "arXiv CS.AI", "url": "https://arxiv.org/list/cs.AI/recent", "type": "rss", "feed_url": "https://rss.arxiv.org/rss/cs.AI", "enabled": True},
    {"id": "karpathy", "name": "Andrej Karpathy", "url": "https://twitter.com/karpathy", "type": "rss", "feed_url": "https://nitter.net/karpathy/rss", "enabled": True},
    {"id": "willison", "name": "Simon Willison", "url": "https://simonwillison.net/", "type": "rss", "feed_url": "https://simonwillison.net/atom/entries/", "enabled": True},
]

def get_news_settings():
    if "news" not in settings:
        settings["news"] = {"sources": DEFAULT_SOURCES}
        save_settings()
    return settings["news"]

class NewsSource(BaseModel):
    id: str
    name: str
    url: str
    type: str # 'rss', 'api', 'scrape'
    feed_url: Optional[str] = None
    enabled: bool = True

class NewsItem(BaseModel):
    id: str
    title: str
    url: str
    source_name: str
    timestamp: str
    points: Optional[int] = None
    comments: Optional[int] = None
    summary: Optional[str] = None

@router.get("/sources")
async def get_sources():
    news_settings = get_news_settings()
    return {"status": "success", "sources": news_settings["sources"]}

class AddSourceTabsRequest(BaseModel):
    name: str
    url: str

@router.post("/sources")
async def add_source(request: AddSourceTabsRequest):
    news_settings = get_news_settings()
    
    # Check for duplicates
    if any(s["url"] == request.url for s in news_settings["sources"]):
        raise HTTPException(status_code=400, detail="Source already exists")
    
    # Try to discover RSS feed
    feed_url = None
    try:
        response = requests.get(request.url, timeout=5)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Look for RSS/Atom links
        rss_link = soup.find('link', type='application/rss+xml') or \
                   soup.find('link', type='application/atom+xml')
        
        if rss_link:
            feed_url = rss_link.get('href')
            if feed_url and not feed_url.startswith('http'):
                # Handle relative paths
                from urllib.parse import urljoin
                feed_url = urljoin(request.url, feed_url)
    except Exception as e:
        print(f"Feed discovery failed for {request.url}: {e}")

    new_source = {
        "id": request.name.lower().replace(" ", "_"),
        "name": request.name,
        "url": request.url,
        "type": "rss" if feed_url else "scrape",
        "feed_url": feed_url,
        "enabled": True
    }
    
    news_settings["sources"].append(new_source)
    save_settings()
    return {"status": "success", "source": new_source}

@router.delete("/sources/{source_id}")
async def delete_source(source_id: str):
    news_settings = get_news_settings()
    news_settings["sources"] = [s for s in news_settings["sources"] if s["id"] != source_id]
    save_settings()
    return {"status": "success"}

# Simple in-memory cache for HN stories
_hn_cache = {"items": [], "timestamp": 0}
HN_CACHE_TTL = 300  # 5 minutes

async def fetch_hn():
    """Fetch Hacker News top stories with caching and parallel requests."""
    import time
    global _hn_cache
    
    # Return cached data if fresh
    if time.time() - _hn_cache["timestamp"] < HN_CACHE_TTL and _hn_cache["items"]:
        return _hn_cache["items"]
    
    try:
        import aiohttp
        
        # Get top stories (limit to 20 for speed)
        async with aiohttp.ClientSession() as session:
            async with session.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                story_ids = (await resp.json())[:20]
            
            # Fetch all stories in parallel
            async def fetch_story(sid):
                try:
                    async with session.get(f"https://hacker-news.firebaseio.com/v0/item/{sid}.json", timeout=aiohttp.ClientTimeout(total=5)) as sresp:
                        story = await sresp.json()
                        if story:
                            return NewsItem(
                                id=f"hn_{sid}",
                                title=story.get("title", ""),
                                url=story.get("url", f"https://news.ycombinator.com/item?id={sid}"),
                                source_name="Hacker News",
                                timestamp=datetime.fromtimestamp(story.get("time", 0)).isoformat(),
                                points=story.get("score"),
                                comments=len(story.get("kids", [])) if "kids" in story else 0
                            )
                except Exception as e:
                    print(f"Error fetching story {sid}: {e}")
                return None
            
            items = await asyncio.gather(*[fetch_story(sid) for sid in story_ids])
            items = [i for i in items if i is not None]
            
            # Update cache
            _hn_cache = {"items": items, "timestamp": time.time()}
            return items
            
    except Exception as e:
        print(f"HN fetch error: {e}")
        # Return stale cache if available
        if _hn_cache["items"]:
            return _hn_cache["items"]
        return []

async def fetch_rss(source):
    try:
        feed = feedparser.parse(source["feed_url"])
        items = []
        for entry in feed.entries[:30]:
            # Try to get timestamp
            ts = datetime.now().isoformat()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                ts = datetime(*entry.published_parsed[:6]).isoformat()
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                ts = datetime(*entry.updated_parsed[:6]).isoformat()
                
            items.append(NewsItem(
                id=f"{source['id']}_{entry.get('id', entry.link)}",
                title=entry.title,
                url=entry.link,
                source_name=source["name"],
                timestamp=ts,
                summary=entry.get("summary", "")[:200]
            ))
        return items
    except Exception as e:
        print(f"RSS fetch error for {source['name']}: {e}")
        return []

@router.get("/feed")
async def get_feed(source_id: Optional[str] = None):
    news_settings = get_news_settings()
    sources = news_settings["sources"]
    
    if source_id:
        sources = [s for s in sources if s["id"] == source_id]
    
    all_items = []
    tasks = []
    
    for source in sources:
        if not source.get("enabled", True):
            continue
            
        if source["id"] == "hn":
            tasks.append(fetch_hn())
        elif source["type"] == "rss" and source["feed_url"]:
            tasks.append(fetch_rss(source))
    
    results = await asyncio.gather(*tasks)
    for res in results:
        all_items.extend(res)
        
    # Sort by timestamp
    all_items.sort(key=lambda x: x.timestamp, reverse=True)
    
    return {"status": "success", "items": all_items[:100]}

@router.get("/article")
async def get_article_content(url: str):
    """Fetch and render a full webpage using Playwright, returning the complete HTML."""
    try:
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            # Launch headless browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Navigate to the URL and wait for content
            await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            
            # Wait a bit more for dynamic content
            await page.wait_for_timeout(1000)
            
            # Get the full rendered HTML
            html_content = await page.content()
            
            await browser.close()
            
            # Inject a base tag so relative URLs resolve correctly
            if "<base" not in html_content.lower():
                from urllib.parse import urljoin
                base_tag = f'<base href="{url}" target="_blank">'
                html_content = html_content.replace("<head>", f"<head>{base_tag}", 1)
            
            return {"status": "success", "html": html_content, "url": url}
            
    except Exception as e:
        print(f"Playwright rendering error for {url}: {e}")
        return {"status": "error", "error": str(e)}
