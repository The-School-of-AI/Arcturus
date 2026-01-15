from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Any
import asyncio
import json

# Import directly from the tools used in server_browser
try:
    from mcp_servers.tools.switch_search_method import smart_search
    from mcp_servers.tools.web_tools_async import smart_web_extract
except ImportError:
    # Fallback/Debug path if needed
    import sys
    sys.path.append('.')
    from mcp_servers.tools.switch_search_method import smart_search
    from mcp_servers.tools.web_tools_async import smart_web_extract

router = APIRouter(prefix="/agent")

class SearchRequest(BaseModel):
    query: str
    limit: Optional[int] = 5

class UrlRequest(BaseModel):
    url: str

@router.post("/search")
async def agent_search(request: SearchRequest):
    """
    "God Mode" search: Searches web, visits top results, extracts text.
    Returns: JSON string of results with 'url', 'content', 'rank'.
    """
    try:
        # Step 1: Get URLs
        urls = await smart_search(request.query, request.limit)
        
        if not urls:
            return {"status": "success", "results": [], "message": "No results found"}
        
        # Step 2: Extract text content from each URL parallelly
        results = []
        max_extracts = min(len(urls), request.limit)
        
        # We process sequentially here for safety, but could parallelize with gather
        # Re-using logic from server_browser.py
        for i, url in enumerate(urls[:max_extracts]):
            try:
                # Timeout 20s per page
                web_result = await asyncio.wait_for(smart_web_extract(url), timeout=20)
                text_content = web_result.get("best_text", "")[:4000] # Cap content size
                # Clean whitespace
                text_content = " ".join(text_content.split())
                
                results.append({
                    "url": url,
                    "title": web_result.get("title", ""),
                    "content": text_content if text_content.strip() else "[No readable content]",
                    "rank": i + 1
                })
            except Exception as e:
                results.append({
                    "url": url,
                    "content": f"[Error visiting: {str(e)}]",
                    "rank": i + 1
                })
        
        return {
            "status": "success", 
            "results": results,
            "summary": f"Found and read {len(results)} pages for '{request.query}'"
        }

    except Exception as e:
        print(f"Agent Search Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/read_url")
async def agent_read_url(request: UrlRequest):
    """Reads a single specific URL."""
    try:
        result = await asyncio.wait_for(smart_web_extract(request.url), timeout=45)
        text = result.get("best_text", "")[:15000]
        return {
            "status": "success",
            "url": request.url,
            "title": result.get("title", ""),
            "content": text if text else "[No text extracted]"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read URL: {str(e)}")
