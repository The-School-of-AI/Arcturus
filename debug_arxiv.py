import feedparser
import requests

url = "http://export.arxiv.org/rss/cs.AI"
print(f"Testing URL: {url}")

try:
    # First try requests to check connectivity/status
    response = requests.get(url, timeout=10)
    print(f"Status Code: {response.status_code}")
    print(f"Content Length: {len(response.text)}")
    print(f"First 500 chars: {response.text[:500]}")
    
    # Then try feedparser
    feed = feedparser.parse(url)
    print(f"Feed Title: {feed.feed.get('title', 'No Title')}")
    print(f"Number of entries: {len(feed.entries)}")
    if feed.entries:
        print(f"First entry: {feed.entries[0].title}")
    
    if feed.bozo:
        print(f"Feedparser error (bozo): {feed.bozo_exception}")

except Exception as e:
    print(f"Error: {e}")
