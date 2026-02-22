from playwright.async_api import Page, ElementHandle
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("phantom-extractor")

class PageExtractor:
    """
    Intelligent content extraction and DOM normalization.
    Converts complex web pages into simplified, LLM-friendly representations.
    Inspired by OpenClaw: uses accessibility roles and aria-refs.
    """
    
    def __init__(self, page: Page):
        self.page = page

    async def get_simplified_dom(self) -> str:
        """
        Produce a normalized DOM representation.
        Strips irrelevant elements and labels interactive components.
        """
        # Inject script to extract interactive elements and their accessibility info
        extract_script = """
        () => {
            const interactiveElements = [];
            const selectors = 'button, input, select, textarea, a, [role="button"], [role="link"], [role="checkbox"], [tabindex="0"]';
            const elements = document.querySelectorAll(selectors);
            
            elements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                if (rect.width > 0 && rect.height > 0 && window.getComputedStyle(el).visibility !== 'hidden') {
                    const ref = `e${index}`;
                    el.setAttribute('data-phantom-ref', ref);
                    
                    interactiveElements.push({
                        ref: ref,
                        tag: el.tagName.toLowerCase(),
                        role: el.getAttribute('role') || el.type || '',
                        text: el.innerText.trim() || el.placeholder || el.ariaLabel || '',
                        rect: {
                            x: rect.x,
                            y: rect.y,
                            width: rect.width,
                            height: rect.height
                        }
                    });
                }
            });
            return interactiveElements;
        }
        """
        try:
            elements = await self.page.evaluate(extract_script)
            
            # Build text representation
            lines = ["# Interactive Elements:"]
            for el in elements:
                lines.append(f"[{el['ref']}] {el['tag']}(role='{el['role']}', text='{el['text']}')")
            
            # Simple content summary
            content = await self.page.content()
            # In a real implementation, we would use Trafilatura or similar for main text
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to extract simplified DOM: {e}")
            return f"Error extracting DOM: {str(e)}"

    async def get_accessibility_tree(self) -> Dict[str, Any]:
        """Parse the browser's accessibility tree.

        Uses locator-based aria_snapshot() (Playwright >=1.48). Falls back to
        the legacy accessibility.snapshot() for older Playwright builds.
        """
        # Modern API: Playwright >= 1.48 (locator-based aria_snapshot)
        try:
            snapshot = await self.page.locator(":root").aria_snapshot()
            return {"role": "document", "snapshot": snapshot}
        except AttributeError:
            pass  # Method not available on this Playwright version
        except Exception as e:
            logger.warning(f"aria_snapshot() failed: {e}")

        # Legacy API: Playwright < 1.48
        if hasattr(self.page, "accessibility"):
            try:
                tree = await self.page.accessibility.snapshot()
                return tree or {"role": "document", "snapshot": ""}
            except Exception as e:
                logger.error(f"Legacy accessibility.snapshot() also failed: {e}")
                return {"error": str(e)}

        return {"error": "No accessibility API found on this Playwright version"}

    async def get_labeled_screenshot(self) -> str:
        """
        Capture a screenshot with bounding boxes on interactive elements.
        Uses the data-phantom-ref attributes injected by get_simplified_dom.
        """
        # This will be integrated with visual understanding models later
        # For now, just a standard screenshot but with labels available in DOM
        return await self.page.screenshot()

# Intelligent DOM normalization and accessibility tree parsing included above.
