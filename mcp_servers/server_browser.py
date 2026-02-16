import json
from mcp.server.fastmcp import FastMCP, Context
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import urllib.parse
import sys
import traceback
from datetime import datetime
import asyncio
import os
from dotenv import load_dotenv

# MCP Protocol Safety: Redirect print to stderr
def print(*args, **kwargs):
    sys.stderr.write(" ".join(map(str, args)) + "\n")
    sys.stderr.flush()

load_dotenv()

# Browser Use Imports
try:
    from browser_use import Agent, Browser, BrowserConfig
    from langchain_google_genai import ChatGoogleGenerativeAI
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    sys.stderr.write("⚠️ browser-use not installed. Vision features will be disabled.\n")

load_dotenv()

# Initialize FastMCP server
mcp = FastMCP("hybrid-browser")

# Global Browser Instance for Persistence
GLOBAL_BROWSER = None

async def get_shared_browser():
    global GLOBAL_BROWSER
    if not BROWSER_USE_AVAILABLE:
        return None
        
    if GLOBAL_BROWSER is None:
        try:
            # Try connecting to local Chrome first
            # We use CDP to verify connection before init
            if await CDPClient.get_active_tab():
                print("Reusing existing Chrome instance on port 9222")
                GLOBAL_BROWSER = Browser(config=BrowserConfig(cdp_url="http://localhost:9222"))
            else:
                print("Launching new Chrome instance (headless=True)")
                GLOBAL_BROWSER = Browser()
        except Exception as e:
            print(f"Failed to init shared browser: {e}")
            return None
            
    return GLOBAL_BROWSER

# --- Tool 1: Fast Robust Search (DuckDuckGo + Fallbacks) ---

# --- Robust Tools Imports ---
try:
    from tools.switch_search_method import smart_search
    from tools.web_tools_async import smart_web_extract
except ImportError:
    # Try relative import if running as module
    from .tools.switch_search_method import smart_search
    from .tools.web_tools_async import smart_web_extract

@mcp.tool()
async def web_search(string: str, integer: int = 5) -> str:
    """Search the web using multiple engines (DuckDuckGo, Bing, Ecosia, etc.) and return a list of relevant result URLs"""
    try:
        urls = await smart_search(string, integer)
        return json.dumps(urls)
    except Exception as e:
        return f"[Error] Search failed: {str(e)}"

@mcp.tool()
async def web_extract_text(string: str) -> str:
    """Extract readable text from a webpage using robust methods (Playwright/Trafilatura)."""
    try:
        # Timeout 45s for robust extraction
        result = await asyncio.wait_for(smart_web_extract(string), timeout=45)
        text = result.get("best_text", "")[:15000] # Increased limit
        return text if text else "[Error] No text extracted"
    except Exception as e:
        return f"[Error] Extraction failed: {str(e)}"

# --- Tool 3: Advanced Bulk Search (Restored from Legacy) ---

from mcp.types import TextContent

@mcp.tool()
async def search_web_with_text_content(string: str) -> dict:
    """Search web and return URLs with extracted text content. Gets both URLs and readable text from top search results. Ideal for exhaustive research."""
    
    try:
        # Step 1: Get URLs
        urls = await smart_search(string, 5) # Default to 5
        
        if not urls:
            return {
                "content": [
                    TextContent(
                        type="text",
                        text="[error] No search results found"
                    )
                ]
            }
        
        # Step 2: Extract text content from each URL
        results = []
        max_extracts = min(len(urls), 5)
        
        for i, url in enumerate(urls[:max_extracts]):
            try:
                print(f"Link: {url} | Status: Visiting...") 
                web_result = await asyncio.wait_for(smart_web_extract(url), timeout=20)
                text_content = web_result.get("best_text", "")[:4000]
                text_content = text_content.replace('\n', ' ').replace('  ', ' ').strip()
                token_count = len(text_content) // 4
                
                print(f"Link: {url} | Status: Extracted | Tokens: {token_count}")

                results.append({
                    "url": url,
                    "content": text_content if text_content.strip() else "[error] No readable content found",
                    "images": web_result.get("images", []),
                    "rank": i + 1
                })
            except Exception as e:
                print(f"Link: {url} | Status: Failed | Error: {str(e)}")
                results.append({
                    "url": url,
                    "content": f"[error] {str(e)}",
                    "rank": i + 1
                })
        
        return {
            "content": [
                TextContent(
                    type="text",
                    text=json.dumps(results)
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"[error] {str(e)}"
                )
            ]
        }

@mcp.tool()
async def fetch_search_urls(string: str, integer: int = 5) -> str:
    """Get top website URLs for your search query. Just gets the URLs not the contents."""
    try:
        urls = await smart_search(string, integer)
        return json.dumps(urls)
    except Exception as e:
        return f"[Error] Search failed: {str(e)}"

@mcp.tool()
async def webpage_url_to_raw_text(string: str) -> dict:
    """Extract readable text from a webpage."""
    try:
        result = await asyncio.wait_for(smart_web_extract(string), timeout=30)
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"[{result.get('best_text_source', '')}] " + result.get("best_text", "")[:8000]
                )
            ]
        }
    except Exception as e:
        return {
            "content": [
                TextContent(
                    type="text",
                    text=f"[error] Failed to extract: {str(e)}"
                )
            ]
        }

