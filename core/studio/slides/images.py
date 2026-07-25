"""Image resolution for Forge slides: web search (DuckDuckGo) + AI fallback."""

import asyncio
import io
import json
import logging
import re
from typing import Any, Dict

from core.schemas.studio_schema import SlidesContentTree
from core.studio.images import generate_single_image

logger = logging.getLogger(__name__)

_SEMAPHORE_LIMIT = 3  # ~13 RPM stays under 15 RPM limit


def _extract_image_info(element_content) -> tuple[str | None, str | None]:
    """Extract URL and description from an image element's content.

    Returns (url_or_none, description_or_none).
    Content can be:
      - A plain string description (legacy)
      - A dict {"url": "...", "alt": "..."} (new format with external URL)
      - A dict {"alt": "..."} (new format without URL, for AI generation)
      - A JSON string encoding either of the above
    """
    if not element_content:
        return None, None

    if isinstance(element_content, dict):
        return element_content.get("url"), element_content.get("alt") or element_content.get("description")

    if isinstance(element_content, str):
        # Check if it's a URL directly
        if element_content.startswith(("http://", "https://")):
            return element_content, None

        # Try parsing as JSON
        try:
            parsed = json.loads(element_content)
            if isinstance(parsed, dict):
                return parsed.get("url"), parsed.get("alt") or parsed.get("description")
        except (json.JSONDecodeError, TypeError):
            pass

        # Plain description string
        return None, element_content

    return None, None


def extract_image_url(element_content) -> str | None:
    """Extract external image URL from element content, if present."""
    url, _ = _extract_image_info(element_content)
    return url


async def generate_slide_images(
    content_tree: SlidesContentTree,
) -> dict[str, io.BytesIO]:
    """Scan content_tree for image_text slides and generate images in parallel.

    Slides with external URLs are skipped (rendered directly by the frontend).
    Only slides with text descriptions (no URL) trigger AI image generation.

    Returns a dict mapping slide ID to JPEG BytesIO buffers.
    Only slides with successful generation are included; failures are silently
    skipped (the exporter falls back to text placeholders).
    """
    tasks: list[tuple[str, str]] = []
    for slide in content_tree.slides:
        if slide.slide_type not in ("image_text", "image_full"):
            continue
        for el in slide.elements:
            if el.type == "image" and el.content:
                url, desc = _extract_image_info(el.content)
                if url:
                    # Has external URL — skip AI generation
                    logger.info("Slide %s has external image URL, skipping generation", slide.id)
                elif desc:
                    # No URL, has description — generate with AI
                    tasks.append((slide.id, desc))
                break

    if not tasks:
        return {}

    sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)

    async def _bounded(slide_id: str, desc: str) -> tuple[str, io.BytesIO | None]:
        async with sem:
            buf = await generate_single_image(desc)
            return slide_id, buf

    results = await asyncio.gather(
        *[_bounded(sid, desc) for sid, desc in tasks],
        return_exceptions=True,
    )

    images: dict[str, io.BytesIO] = {}
    for r in results:
        if isinstance(r, Exception):
            logger.warning("Image generation task failed: %s", r)
            continue
        slide_id, buf = r
        if buf is not None:
            images[slide_id] = buf

    logger.info("Generated %d/%d slide images", len(images), len(tasks))
    return images


# --- HTML image placeholder resolution ---

# Regex to find <img ... data-placeholder="true" ... > tags in HTML
_IMG_PLACEHOLDER_RE = re.compile(
    r'<img\b[^>]*data-placeholder\s*=\s*["\']true["\'][^>]*>',
    re.IGNORECASE,
)

# Extract alt text from an <img> tag
_ALT_RE = re.compile(r'alt\s*=\s*["\']([^"\']*)["\']', re.IGNORECASE)


def _extract_html_placeholders(html: str) -> list[tuple[str, str]]:
    """Find all placeholder <img> tags in HTML.

    Returns list of (full_match, alt_text) tuples.
    """
    results = []
    for match in _IMG_PLACEHOLDER_RE.finditer(html):
        tag = match.group(0)
        alt_match = _ALT_RE.search(tag)
        alt_text = alt_match.group(1) if alt_match else ""
        if alt_text:
            results.append((tag, alt_text))
    return results


# Domains that block hotlinking / require auth — skip these in image search
_BLOCKED_IMAGE_DOMAINS = {
    "shutterstock.com", "gettyimages.com", "istockphoto.com",
    "alamy.com", "dreamstime.com", "depositphotos.com",
    "123rf.com", "stock.adobe.com", "adobestock.com",
    "freepik.com",
}


