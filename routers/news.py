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
    {"id": "arxiv", "name": "arXiv CS.AI", "url": "https://arxiv.org/list/cs.AI/recent", "type": "rss", "feed_url": "http://export.arxiv.org/rss/cs.AI", "enabled": True},
    {"id": "karpathy", "name": "Andrej Karpathy", "url": "https://twitter.com/karpathy", "type": "rss", "feed_url": "https://nitter.net/karpathy/rss", "enabled": True},
    {"id": "willison", "name": "Simon Willison", "url": "https://simonwillison.net/", "type": "rss", "feed_url": "https://simonwillison.net/atom/entries/", "enabled": True},
]

def get_news_settings():
    if "news" not in settings:
        settings["news"] = {"sources": DEFAULT_SOURCES}
        save_settings()
    
    # Migration: Fix broken Arxiv URL
    sources = settings["news"]["sources"]
    dirty = False
    for s in sources:
        if s["id"] == "arxiv" and s["feed_url"] == "https://rss.arxiv.org/rss/cs.AI":
            s["feed_url"] = "http://export.arxiv.org/rss/cs.AI"
            dirty = True
    
    if dirty:
        print("  🔧 Automatically fixed broken Arxiv URL")
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
        # Detect PDF: Check extension, specific domains, or Head request
        is_pdf = url.lower().endswith('.pdf') or "arxiv.org/pdf/" in url
        
        if not is_pdf:
            # Fallback: Quick HEAD request to check Content-Type (with short timeout)
            try:
                head = requests.head(url, allow_redirects=True, timeout=2)
                if 'application/pdf' in head.headers.get('Content-Type', '').lower():
                    is_pdf = True
            except:
                pass # Ignore network errors during check

        if is_pdf:
            try:
                import io
                import pymupdf  # Ensure pymupdf is available
                
                # Fetch content
                response = requests.get(url, timeout=15)
                doc = pymupdf.open(stream=response.content, filetype="pdf")
                
                html_content = "<div style='padding: 20px; font-family: sans-serif;'>"
                # Render only first 10 pages to prevent massive load times for large docs
                for i, page in enumerate(doc):
                    if i >= 10:
                        html_content += "<p><em>... (Display limited to first 10 pages) ...</em></p>"
                        break
                    # Get HTML representation of the page
                    html_content += page.get_text("html")
                    html_content += "<hr style='margin: 20px 0; border: 0; border-top: 1px solid #ccc;'/>"
                
                html_content += "</div>"
                return {"status": "success", "html": html_content, "url": url}
            except Exception as e:
                print(f"PDF processing error for {url}: {e}")
                # Fallback to playwright if PDF processing fails (might still fail there)

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

@router.get("/reader")
async def get_reader_content(url: str):
    """Extract the main article content as markdown for reader mode."""
    try:
        # Detect PDF
        is_pdf = url.lower().endswith('.pdf') or "arxiv.org/pdf/" in url
        if not is_pdf:
             try:
                head = requests.head(url, allow_redirects=True, timeout=2)
                if 'application/pdf' in head.headers.get('Content-Type', '').lower():
                    is_pdf = True
             except: pass

        if is_pdf:
            try:
                import functools
                import pymupdf4llm
                import requests
                import pymupdf
                
                # Fetch PDF content
                response = requests.get(url, timeout=15)
                
                doc = pymupdf.open(stream=response.content, filetype="pdf")
                md_text = pymupdf4llm.to_markdown(doc)
                
                return {"status": "success", "content": md_text, "url": url}
            except Exception as e:
                print(f"PDF Reader error for {url}: {e}")
                # Fallthrough to trafilatura if custom handling fails

        import trafilatura
        
        # Download the web page
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"status": "error", "error": "Failed to fetch the URL"}
        
        # Extract the main content as markdown
        content = trafilatura.extract(
            downloaded,
            include_comments=False,
            include_tables=True,
            output_format='markdown'
        )
        
        if not content:
            # Fallback to plain text
            content = trafilatura.extract(downloaded, include_comments=False)
        
        if not content:
            return {"status": "error", "error": "Could not extract article content"}
        
        return {"status": "success", "content": content, "url": url}
    except Exception as e:
        print(f"Reader extraction error for {url}: {e}")
        return {"status": "error", "error": str(e)}

@router.get("/proxy")
async def proxy_content(url: str):
    """Proxy content to avoid CORS issues, specifically for PDFs."""
    try:
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(status_code=400, detail="Invalid URL")
            
        # Stream response
        r = requests.get(url, stream=True, timeout=30)
        
        def iterfile():
            try:
                for chunk in r.iter_content(chunk_size=8192):
                    yield chunk
            except Exception as e:
                print(f"Stream error: {e}")

        # Forward content type
        content_type = r.headers.get("Content-Type", "application/octet-stream")
        
        from fastapi.responses import StreamingResponse
        return StreamingResponse(iterfile(), media_type=content_type)
        
    except Exception as e:
        print(f"Proxy error for {url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
