from playwright.async_api import Page, ElementHandle
import json
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("phantom-extractor")

import json
import logging
import os
import time
from typing import List, Dict, Any, Optional
from playwright.async_api import Page, ElementHandle
import trafilatura
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("phantom-extractor")

class PageExtractor:
    """
    Intelligent content extraction and DOM normalization.
    Converts complex web pages into simplified, LLM-friendly representations.
    Inspired by OpenClaw: uses accessibility roles and aria-refs.
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.last_elements = [] # Cache elements from the last extraction for annotation

    async def get_simplified_dom(self) -> str:
        """
        Produce a normalized DOM representation.
        Strips irrelevant elements and labels interactive components.
        Refined for token efficiency.
        """
        extract_script = """
        () => {
            const interactiveElements = [];
            const semanticElements = [];
            
            // Collect interactive elements
            const interactiveSelectors = 'button, input, select, textarea, a, [role="button"], [role="link"], [role="checkbox"], [tabindex="0"]';
            const iElements = document.querySelectorAll(interactiveSelectors);
            
            iElements.forEach((el, index) => {
                const rect = el.getBoundingClientRect();
                const style = window.getComputedStyle(el);
                if (rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none') {
                    const ref = `e${index}`;
                    el.setAttribute('data-phantom-ref', ref);
                    
                    interactiveElements.push({
                        ref: ref,
                        tag: el.tagName.toLowerCase(),
                        role: el.getAttribute('role') || el.type || el.tagName.toLowerCase(),
                        text: (el.innerText || el.placeholder || el.ariaLabel || el.title || "").trim().substring(0, 100),
                        rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
                    });
                }
            });

            // Collect semantic context (headings)
            const headings = document.querySelectorAll('h1, h2, h3');
            headings.forEach(h => {
                semanticElements.push({
                    tag: h.tagName.toLowerCase(),
                    text: h.innerText.trim()
                });
            });

            return { interactive: interactiveElements, semantic: semanticElements };
        }
        """
        try:
            result = await self.page.evaluate(extract_script)
            self.last_elements = result.get("interactive", [])
            semantic_elements = result.get("semantic", [])
            
            # Build text representation (Normalized DOM 2.0)
            lines = ["# Interactive Elements:"]
            for el in self.last_elements:
                lines.append(f"[ref={el['ref']}] {el['role']}: {el['text']}")
            
            # Add semantic headings for context
            if semantic_elements:
                lines.append("\n# Page headings:")
                for h in semantic_elements:
                    lines.append(f"<{h['tag']}> {h['text']}")
            
            # Add a summary of the main content
            main_text = await self.extract_structured_data()
            if main_text:
                lines.append("\n# Page Content Summary:")
                lines.append(main_text[:2000] + "..." if len(main_text) > 2000 else main_text)
            
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Failed to extract simplified DOM: {e}")
            return f"Error extracting DOM: {str(e)}"

    async def extract_structured_data(self) -> str:
        """
        Smart extraction of article text, tables, and lists using Trafilatura.
        """
        try:
            content = await self.page.content()
            # extract() returns the main text of the page
            downloaded = trafilatura.extract(content, include_tables=True, include_links=True)
            return downloaded or ""
        except Exception as e:
            logger.error(f"Structured extraction failed: {e}")
            return ""

    async def get_accessibility_tree(self) -> Dict[str, Any]:
        """Parse the browser's accessibility tree."""
        try:
            # Modern API: Playwright >= 1.48
            try:
                snapshot = await self.page.locator(":root").aria_snapshot()
                return {"role": "document", "snapshot": snapshot}
            except:
                pass

            # Legacy API
            if hasattr(self.page, "accessibility"):
                tree = await self.page.accessibility.snapshot()
                return tree or {"role": "document", "snapshot": ""}
                
        except Exception as e:
            logger.error(f"Failed to get accessibility tree: {e}")
            
        return {"error": "No accessibility API available"}

    async def get_labeled_screenshot(self, output_path: Optional[str] = None) -> str:
        """
        Capture a screenshot and draw bounding boxes on interactive elements.
        Uses cached elements from the last get_simplified_dom call.
        """
        if not output_path:
            output_path = os.path.join(os.getcwd(), "data", "screenshots", f"labeled_{int(time.time())}.png")
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Take base screenshot
        temp_ss = output_path + ".temp.png"
        await self.page.screenshot(path=temp_ss)
        
        try:
            with Image.open(temp_ss) as img:
                draw = ImageDraw.Draw(img)
                # Try to load a font, fallback to default
                try:
                    font = ImageFont.truetype("Arial.ttf", 14)
                except:
                    font = ImageFont.load_default()
                
                for el in self.last_elements:
                    rect = el['rect']
                    # Draw red bounding box
                    draw.rectangle(
                        [rect['x'], rect['y'], rect['x'] + rect['width'], rect['y'] + rect['height']],
                        outline="red", width=2
                    )
                    # Label with the reference index
                    draw.text((rect['x'], rect['y'] - 15), el['ref'], fill="red", font=font)
                
                img.save(output_path)
            
            os.remove(temp_ss)
            logger.info(f"Labeled screenshot saved to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Failed to label screenshot: {e}")
            if os.path.exists(temp_ss):
                os.rename(temp_ss, output_path)
            return output_path


# Intelligent DOM normalization and accessibility tree parsing included above.
