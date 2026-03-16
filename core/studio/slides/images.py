"""AI image generation for Forge slide exports using Gemini."""

import asyncio
import io
import json
import logging

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
