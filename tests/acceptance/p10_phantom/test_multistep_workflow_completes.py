import pytest
import asyncio
from browser.controller import BrowserController
from browser.extractor import PageExtractor

@pytest.fixture
async def browser():
    ctrl = BrowserController(headless=True)
    await ctrl.start()
    yield ctrl
    await ctrl.stop()

@pytest.mark.asyncio
async def test_navigation(browser):
    """Test 1: Basic navigation."""
    await browser.navigate("https://example.com")
    assert "Example Domain" in await browser.page.title()

@pytest.mark.asyncio
async def test_element_extraction(browser):
    """Test 2: Simplified DOM extraction."""
    await browser.navigate("https://example.com")
    extractor = PageExtractor(browser.page)
    dom = await extractor.get_simplified_dom()
    assert "[e0]" in dom

@pytest.mark.asyncio
async def test_click_interaction(browser):
    """Test 3: Click interaction."""
    await browser.navigate("https://example.com")
    # example.com has one link
    await browser.click("a")
    assert "iana.org" in browser.page.url

@pytest.mark.asyncio
async def test_typing_interaction(browser):
    """Test 4: Typing interaction."""
    # Using a site with a search bar for typing test
    await browser.navigate("https://www.google.com")
    # Basic check - might need adjustment based on consent screens
    try:
        await browser.type('textarea[name="q"]', "Phantom Agent")
    except:
        pytest.skip("Search bar not found (likely consent screen)")

@pytest.mark.asyncio
async def test_screenshot_capture(browser):
    """Test 5: Screenshot capability."""
    await browser.navigate("https://example.com")
    path = await browser.get_screenshot("test_ss.png")
    import os
    assert os.path.exists(path)

@pytest.mark.asyncio
async def test_accessibility_tree(browser):
    """Test 6: Accessibility tree snapshot."""
    await browser.navigate("https://example.com")
    extractor = PageExtractor(browser.page)
    tree = await extractor.get_accessibility_tree()
    assert "role" in tree
    assert "snapshot" in tree

@pytest.mark.asyncio
async def test_invalid_url_handling(browser):
    """Test 7: Error handling for invalid URL."""
    with pytest.raises(Exception):
        await browser.navigate("https://this-is-not-a-real-website-12345.com")

@pytest.mark.asyncio
async def test_multistep_workflow(browser):
    """Test 8: Multi-step workflow completeness."""
    await browser.navigate("https://example.com")
    await browser.click("a")
    assert "iana.org" in browser.page.url
    await browser.navigate("https://example.com")
    extractor = PageExtractor(browser.page)
    dom = await extractor.get_simplified_dom()
    assert "Example Domain" in await browser.page.content()