def _is_embeddable_url(url: str) -> bool:
    """Check if the image URL is from a domain that allows hotlinking."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        # Check against blocked domains (match suffix for subdomains)
        return not any(host == d or host.endswith("." + d) for d in _BLOCKED_IMAGE_DOMAINS)
    except Exception:
        return True


async def _search_image_url(query: str) -> str | None:
    """Search the web for an embeddable image URL using DuckDuckGo image search.

    Skips stock photo sites that block hotlinking.
    Validates the URL returns an actual image via HEAD request.
    Returns a direct image URL (jpg/png/webp) or None.
    """
    try:
        import re
        import urllib.parse
        import httpx

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) "
                "AppleWebKit/537.36 Chrome/113.0.5672.92 Safari/537.36"
            ),
            "Referer": "https://duckduckgo.com/",
        }

        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=headers) as client:
            # Step 1: Get vqd token from DuckDuckGo
            token_url = (
                f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
                "&iax=images&ia=images"
            )
            r = await client.get(token_url, headers=headers)
            vqd_match = re.search(r'vqd="([^"]+)"', r.text) or re.search(
                r"vqd=([^&\"]+)", r.text
            )
            if not vqd_match:
                logger.debug("No vqd token for image search: %r", query)
                return None

            vqd = vqd_match.group(1)

            # Step 2: Query the image API
            img_api = (
                f"https://duckduckgo.com/i.js?l=wt-wt&o=json"
                f"&q={urllib.parse.quote(query)}&vqd={vqd}&f=,,,,,&p=1"
            )
            r2 = await client.get(img_api, headers=headers)
            data = r2.json()

            # Step 3: Pick the best embeddable image URL
            for item in data.get("results", [])[:20]:
                url = item.get("image", "")
                if not url:
                    continue
                # Skip stock photo sites that block hotlinking
                if not _is_embeddable_url(url):
                    continue
                # Prefer URLs with image extensions
                if any(ext in url.lower() for ext in (".jpg", ".jpeg", ".png", ".webp")):
                    # Quick HEAD check to verify the URL actually serves an image
                    try:
                        head = await client.head(url, timeout=5)
                        ct = head.headers.get("content-type", "")
                        if head.status_code == 200 and "image" in ct:
                            return url
                    except Exception:
                        continue

            # Fallback: try any result that passes the embeddable check
            for item in data.get("results", [])[:20]:
                url = item.get("image", "")
                if url and _is_embeddable_url(url):
                    try:
                        head = await client.head(url, timeout=5)
                        ct = head.headers.get("content-type", "")
                        if head.status_code == 200 and "image" in ct:
                            return url
                    except Exception:
                        continue

        return None
    except Exception as e:
        logger.debug("Image search failed for %r: %s", query, e)
        return None


async def _resolve_single_placeholder(
    alt_text: str,
    sem: asyncio.Semaphore,
) -> str | None:
    """Search the web for a real image matching the alt text.

    Returns an image URL string, or None if no image found.
    No AI generation fallback — we only use real images from the web.
    """
    async with sem:
        url = await _search_image_url(alt_text)
        if url:
            logger.info("Found image for %r: %s", alt_text[:60], url[:100])
            return url

        logger.info("No image found for %r", alt_text[:60])
        return None


async def resolve_html_images(content_tree_dict: Dict[str, Any]) -> bool:
    """Resolve <img data-placeholder="true"> tags in slide HTML fields.

    Mutates content_tree_dict in-place: replaces placeholder <img> tags with
    ones that have real src URLs from web image search.

    Returns True if any placeholders were resolved.
    """
    slides = content_tree_dict.get("slides", [])
    # Collect all placeholders across all slides
    tasks: list[tuple[int, str, str]] = []  # (slide_idx, original_tag, alt_text)
    for i, slide in enumerate(slides):
        html = slide.get("html")
        if not html:
            continue
        for tag, alt_text in _extract_html_placeholders(html):
            tasks.append((i, tag, alt_text))

    if not tasks:
        return False

    logger.info("Resolving %d HTML image placeholders", len(tasks))

    sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)
    resolve_results = await asyncio.gather(
        *[_resolve_single_placeholder(alt, sem) for _, _, alt in tasks],
        return_exceptions=True,
    )

    resolved_count = 0
    for (slide_idx, original_tag, alt_text), result in zip(tasks, resolve_results):
        if isinstance(result, Exception):
            logger.warning("Placeholder resolution failed for %r: %s", alt_text, result)
            continue
        if result is None:
            continue

        # Build replacement tag with src, remove data-placeholder
        new_tag = original_tag.replace('data-placeholder="true"', '').replace("data-placeholder='true'", '')
        # Insert src attribute
        new_tag = new_tag.replace("<img", f'<img src="{result}"', 1)
        slides[slide_idx]["html"] = slides[slide_idx]["html"].replace(original_tag, new_tag, 1)
        resolved_count += 1

    logger.info("Resolved %d/%d HTML image placeholders", resolved_count, len(tasks))
    return resolved_count > 0
