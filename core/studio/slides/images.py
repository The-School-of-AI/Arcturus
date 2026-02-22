"""AI image generation for Forge slide exports using Gemini."""

import asyncio
import io
import logging
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from PIL import Image

from core.model_manager import ModelManager

load_dotenv()
from core.schemas.studio_schema import SlidesContentTree

logger = logging.getLogger(__name__)

_IMAGE_PROMPT = (
    "Generate a professional, clean 16:9 wide-format presentation image for: {description}. "
    "Style: modern, minimal, no text or labels or watermarks. "
    "Composition: wide landscape, subject centered, mood and setting clearly conveyed."
)

_SEMAPHORE_LIMIT = 3  # ~13 RPM stays under 15 RPM limit

_client = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


async def generate_slide_images(
    content_tree: SlidesContentTree,
) -> dict[str, io.BytesIO]:
    """Scan content_tree for image_text slides and generate images in parallel.

    Returns a dict mapping slide ID to JPEG BytesIO buffers.
    Only slides with successful generation are included; failures are silently
    skipped (the exporter falls back to text placeholders).
    """
    tasks: list[tuple[str, str]] = []
    for slide in content_tree.slides:
        if slide.slide_type not in ("image_text", "image_full"):
            continue
        for el in slide.elements:
            if el.type == "image" and el.content and isinstance(el.content, str):
                tasks.append((slide.id, el.content))
                break

    if not tasks:
        return {}

    sem = asyncio.Semaphore(_SEMAPHORE_LIMIT)

    async def _bounded(slide_id: str, desc: str) -> tuple[str, io.BytesIO | None]:
        async with sem:
            buf = await _generate_single_image(desc)
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


def _crop_to_16_9(img: Image.Image) -> Image.Image:
    """Center-crop an image to 16:9 aspect ratio."""
    w, h = img.size
    target_ratio = 16 / 9
    current_ratio = w / h

    if abs(current_ratio - target_ratio) < 0.01:
        return img  # Already 16:9

    if current_ratio > target_ratio:
        # Too wide — crop sides
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        return img.crop((left, 0, left + new_w, h))
    else:
        # Too tall — crop top/bottom
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        return img.crop((0, top, w, top + new_h))


async def _generate_single_image(description: str) -> io.BytesIO | None:
    """Call Gemini to generate a single image, returning JPEG bytes or None."""
    await ModelManager._wait_for_rate_limit_static()

    try:
        client = _get_client()
        prompt = _IMAGE_PROMPT.format(description=description)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model="gemini-2.5-flash-image",
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE"],
            ),
        )

        # Extract image from response parts
        for part in response.candidates[0].content.parts:
            if part.inline_data is not None:
                raw_bytes = part.inline_data.data
                img = Image.open(io.BytesIO(raw_bytes))

                # Convert to RGB JPEG for smaller file size
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")

                # Center-crop to 16:9 aspect ratio
                img = _crop_to_16_9(img)

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                return buf

        logger.warning("No image data in Gemini response for: %s", description[:80])
        return None

    except Exception as e:
        logger.warning("Image generation failed for '%s': %s", description[:80], e)
        return None
