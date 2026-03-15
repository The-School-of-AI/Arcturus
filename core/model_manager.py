import os
import time
import json
import asyncio
import yaml
from pathlib import Path
from google import genai
from ops.tracing import llm_span
from opentelemetry.trace import Status, StatusCode
from google.genai.errors import ServerError
from dotenv import load_dotenv

from ops.cost import ConfigurableCostCalculator, CostCalculator

load_dotenv()

ROOT = Path(__file__).parent.parent
MODELS_JSON = ROOT / "config" / "models.json"
MODELS_YAML = ROOT / "config" / "models.yaml"
PROFILE_YAML = ROOT / "config" / "profiles.yaml"


def _estimate_tokens(text: str) -> int:
    """Fallback token estimate: ~4 chars per token."""
    return max(0, len(text or "") // 4)


# OpenRouter config
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "google/gemini-2.5-flash-lite-preview-09-2025"

# Map bare Gemini model names to OpenRouter model IDs
GEMINI_TO_OPENROUTER = {
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-2.5-flash-lite": "google/gemini-2.5-flash-lite",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
    "gemini-2.0-flash": "google/gemini-2.0-flash-001",
    "gemini-3.0-flash": "google/gemini-3-flash-preview",
    "gemini-3.0-pro": "google/gemini-3-pro-preview",
}

def _resolve_openrouter_model(model_name: str) -> str:
    """Convert a bare Gemini model name to its OpenRouter equivalent."""
    if model_name.startswith("google/"):
        return model_name  # Already an OpenRouter model ID
    return GEMINI_TO_OPENROUTER.get(model_name, OPENROUTER_DEFAULT_MODEL)

class ModelManager:
    def __init__(
        self,
        model_name: str = None,
        provider: str = None,
        role: str = None,
        cost_calculator: CostCalculator = None,
    ):
        """
        Initialize ModelManager with flexible model specification.

        Args:
            model_name: The model to use (key from models.json or raw name).
            provider: Optional explicit provider ("gemini", "openrouter", or "ollama").
            role: Optional role ("planner", "verifier") from models.yaml.
        """
        self.config = json.loads(MODELS_JSON.read_text())
        self.profile = yaml.safe_load(PROFILE_YAML.read_text())

        # Load Role Config
        if MODELS_YAML.exists():
            self.role_config = yaml.safe_load(MODELS_YAML.read_text())
        else:
            self.role_config = {"roles": {}, "settings": {}}

        # Resolve Role if provided
        if role:
            if role not in self.role_config.get("roles", {}):
                raise ValueError(f"Unknown role: '{role}'. Available: {list(self.role_config.get('roles', {}).keys())}")

            # Override model_name with the one defined for the role
            model_name = self.role_config["roles"][role]
            # Verify explicit provider setting isn't conflicting?
            # We assume role config implies the correct provider via the model definition or name.

        # Load settings for Ollama URL
        try:
            from config.settings_loader import settings
            self.ollama_base_url = settings.get("ollama", {}).get("base_url", "http://127.0.0.1:11434")
        except:
            self.ollama_base_url = "http://127.0.0.1:11434"

        if provider:
            self.text_model_key = model_name or "gemini-2.5-flash"

            if provider == "gemini":
                # Use native Google Gemini API
                self.model_type = "gemini"
                self.model_info = {
                    "type": "gemini",
                    "model": self.text_model_key,
                    "api_key_env": "GEMINI_API_KEY"
                }
                self.client = None
            elif provider == "openrouter":
                # Use OpenRouter API
                self.model_type = "openrouter"
                resolved_model = _resolve_openrouter_model(self.text_model_key)
                self.model_info = {
                    "type": "openrouter",
                    "model": resolved_model,
                    "api_key_env": "OPENROUTER_API_KEY",
                    "base_url": OPENROUTER_BASE_URL
                }
                self.client = None
            elif provider == "ollama":
                self.model_type = "ollama"
                self.model_info = {
                    "type": "ollama",
                    "model": self.text_model_key,
                    "url": {
                        "generate": f"{self.ollama_base_url}/api/generate",
                        "chat": f"{self.ollama_base_url}/api/chat"
                    }
                }
                self.client = None
            else:
                raise ValueError(f"Unknown provider: {provider}")
        else:
            # LEGACY: Lookup in models.json by key
            if model_name:
                self.text_model_key = model_name
            else:
                self.text_model_key = self.profile["llm"]["text_generation"]

            # Validate that the model exists in config
            if self.text_model_key not in self.config["models"]:
                available_models = list(self.config["models"].keys())
                raise ValueError(f"Model '{self.text_model_key}' not found in models.json. Available: {available_models}")

            self.model_info = self.config["models"][self.text_model_key]
            self.model_type = self.model_info["type"]
            self.config_from_file = True

            # Native Gemini type from models.json
            if self.model_type == "gemini":
                self.model_info = {
                    "type": "gemini",
                    "model": self.model_info.get("model", "gemini-2.5-flash"),
                    "api_key_env": self.model_info.get("api_key_env", "GEMINI_API_KEY")
                }
                self.client = None
            elif self.model_type == "openrouter":
                self.client = None
            # Ollama doesn't need a persistent client

        self.cost_calculator = cost_calculator or ConfigurableCostCalculator()

        # STRICT MODE ENFORCEMENT
        if role == "verifier":
            enforce_local = self.role_config.get("settings", {}).get("enforce_local_verifier", False)
            if enforce_local and self.model_type != "ollama":
                raise PermissionError(
                    f"SECURITY VIOLATION: Role 'verifier' is configured to STRICT LOCAL ONLY. "
                    f"Attempted to use provider '{self.model_type}'. "
                    f"Please check config/models.yaml."
                )

    async def generate_text(self, prompt: str) -> str:
        """
        Generate text via Gemini, OpenRouter, or Ollama API.
        WATCHTOWER: Span for each LLM API call.
        - Span name: llm.generate
        - Attributes: model, provider, prompt_length, output_length, cost_usd, input_tokens, output_tokens
        """
        with llm_span(self.text_model_key, self.model_type, len(prompt)) as span:
            try:
                if self.model_type == "gemini":
                    result, input_tokens, output_tokens = await self._gemini_generate(prompt)
                elif self.model_type == "openrouter":
                    result, input_tokens, output_tokens = await self._openrouter_generate(prompt)
                elif self.model_type == "ollama":
                    result, input_tokens, output_tokens = await self._ollama_generate(prompt)
                else:
                    raise NotImplementedError(f"Unsupported model type: {self.model_type}")

                span.set_attribute("prompt", prompt)
                span.set_attribute("output_length", len(result))
                span.set_attribute("output_preview", (result[:1000] if result else ""))
                span.set_attribute("input_tokens", input_tokens)
                span.set_attribute("output_tokens", output_tokens)
                cost_result = self.cost_calculator.compute(
                    input_tokens, output_tokens, self.text_model_key, self.model_type
                )
                span.set_attribute("cost_usd", cost_result.cost_usd)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    async def generate_content(self, contents: list) -> str:
        """
        Generate content with multimodal input (text + images) via Gemini, OpenRouter, or Ollama.
        WATCHTOWER: Span for each LLM API call with multimodal content.
        - Span name: llm.generate
        - Attributes: model, provider, prompt_length, output_length, cost_usd, input_tokens, output_tokens
        """
        prompt_len = sum(len(c) if isinstance(c, str) else 0 for c in contents)
        with llm_span(self.text_model_key, self.model_type, prompt_len) as span:
            try:
                if self.model_type == "gemini":
                    await self._wait_for_rate_limit()
                    result, input_tokens, output_tokens = await self._gemini_generate_content(contents)
                elif self.model_type == "openrouter":
                    result, input_tokens, output_tokens = await self._openrouter_generate_content(contents)
                elif self.model_type == "ollama":
                    result, input_tokens, output_tokens = await self._ollama_generate_content(contents)
                else:
                    raise NotImplementedError(f"Unsupported model type: {self.model_type}")
                span.set_attribute("output_length", len(result))
                span.set_attribute("output_preview", (result[:500] if result else ""))
                span.set_attribute("input_tokens", input_tokens)
                span.set_attribute("output_tokens", output_tokens)
                cost_result = self.cost_calculator.compute(
                    input_tokens, output_tokens, self.text_model_key, self.model_type
                )
                span.set_attribute("cost_usd", cost_result.cost_usd)
                return result
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    async def _ollama_generate_content(self, contents: list) -> tuple[str, int, int]:
        """Generate content with Ollama, supporting multimodal models like gemma3, llava, etc."""
        import base64
        import io
        from PIL import Image as PILImage

        text_parts = []
        images_base64 = []

        for content in contents:
            if isinstance(content, str):
                text_parts.append(content)
            elif hasattr(content, 'save'):  # PIL Image check
                try:
                    img = content
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')

                    # Resize if too large (Ollama has limits)
                    MAX_DIM = 1024
                    if img.width > MAX_DIM or img.height > MAX_DIM:
                        img.thumbnail((MAX_DIM, MAX_DIM), PILImage.Resampling.LANCZOS)

                    # Encode to base64
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    encoded = base64.b64encode(buf.getvalue()).decode("utf-8")
                    images_base64.append(encoded)
                except Exception as e:
                    print(f"⚠️ Failed to encode image for Ollama: {e}")

        prompt = "\n".join(text_parts)

        if images_base64:
            return await self._ollama_generate_with_images(prompt, images_base64)
        else:
            return await self._ollama_generate(prompt)

    async def _ollama_generate_with_images(self, prompt: str, images: list) -> tuple[str, int, int]:
        """Generate with Ollama using images (for multimodal models). Returns (text, input_tokens, output_tokens)."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.model_info["url"]["generate"],
                    json={
                        "model": self.model_info["model"],
                        "prompt": prompt,
                        "images": images,
                        "stream": False
                    }
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    text = result["response"].strip()
                    inp = result.get("prompt_eval_count")
                    out = result.get("eval_count")
                    input_tokens = inp if inp is not None else _estimate_tokens(prompt)
                    output_tokens = out if out is not None else _estimate_tokens(text)
                    return (text, input_tokens, output_tokens)
        except Exception as e:
            raise RuntimeError(f"Ollama multimodal generation failed: {str(e)}")

    # --- Rate Limiting Helper ---
    _last_call = 0
    _lock = asyncio.Lock()

    async def _wait_for_rate_limit(self):
        """Enforce ~15 RPM limit for Gemini (4s interval)"""
        await ModelManager._wait_for_rate_limit_static()

    @staticmethod
    async def _wait_for_rate_limit_static():
        """Class-level rate limiter usable without a ModelManager instance."""
        async with ModelManager._lock:
            now = time.time()
            elapsed = now - ModelManager._last_call
            if elapsed < 4.5: # 4.5s buffer for safety
                sleep_time = 4.5 - elapsed
                # print(f"[Rate Limit] Sleeping for {sleep_time:.2f}s...")
                await asyncio.sleep(sleep_time)
            ModelManager._last_call = time.time()

    async def _gemini_generate(self, prompt: str) -> tuple[str, int, int]:
        """Generate text using the native Google Gemini API. Returns (text, input_tokens, output_tokens)."""
        await self._wait_for_rate_limit()
        try:
            api_key = os.getenv(self.model_info.get("api_key_env", "GEMINI_API_KEY"))
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set in environment")
            client = genai.Client(api_key=api_key)
            response = await client.aio.models.generate_content(
                model=self.model_info["model"],
                contents=prompt
            )
            text = response.text.strip()
            usage = getattr(response, "usage_metadata", None)
            if usage:
                inp = getattr(usage, "prompt_token_count", None) or 0
                out = getattr(usage, "candidates_token_count", None) or 0
            else:
                inp = _estimate_tokens(prompt)
                out = _estimate_tokens(text)
            return (text, inp, out)
        except ServerError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"Gemini generation failed: {str(e)}")

    async def _gemini_generate_content(self, contents: list) -> tuple[str, int, int]:
        """Generate content with native Gemini API, supporting text and images. Returns (text, input_tokens, output_tokens)."""
        try:
            import io
            from google.genai import types

            api_key = os.getenv(self.model_info.get("api_key_env", "GEMINI_API_KEY"))
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set in environment")
            client = genai.Client(api_key=api_key)

            parts = []
            for content in contents:
                if isinstance(content, str):
                    parts.append(types.Part.from_text(text=content))
                elif hasattr(content, 'save'):  # PIL Image
                    img = content
                    if img.mode in ('RGBA', 'P'):
                        img = img.convert('RGB')
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=85)
                    image_bytes = buf.getvalue()
                    parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))

            response = await client.aio.models.generate_content(
                model=self.model_info["model"],
                contents=parts
            )
            text = response.text.strip()
            usage = getattr(response, "usage_metadata", None)
            if usage:
                inp = getattr(usage, "prompt_token_count", None) or 0
                out = getattr(usage, "candidates_token_count", None) or 0
            else:
                inp = _estimate_tokens("".join(str(c) for c in contents) if contents else "")
                out = _estimate_tokens(text)
            return (text, inp, out)
        except ServerError as e:
            raise e
        except Exception as e:
            raise RuntimeError(f"Gemini multimodal generation failed: {str(e)}")

    async def _ollama_generate(self, prompt: str) -> tuple[str, int, int]:
        """Returns (text, input_tokens, output_tokens)."""
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.model_info["url"]["generate"],
                    json={"model": self.model_info["model"], "prompt": prompt, "stream": False},
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    text = result["response"].strip()
                    inp = result.get("prompt_eval_count")
                    out = result.get("eval_count")
                    input_tokens = inp if inp is not None else _estimate_tokens(prompt)
                    output_tokens = out if out is not None else _estimate_tokens(text)
                    return (text, input_tokens, output_tokens)
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {str(e)}")

    async def _openrouter_generate(self, prompt: str) -> tuple[str, int, int]:
        """Generate text using OpenRouter's OpenAI-compatible API. Returns (text, input_tokens, output_tokens)."""
        try:
            import aiohttp
            api_key = os.getenv(self.model_info.get("api_key_env", "OPENROUTER_API_KEY"))
            base_url = self.model_info.get("base_url", OPENROUTER_BASE_URL)

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model_info["model"],
                        "messages": [{"role": "user", "content": prompt}],
                    }
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    text = result["choices"][0]["message"]["content"].strip()
                    usage = result.get("usage", {})
                    input_tokens = usage.get("prompt_tokens", _estimate_tokens(prompt))
                    output_tokens = usage.get("completion_tokens", _estimate_tokens(text))
                    return (text, input_tokens, output_tokens)
        except Exception as e:
            raise RuntimeError(f"OpenRouter generation failed: {str(e)}")

    async def _openrouter_generate_content(self, contents: list) -> tuple[str, int, int]:
        """Generate content with OpenRouter, extracting text from multimodal inputs. Returns (text, input_tokens, output_tokens)."""
        text_parts = []
        for content in contents:
            if isinstance(content, str):
                text_parts.append(content)
        prompt = "\n".join(text_parts)
        return await self._openrouter_generate(prompt)
