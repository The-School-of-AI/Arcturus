
try:
    from browser_use import Agent, Browser, BrowserConfig
    print("Browser and BrowserConfig found")
except ImportError as e:
    print(f"ImportError: {e}")
    try:
        from browser_use.browser.browser import Browser, BrowserConfig
        print("Found in browser_use.browser.browser")
    except ImportError:
        print("Could not find Browser/BrowserConfig")
