import sys
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

from routers.browser_utils import perform_web_search, extract_url_content

async def main():
    print("Testing Web Search...")
    try:
        results = await perform_web_search("python fastapi", count=2)
        print(f"Search Results: {results[:100]}...") # Truncate
    except Exception as e:
        print(f"Search Failed: {e}")

    print("\nTesting URL Extraction...")
    try:
        # Use a stable URL
        text = await extract_url_content("https://fastapi.tiangolo.com/")
        print(f"Extraction result length: {len(text)}")
        print(f"Sample content: {text[:100]}...")
    except Exception as e:
        print(f"Extraction Failed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except ImportError as e:
        print(f"Dependencies missing (likely mcp_servers not setup recursively): {e}")
