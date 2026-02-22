import json
from mcp.server.fastmcp import FastMCP, Context
from typing import List, Dict, Optional, Any
import sys
import traceback
import os
import asyncio
from dotenv import load_dotenv

# Add the project root to sys.path to import browser module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from browser.controller import BrowserController
from browser.extractor import PageExtractor
from browser.logic import AgentLoop, LLMClassifier

# ... (inside get_controller or as a helper)
async def get_extractor():
    ctrl = await get_controller()
    return PageExtractor(ctrl.page)

@mcp.tool()
async def browser_autonomous_task(task: str) -> str:
    """Execute a task autonomously using the agent action loop."""
    try:
        ctrl = await get_controller()
        extractor = await get_extractor()
        loop = AgentLoop(ctrl, extractor)
        result = await loop.execute_task(task)
        return json.dumps(result, indent=2)
    except Exception as e:
        return f"Error executing autonomous task: {str(e)}"

@mcp.tool()
async def browser_get_simplified_dom() -> str:
    """Get a simplified, LLM-friendly DOM representation of the current page."""
    try:
        extractor = await get_extractor()
        return await extractor.get_simplified_dom()
    except Exception as e:
        return f"Error extracting simplified DOM: {str(e)}"

@mcp.tool()
async def browser_accessibility_tree() -> str:
    """Get the accessibility tree snapshot of the current page."""
    try:
        extractor = await get_extractor()
        tree = await extractor.get_accessibility_tree()
        return json.dumps(tree, indent=2)
    except Exception as e:
        return f"Error getting accessibility tree: {str(e)}"

@mcp.tool()
async def browser_select(selector: str, value: str) -> str:
    """Select an option from a dropdown menu."""
    try:
        ctrl = await get_controller()
        await ctrl.select_option(selector, value)
        return f"Selected {value} in {selector}"
    except Exception as e:
        return f"Error selecting {value} in {selector}: {str(e)}"

@mcp.tool()
async def browser_scroll(direction: str = "down", amount: int = 500) -> str:
    """Scroll the page up or down."""
    try:
        ctrl = await get_controller()
        await ctrl.scroll(direction, amount)
        return f"Scrolled {direction} by {amount}px"
    except Exception as e:
        return f"Error scrolling: {str(e)}"

@mcp.tool()
async def browser_navigate(url: str) -> str:
    """Navigate to a specified URL."""
    try:
        ctrl = await get_controller()
        await ctrl.navigate(url)
        return f"Successfully navigated to {url}"
    except Exception as e:
        return f"Error navigating to {url}: {str(e)}"

@mcp.tool()
async def browser_click(selector: str) -> str:
    """Click an element on the current page using a CSS selector."""
    try:
        ctrl = await get_controller()
        await ctrl.click(selector)
        return f"Clicked element: {selector}"
    except Exception as e:
        return f"Error clicking {selector}: {str(e)}"

@mcp.tool()
async def browser_type(selector: str, text: str) -> str:
    """Type text into an input field."""
    try:
        ctrl = await get_controller()
        await ctrl.type(selector, text)
        return f"Typed text into {selector}"
    except Exception as e:
        return f"Error typing into {selector}: {str(e)}"

@mcp.tool()
async def browser_screenshot() -> str:
    """Capture a screenshot of the current page."""
    try:
        ctrl = await get_controller()
        path = await ctrl.get_screenshot()
        return f"Screenshot saved to {path}"
    except Exception as e:
        return f"Error taking screenshot: {str(e)}"

@mcp.tool()
async def browser_get_content() -> str:
    """Get the HTML content of the current page."""
    try:
        ctrl = await get_controller()
        content = await ctrl.get_page_content()
        return content[:50000] # Limit output size for MCP
    except Exception as e:
        return f"Error getting content: {str(e)}"

# Keep existing search tools but make them optional or refactor them if needed
# For now, let's focus on the Phantom core requirements

@mcp.tool()
async def web_search(query: str, num_results: int = 5) -> str:
    """Search the web (placeholder for integrated search)."""
    # This can later be integrated with the controller to perform searches via a search engine page
    return f"Search for '{query}' requested. Phantom prefers direct navigation for precision."

if __name__ == "__main__":
    mcp.run(transport="stdio")

