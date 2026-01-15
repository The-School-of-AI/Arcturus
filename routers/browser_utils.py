import sys
from pathlib import Path
import asyncio
import json

# Add project root to sys.path to allow importing mcp_servers
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from mcp_servers.tools.switch_search_method import smart_search
from mcp_servers.tools.web_tools_async import smart_web_extract

async def perform_web_search(query: str, count: int = 5) -> str:
    """
    Perform a web search and return a list of URLs.
    """
    try:
        urls = await smart_search(query, count)
        return json.dumps(urls)
    except Exception as e:
        return f"[Error] Search failed: {str(e)}"

async def extract_url_content(url: str, timeout: int = 45) -> str:
    """
    Extract readable text from a URL using robust methods.
    """
    try:
        result = await asyncio.wait_for(smart_web_extract(url), timeout=timeout)
        text = result.get("best_text", "")[:15000]
        return text if text else "[Error] No text extracted"
    except Exception as e:
        return f"[Error] Extraction failed: {str(e)}"
