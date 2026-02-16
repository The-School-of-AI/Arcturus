
import os
import json
import re
import time
import yaml
from pathlib import Path
from typing import Optional, Dict, Any

class AppGenerator:
    def __init__(self, project_root: Path = None):
        if project_root is None:
            # Try to resolve project root dynamically
            # Assuming we are in core/generator.py -> ..
            self.project_root = Path(__file__).parent.parent
        else:
            self.project_root = project_root
            
        self.apps_dir = self.project_root / "apps"
        self.prompts_dir = self.project_root / "prompts"
        self.config_dir = self.project_root / "config"
        
        # Ensure directories exist
        self.apps_dir.mkdir(exist_ok=True)

    def _get_model_config(self, key: str = "text_generation") -> str:
        try:
            profile = yaml.safe_load((self.config_dir / "profiles.yaml").read_text())
            models_config = json.loads((self.config_dir / "models.json").read_text())
            
            model_key = profile.get("llm", {}).get(key, "gemini")
            model_info = models_config.get("models", {}).get(model_key, {})
            return model_info.get("model", "gemini-2.5-flash")
        except:
            return "gemini-2.5-flash"

    async def generate_frontend(self, prompt: str, model_override: Optional[str] = None) -> Dict[str, Any]:
        """Generate UI JSON configuration."""
        print(f"[Generator] Generating Frontend for: {prompt[:50]}...")
        
        # Load prompt from Skill
        try:
            from core.skills.library.appgenerationprompt.skill import AppgenerationpromptSkill
            skill = AppgenerationpromptSkill()
            # The prompt expects {{USER_REQUEST}}, but the code was using {{USER_PROMPT}}
            # Let's align with the skill's template
            generation_prompt = skill.prompt_text.replace("{{USER_REQUEST}}", prompt)
            generation_prompt = generation_prompt.replace("{{USER_PROMPT}}", prompt) # Handle both just in case
        except ImportError:
             raise ImportError("AppgenerationpromptSkill not found. Ensure core.skills.library.appgenerationprompt is available.")

        
        # Start AI
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        model = model_override or self._get_model_config()
        
        # Call Gemini
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        
        response = client.models.generate_content(
            model=model,
            contents=generation_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.3
            )
        )
        
        try:
            return self._extract_json(response.text)
        except Exception as e:
            print(f"[Generator] JSON Extract failed: {e}")
            raise

    async def generate_backend(self, prompt: str, frontend_spec: Dict[str, Any], model_override: Optional[str] = None) -> str:
        """Generate Python backend code."""
        print(f"[Generator] Generating Backend...")
        
        # Load prompt
        prompt_file = self.prompts_dir / "BackendGenerationPrompt.md"
        if not prompt_file.exists():
            # Fallback simple prompt
            generation_prompt = f"Create a FastAPI router for this app:\nUser Prompt: {prompt}\nSpec: {json.dumps(frontend_spec)}"
        else:
            generation_prompt = prompt_file.read_text()
            generation_prompt = generation_prompt.replace("{{USER_PROMPT}}", prompt)
            generation_prompt = generation_prompt.replace("{{FRONTEND_SPEC}}", json.dumps(frontend_spec, indent=2))
            
        # Start AI
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        model = model_override or self._get_model_config()
        
        response = client.models.generate_content(
            model=model,
            contents=generation_prompt,
            config=types.GenerateContentConfig(temperature=0.2)
        )
        
        return self._extract_code(response.text)

    async def generate_app(self, name: str, prompt: str, model_override: Optional[str] = None) -> Dict[str, Any]:
        """Orchestrate full app generation."""
        app_id = f"app-{int(time.time() * 1000)}"
        app_folder = self.apps_dir / app_id
        app_folder.mkdir(exist_ok=True)
        
        print(f"[Generator] Creating app {app_id} ({name})")
        
        # 1. Frontend
        frontend_data = await self.generate_frontend(prompt, model_override)
        
        # Enrich metadata
        frontend_data["id"] = app_id
        frontend_data["name"] = name
        frontend_data["description"] = prompt[:200]
        frontend_data["lastModified"] = int(time.time() * 1000)
        
        # Save Frontend
        (app_folder / "ui.json").write_text(json.dumps(frontend_data, indent=2))
        
        # 2. Backend
        backend_code = await self.generate_backend(prompt, frontend_data, model_override)
        (app_folder / "backend.py").write_text(backend_code)
        
        print(f"[Generator] App {app_id} created successfully.")
        return {
            "id": app_id,
            "path": str(app_folder),
            "frontend": frontend_data,
            "backend_files": ["backend.py"]
        }

    def _extract_json(self, text: str) -> Dict[str, Any]:
        """Robust JSON extraction."""
        text = text.strip()
        match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
        if match:
            text = match.group(1).strip()
        else:
            idx = text.find('{')
            if idx >= 0:
                text = text[idx:]
        return json.loads(text)

    def _extract_code(self, text: str) -> str:
        """Extract code from markdown."""
        match = re.search(r'```(?:python)?\s*\n(.*?)\n```', text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text # Fallback return all text
