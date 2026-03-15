"""Shared AI image generation for Forge exports using Gemini."""

import asyncio
import io
import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types as genai_types
from PIL import Image

from core.model_manager import ModelManager

load_dotenv()

logger = logging.getLogger(__name__)

_IMAGE_PROMPT = (
    "Generate a professional, clean presentation image for: {description}. "
    "Style: modern, minimal, no text or labels or watermarks. "
    "Composition: wide landscape, subject centered, mood and setting clearly conveyed."
)

_MODELS_JSON = Path(__file__).parent.parent.parent / "config" / "models.json"

_client = None


def _get_image_model() -> str:
    """Resolve the image generation model from config/models.json."""
    config = json.loads(_MODELS_JSON.read_text())
    key = config.get("defaults", {}).get("image_generation", "gemini-image")
    model_info = config.get("models", {}).get(key, {})
    return model_info.get("model", "gemini-3.1-flash-image-preview")


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    return _client


async def generate_single_image(description: str) -> io.BytesIO | None:
    """Call Gemini to generate a single image, returning JPEG bytes or None."""
    await ModelManager._wait_for_rate_limit_static()

    try:
        client = _get_client()
        prompt = _IMAGE_PROMPT.format(description=description)

        response = await asyncio.to_thread(
            client.models.generate_content,
            model=_get_image_model(),
            contents=prompt,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE"],
                image_config=genai_types.ImageConfig(
                    aspect_ratio="16:9",
                    image_size="512",
                ),
            ),
        )

        # Extract image from response parts
        for part in response.parts:
            if part.inline_data is not None:
                img = Image.open(io.BytesIO(part.inline_data.data))

                # Convert to RGB JPEG for smaller file size
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")

                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=85)
                buf.seek(0)
                return buf

        logger.warning("No image data in Gemini response for: %s", description[:80])
        return None

    except Exception as e:
        logger.warning("Image generation failed for '%s': %s", description[:80], e)
        return None
