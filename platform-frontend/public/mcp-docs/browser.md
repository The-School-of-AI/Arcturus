# Browser MCP

## Overview
The Browser MCP server provides advanced web interaction capabilities, allowing AI agents to search the web, extract content, and even perform complex browser automation tasks.

## Tools

### `web_search`
Search the web using multiple engines (DuckDuckGo, Bing, etc.) and return a list of relevant result URLs.
- **query**: The search string.
- **limit**: Number of results to return (default: 5).

### `web_extract_text`
Extract readable text from a webpage using robust methods (Playwright/Trafilatura).
- **url**: The URL to extract content from.

### `browser_use_action`
Execute a complex browser task using Vision and generic reasoning. Use this for logging in, filling forms, or navigating complex sites.
- **task**: Description of the task to perform.
- **headless**: Whether to run in headless mode (default: true).
