import os
import time
import asyncio
import json
import yaml
import random
import functools
from pathlib import Path
from google import genai
from google.genai.errors import ServerError, ClientError
from dotenv import load_dotenv

def backoff_retry(max_retries=5, base_delay=2.0, max_delay=32.0):
    """Decorator to retry async functions with exponential backoff and jitter."""
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            retries = 0
            while retries < max_retries:
                try:
                    return await func(*args, **kwargs)
                except (ServerError, ClientError) as e:
                    # 503 Service Unavailable or 429 Too Many Requests
                    error_msg = str(e).lower()
                    status_code = getattr(e, 'status_code', None)
                    
                    is_rate_limit = (
                        status_code in [429, 503] or 
                        "503" in error_msg or 
                        "429" in error_msg or 
                        "rate limit" in error_msg or
                        "service unavailable" in error_msg
                    )
                    
                    if not is_rate_limit:
                        raise e
                    
                    retries += 1
                    if retries >= max_retries:
                        print(f"[ERROR] Max retries reached for {func.__name__}. Error: {e}")
                        raise e
                    
                    delay = min(base_delay * (2 ** (retries - 1)) + random.uniform(0, 1), max_delay)
                    print(f"[WARN] Rate limit hit in {func.__name__} (Attempt {retries}/{max_retries}). Retrying in {delay:.2f}s...")
                    await asyncio.sleep(delay)
                except Exception as e:
                    # Non-retriable error
                    raise e
        return wrapper
    return decorator

load_dotenv()

ROOT = Path(__file__).parent.parent
MODELS_JSON = ROOT / "config" / "models.json"
MODELS_YAML = ROOT / "config" / "models.yaml"
PROFILE_YAML = ROOT / "config" / "profiles.yaml"

class ModelManager:
    def __init__(self, model_name: str = None, provider: str = None, role: str = None):
        """
        Initialize ModelManager with flexible model specification.
        
        Args:
            model_name: The model to use (key from models.json or raw name).
            provider: Optional explicit provider ("gemini" or "ollama").
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

        # 🎯 NEW: Support explicit provider specification (from settings)
        if provider:
            self.model_type = provider
            self.text_model_key = model_name or "gemini-2.5-flash"
            
            if provider == "gemini":
                # Gemini: model_name is the actual Gemini model like "gemini-2.5-flash"
                self.model_info = {
                    "type": "gemini",
                    "model": self.text_model_key,
                    "api_key_env": "GEMINI_API_KEY"
                }
                api_key = os.getenv("GEMINI_API_KEY")
                self.client = genai.Client(api_key=api_key)
            elif provider == "ollama":
                # Ollama: model_name is the Ollama model like "phi4" or "llama3:8b"
                self.model_info = {
                    "type": "ollama",
                    "model": self.text_model_key,
                    "url": {
                        "generate": f"{self.ollama_base_url}/api/generate",
                        "chat": f"{self.ollama_base_url}/api/chat"
                    }
                }
                self.client = None  # Ollama uses HTTP, no client needed
            else:
                raise ValueError(f"Unknown provider: {provider}")
        else:
            # 🔄 LEGACY: Lookup in models.json by key
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
            self.config_from_file = True # Flag to indicate this came from models.json

            # Initialize client based on model type
            if self.model_type == "gemini":
                api_key = os.getenv("GEMINI_API_KEY")
                self.client = genai.Client(api_key=api_key)
            # Ollama doesn't need a persistent client

        # 🔒 STRICT MODE ENFORCEMENT
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
            await self._wait_for_rate_limit()
            return await self._gemini_generate_content(contents)
        elif self.model_type == "ollama":
            # Ollama multimodal: extract text and images separately
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
                # Convert PIL Image to base64
                try:
                    img = content
                    # Convert to RGB if necessary
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
                    print(f"[WARN] Failed to encode image for Ollama: {e}")
        
        prompt = "\n".join(text_parts)
        
        if images_base64:
            # Use Ollama's multimodal format with images array
            return await self._ollama_generate_with_images(prompt, images_base64)
        else:
            # Text-only fallback
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
                        "images": images,  # Base64 encoded images
                        "stream": False
                    }
                ) as response:
                    response.raise_for_status()
                    result = await response.json()
                    return result["response"].strip()
        except Exception as e:
            raise RuntimeError(f"Ollama multimodal generation failed: {str(e)}")

    # --- Rate Limiting Helper ---
    _last_call = 0
    _lock = asyncio.Lock()

    async def _wait_for_rate_limit(self):
        """Enforce ~15 RPM limit for Gemini (4s interval)"""
        async with ModelManager._lock:
            now = time.time()
            elapsed = now - ModelManager._last_call
            if elapsed < 4.5: # 4.5s buffer for safety
                sleep_time = 4.5 - elapsed
                # print(f"[Rate Limit] Sleeping for {sleep_time:.2f}s...")
                await asyncio.sleep(sleep_time)
            ModelManager._last_call = time.time()


    @backoff_retry()
    async def _gemini_generate(self, prompt: str) -> str:
        await self._wait_for_rate_limit()
        try:
            # ✅ CORRECT: Use synchronous SDK client in thread to bypass aiohttp/DNS issues common on macOS
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_info["model"],
                contents=prompt
            )
            return response.text.strip()

        except ServerError as e:
            # ✅ FIXED: Raise the exception instead of returning it
            raise e
        except Exception as e:
            # ✅ Handle other potential errors
            raise RuntimeError(f"Gemini generation failed: {str(e)}")

    @backoff_retry()
    async def _gemini_generate_content(self, contents: list) -> str:
        """Generate content with support for text and images using Gemini SDK"""
        try:
            # ✅ Use synchronous SDK client in thread (text + images)
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_info["model"],
                contents=contents
            )
            return response.text.strip()

        except ServerError as e:
            # ✅ FIXED: Raise the exception instead of returning it
            raise e
        except Exception as e:
            # ✅ Handle other potential errors
            raise RuntimeError(f"Gemini content generation failed: {str(e)}")

    async def _ollama_generate(self, prompt: str) -> str:
        try:
            # ✅ Use aiohttp for truly async requests
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
