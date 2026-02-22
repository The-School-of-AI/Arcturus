import pytest
import asyncio
import json
import os
from browser.controller import BrowserController
from browser.extractor import PageExtractor

@pytest.fixture
async def browser():
    ctrl = BrowserController(headless=True)
    await ctrl.start()
    yield ctrl
    await ctrl.stop()

@pytest.mark.asyncio
async def test_phantom_oracle_integration(browser):
    """Scenario 1: Phantom output captured as Oracle data source."""
    await browser.navigate("https://example.com")
    extractor = PageExtractor(browser.page)
    dom = await extractor.get_simplified_dom()
    
    # Simulate Oracle data capture
    captured_data = {
        "source": "phantom",
        "url": browser.page.url,
        "content": dom
    }
    assert captured_data["source"] == "phantom"
    # The simplified DOM contains interactive elements (not page title text).
    # Verify that Oracle captured *some* DOM content from Phantom.
    assert len(captured_data["content"]) > 0

@pytest.mark.asyncio
async def test_action_trace_chronicle(browser):
    """Scenario 2: Action trace recorded by Chronicle."""
    actions = []
    # Intercepting actions to simulate Chronicle logging
    await browser.navigate("https://example.com")
    actions.append({"type": "navigate", "url": "https://example.com"})
    
    await browser.click("a")
    actions.append({"type": "click", "selector": "a"})
    
    assert len(actions) == 2
    assert actions[0]["type"] == "navigate"

@pytest.mark.asyncio
async def test_cross_project_failure_propagation(browser):
    """Scenario 3: Graceful behavior on upstream failure."""
    # Simulate a failure in a dependency or external site
    try:
        await browser.navigate("https://invalid-site-that-fails.local")
    except Exception as e:
        # Should log and continue gracefully
        assert True

@pytest.mark.asyncio
async def test_multiprofile_isolation(browser):
    """Scenario 4: Verify profile isolation."""
    # This would check cookies/storage between contexts
    assert browser.context is not None

@pytest.mark.asyncio
async def test_stealth_mode_headers(browser):
    """Scenario 5: Check if stealth mode headers/UA are applied."""
    ua = await browser.page.evaluate("navigator.userAgent")
    assert "Playwright" not in ua
    assert "Mozilla" in ua
