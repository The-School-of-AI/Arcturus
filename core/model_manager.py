import os
import json
import yaml
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
MODELS_JSON = ROOT / "config" / "models.json"
MODELS_YAML = ROOT / "config" / "models.yaml"
PROFILE_YAML = ROOT / "config" / "profiles.yaml"

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
    def __init__(self, model_name: str = None, provider: str = None, role: str = None):
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

            model_name = self.role_config["roles"][role]

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
        if self.model_type == "gemini":
            return await self._gemini_generate(prompt)
        elif self.model_type == "openrouter":
            return await self._openrouter_generate(prompt)
        elif self.model_type == "ollama":
            return await self._ollama_generate(prompt)

        raise NotImplementedError(f"Unsupported model type: {self.model_type}")

    async def generate_content(self, contents: list) -> str:
        """Generate content with support for text and images.

        Contents can contain:
        - str: Text content
        - PIL.Image: Image to process (will be base64-encoded for Ollama)
        """
        if self.model_type == "gemini":
            return await self._gemini_generate_content(contents)
        elif self.model_type == "openrouter":
            return await self._openrouter_generate_content(contents)
        elif self.model_type == "ollama":
            return await self._ollama_generate_content(contents)

        raise NotImplementedError(f"Unsupported model type: {self.model_type}")

    async def _ollama_generate_content(self, contents: list) -> str:
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

                    MAX_DIM = 1024
                    if img.width > MAX_DIM or img.height > MAX_DIM:
                        img.thumbnail((MAX_DIM, MAX_DIM), PILImage.Resampling.LANCZOS)

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

    async def _ollama_generate_with_images(self, prompt: str, images: list) -> str:
        """Generate with Ollama using images (for multimodal models)."""
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
                    return result["response"].strip()
        except Exception as e:
            raise RuntimeError(f"Ollama multimodal generation failed: {str(e)}")

    async def _ollama_generate(self, prompt: str) -> str:
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.model_info["url"]["generate"],
                    json = {"model": self.model_info["model"], "prompt": prompt, "stream": False}
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result["response"].strip()
        except Exception as e:
            raise RuntimeError(f"Ollama generation failed: {str(e)}")

    async def _openrouter_generate(self, prompt: str) -> str:
        """Generate text using OpenRouter's OpenAI-compatible API."""
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
                    return result["choices"][0]["message"]["content"].strip()
        except Exception as e:
            raise RuntimeError(f"OpenRouter generation failed: {str(e)}")

    async def _openrouter_generate_content(self, contents: list) -> str:
        """Generate content with OpenRouter, extracting text from multimodal inputs."""
        text_parts = []
        for content in contents:
            if isinstance(content, str):
                text_parts.append(content)
        prompt = "\n".join(text_parts)
        return await self._openrouter_generate(prompt)

    async def _gemini_generate(self, prompt: str) -> str:
        """Generate text using the native Google Gemini API."""
        try:
            from google import genai
            api_key = os.getenv(self.model_info.get("api_key_env", "GEMINI_API_KEY"))
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY not set in environment")
            client = genai.Client(api_key=api_key)
            response = await client.aio.models.generate_content(
                model=self.model_info["model"],
                contents=prompt
            )
            return response.text.strip()
        except Exception as e:
            raise RuntimeError(f"Gemini generation failed: {str(e)}")

    async def _gemini_generate_content(self, contents: list) -> str:
        """Generate content with native Gemini API, supporting text and images."""
        try:
            import base64
            import io
            from google import genai
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
            return response.text.strip()
        except Exception as e:
            raise RuntimeError(f"Gemini multimodal generation failed: {str(e)}")
