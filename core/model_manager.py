import os
import time
import asyncio
import json
import yaml
from pathlib import Path
from google import genai
from google.genai.errors import ServerError
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
MODELS_JSON = ROOT / "config" / "models.json"
PROFILE_YAML = ROOT / "config" / "profiles.yaml"

class ModelManager:
    def __init__(self, model_name: str = None):
        self.config = json.loads(MODELS_JSON.read_text())
        self.profile = yaml.safe_load(PROFILE_YAML.read_text())

        # 🎯 NEW: Use provided model_name or fall back to profile default
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

        # Initialize client based on model type
        if self.model_type == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            self.client = genai.Client(api_key=api_key)
        # Add other model types as needed

    async def generate_text(self, prompt: str) -> str:
        if self.model_type == "gemini":
            return await self._gemini_generate(prompt)

        elif self.model_type == "ollama":
            return await self._ollama_generate(prompt)

        raise NotImplementedError(f"Unsupported model type: {self.model_type}")

    async def generate_content(self, contents: list) -> str:
        """Generate content with support for text and images"""
        if self.model_type == "gemini":
            await self._wait_for_rate_limit()
            return await self._gemini_generate_content(contents)
        elif self.model_type == "ollama":
            # Ollama doesn't support images, fall back to text-only
            text_content = ""
            for content in contents:
                if isinstance(content, str):
                    text_content += content
            return await self._ollama_generate(text_content)
        
        raise NotImplementedError(f"Unsupported model type: {self.model_type}")

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