# ... (rest of file) ...

@mcp.tool()
async def browser_use_action(string: str, headless: bool = True) -> str:
    """
    Execute a complex browser task using Vision and generic reasoning.
    Use this for: Logging in, filling forms, navigating complex sites, or when text search fails.
    WARNING: Slow and expensive.
    """
    if not BROWSER_USE_AVAILABLE:
        return "Error: `browser-use` library is not installed."

    try:
        # Import settings for model provider and name
        try:
            from config.settings_loader import settings
            agent_settings = settings.get("agent", {})
            model_provider = agent_settings.get("model_provider", "gemini")
            model_name = agent_settings.get("default_model", "gemini-2.5-flash")
            ollama_base_url = settings.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")
        except:
            model_provider = "gemini"
            model_name = "gemini-2.5-flash"
            ollama_base_url = "http://127.0.0.1:11434"
        
        # Initialize LLM based on provider
        if model_provider == "ollama":
            try:
                from langchain_ollama import ChatOllama
                llm = ChatOllama(model=model_name, base_url=ollama_base_url)
                print(f"🖥️ Browser Use: Using Ollama model {model_name}")
            except ImportError:
                print("⚠️ langchain_ollama not installed, falling back to Gemini")
                llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))
        else:
            llm = ChatGoogleGenerativeAI(model=model_name, google_api_key=os.getenv("GEMINI_API_KEY"))
            print(f"☁️ Browser Use: Using Gemini model {model_name}")
        
        # Get shared browser
        browser = await get_shared_browser()
        
        # Initialize Agent
        if browser:
             agent = Agent(task=string, llm=llm, browser=browser)
        else:
             agent = Agent(task=string, llm=llm) # Fallback to default
        
        # Run
        history = await agent.run()
        result = history.final_result()
        return result if result else "Task completed but returned no text result."


    except Exception as e:
        traceback.print_exc()
        return f"Browser Action Failed: {str(e)}"

# --- Tool 3: Chrome DevTools Protocol (CDP) ---
# Connects to local Chrome/Edge instance running with --remote-debugging-port=9222

class CDPClient:
    BASE_URL = "http://localhost:9222"
    
    @classmethod
    async def get_active_tab(cls):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{cls.BASE_URL}/json/list", timeout=2.0)
                pages = resp.json()
                # Prioritize 'page' type and active ones
                for p in pages:
                    if p.get("type") == "page":
                        return p
                return pages[0] if pages else None
        except httpx.ConnectError:
            return None
        except Exception as e:
            print(f"CDP Error: {e}")
            return None

@mcp.tool()
async def get_current_url() -> str:
    """Get the URL of the currently active tab in local Chrome (port 9222)."""
    tab = await CDPClient.get_active_tab()
    if not tab:
        return "Error: Could not connect to Chrome on port 9222. Is it running with --remote-debugging-port=9222?"
    return tab.get("url", "Unknown URL")

@mcp.tool()
async def navigate(url: str) -> str:
    """Navigate the active Chrome tab to a URL."""
    import websockets
    
    if not url.startswith("http"):
        url = "https://" + url
        
    tab = await CDPClient.get_active_tab()
    if not tab:
        return "Error: Could not connect to Chrome."
        
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url:
        return "Error: No WebSocket URL found for tab."
        
    try:
        async with websockets.connect(ws_url) as ws:
            # Navigate
            await ws.send(json.dumps({
                "id": 1,
                "method": "Page.navigate",
                "params": {"url": url}
            }))
            resp = await ws.recv()
            return f"Navigated to {url}. Response: {resp}"
    except Exception as e:
        return f"Navigation failed: {e}"

@mcp.tool()
async def screenshot() -> str:
    """Take a screenshot of the active tab and return base64 string (truncated or saved)."""
    # Simply return a message for now as returning huge base64 to LLM is bad
    # Better to save to file and return path
    import websockets
    import base64
    
    tab = await CDPClient.get_active_tab()
    if not tab: return "Error: No Chrome connection."
    
    ws_url = tab.get("webSocketDebuggerUrl")
    if not ws_url: return "Error: No WebSocket."
    
    try:
        async with websockets.connect(ws_url) as ws:
            await ws.send(json.dumps({
                "id": 2,
                "method": "Page.captureScreenshot",
                "params": {"format": "png"}
            }))
            
            # Wait for response (might be large)
            while True:
                resp = json.loads(await ws.recv())
                if resp.get("id") == 2:
                    break
            
            data = resp.get("result", {}).get("data")
            if data:
                # Save to file
                filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                path = os.path.join(os.getcwd(), "data", "screenshots", filename)
                os.makedirs(os.path.dirname(path), exist_ok=True)
                
                with open(path, "wb") as f:
                    f.write(base64.b64decode(data))
                return f"Screenshot saved to {path}"
            return "Error: No data in response"
    except Exception as e:
        return f"Screenshot failed: {e}"

if __name__ == "__main__":
    mcp.run(transport="stdio")

