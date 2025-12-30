# Hybrid Browser MCP Server

This MCP server provides advanced web browsing and content extraction capabilities, bridging the gap between simple text search and complex autonomous browsing.

## Tools

### `web_search(string: str, integer: int = 5) -> str`
Search the web using multiple engines (DuckDuckGo, Bing, Ecosia) and return a list of relevent URLS.
- **string**: The search query.
- **integer**: Number of results to return (default: 5).

### `web_extract_text(string: str) -> str`
Extract readable text from a webpage using robust methods (Playwright/Trafilatura).
- **string**: The URL to extract content from.

### `search_web_with_text_content(string: str) -> dict`
Search the web and return URLs *with* extracted text content. Ideal for exhaustive research where you need context immediately.
- **string**: The search query.

### `fetch_search_urls(string: str, integer: int = 5) -> str`
Get top website URLs for your search query. Just gets the URLs, not the contents.
- **string**: The search query.

### `webpage_url_to_raw_text(string: str) -> dict`
Extract readable text from a webpage (Alias for `web_extract_text` but returns dict format).
- **string**: The URL to extract.

### `browser_use_action(string: str, headless: bool = True) -> str`
Execute a complex browser task using Vision and generic reasoning (requires `browser-use`).
- **string**: The natural language task description (e.g., "Go to amazon, search for shoes, find the cheapest one").
