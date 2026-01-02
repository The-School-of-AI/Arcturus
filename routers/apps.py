# Apps Router - Handles app CRUD, generation, and hydration
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from shared.state import PROJECT_ROOT

router = APIRouter(prefix="/apps", tags=["Apps"])


# === Pydantic Models ===

class CreateAppRequest(BaseModel):
    name: str
    description: Optional[str] = ""
    cards: List[dict] = []
    layout: List[dict] = []


class SaveAppRequest(BaseModel):
    id: str
    name: str
    description: Optional[str] = ""
    cards: List[dict]
    layout: List[dict]
    lastModified: int
    lastHydrated: Optional[int] = None  # Timestamp of last AI data refresh


class GenerateAppRequest(BaseModel):
    name: str
    prompt: str
    model: Optional[str] = None


class HydrateRequest(BaseModel):
    model: Optional[str] = None  # Override model if needed
    user_prompt: Optional[str] = None  # User's preferences/instructions for data refresh


# === Endpoints ===

@router.get("")
async def list_apps():
    """List all saved apps from apps/ directory"""
    try:
        apps_dir = PROJECT_ROOT / "apps"
        if not apps_dir.exists():
            return []
        
        apps = []
        for app_folder in apps_dir.iterdir():
            if app_folder.is_dir():
                ui_file = app_folder / "ui.json"
                if ui_file.exists():
                    try:
                        data = json.loads(ui_file.read_text())
                        apps.append({
                            "id": app_folder.name,
                            "name": data.get("name", "Untitled App"),
                            "description": data.get("description", ""),
                            "lastModified": data.get("lastModified", 0)
                        })
                    except:
                        continue
        # Sort by recently modified
        return sorted(apps, key=lambda x: x['lastModified'], reverse=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{app_id}")
async def get_app(app_id: str):
    """Get full app configuration"""
    try:
        ui_file = PROJECT_ROOT / "apps" / app_id / "ui.json"
        if not ui_file.exists():
            raise HTTPException(status_code=404, detail="App not found")
        
        return json.loads(ui_file.read_text())
    except Exception as e:
        # Re-raise HTTP exceptions, wrap others
        if isinstance(e, HTTPException): raise e
        raise HTTPException(status_code=500, detail=str(e))


@router.post("")
async def create_app(request: CreateAppRequest):
    """Create or Update an app"""
    # This is mostly a placeholder - the /apps/save endpoint is more commonly used
    pass


@router.post("/save")
async def save_app_endpoint(request: SaveAppRequest):
    try:
        apps_dir = PROJECT_ROOT / "apps"
        apps_dir.mkdir(exist_ok=True)
        
        app_folder = apps_dir / request.id
        app_folder.mkdir(exist_ok=True)
        
        ui_file = app_folder / "ui.json"
        data = request.dict()
        
        ui_file.write_text(json.dumps(data, indent=2))
        return {"status": "success", "id": request.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{app_id}")
async def delete_app(app_id: str):
    try:
        app_folder = PROJECT_ROOT / "apps" / app_id
        if app_folder.exists():
            shutil.rmtree(app_folder)
        return {"status": "success", "id": app_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/generate")
async def generate_app(request: GenerateAppRequest):
    """Generate a new app using AI based on user prompt."""
    import yaml
    try:
        print(f"[Generate] Starting app generation: {request.name}")
        print(f"[Generate] User prompt: {request.prompt[:100]}...")
        
        # Load generation prompt
        prompt_file = PROJECT_ROOT / "prompts" / "AppGenerationPrompt.md"

        if not prompt_file.exists():
            raise HTTPException(status_code=500, detail="App generation prompt not found")
        
        generation_prompt = prompt_file.read_text()
        generation_prompt = generation_prompt.replace("{{USER_PROMPT}}", request.prompt)
        print(f"[Generate] Prompt prepared, length: {len(generation_prompt)} chars")
        
        # Get model from settings (same as agents)
        config_dir = PROJECT_ROOT / "config"
        profile = yaml.safe_load((config_dir / "profiles.yaml").read_text())
        models_config = json.loads((config_dir / "models.json").read_text())
        
        model_key = profile.get("llm", {}).get("text_generation", "gemini")
        model_info = models_config.get("models", {}).get(model_key, {})
        model = model_info.get("model", "gemini-2.0-flash")
        
        # Allow request override
        if request.model:
            model = request.model
        print(f"[Generate] Using model: {model} (from config key: {model_key})")
        
        # Call Gemini for generation with Google Search enabled
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Enable Google Search for real-time data
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        
        print("[Generate] Calling Gemini with Google Search enabled...")
        response = client.models.generate_content(
            model=model,
            contents=generation_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.3  # Slightly higher for creativity in layout
            )
        )
        response_text = response.text.strip()
        print(f"[Generate] Got response, length: {len(response_text)} chars")
        
        # Clean up response - extract JSON from markdown fences or explanatory text
        # Try to find JSON within markdown code fences
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1).strip()
            print("[Generate] Extracted JSON from markdown fences")
        else:
            # Try to find JSON by looking for the opening brace
            json_start = response_text.find('{')
            if json_start > 0:
                response_text = response_text[json_start:].strip()
                print(f"[Generate] Trimmed explanatory text, JSON starts at char {json_start}")
        
        # Parse the generated JSON
        generated_data = json.loads(response_text)
        print(f"[Generate] Parsed JSON successfully, {len(generated_data.get('cards', []))} cards")
        
        # Create app ID and folder
        app_id = f"app-{int(time.time() * 1000)}"
        apps_dir = PROJECT_ROOT / "apps"
        apps_dir.mkdir(exist_ok=True)
        
        app_folder = apps_dir / app_id
        app_folder.mkdir(exist_ok=True)
        
        # Add metadata
        generated_data["id"] = app_id
        generated_data["name"] = request.name
        generated_data["description"] = request.prompt[:200]  # First 200 chars as description
        generated_data["lastModified"] = int(time.time() * 1000)
        generated_data["lastHydrated"] = int(time.time() * 1000)  # Just generated = hydrated
        
        # Save to file
        ui_file = app_folder / "ui.json"
        ui_file.write_text(json.dumps(generated_data, indent=2))
        print(f"[Generate] Saved generated app to {ui_file}")
        
        return {"status": "success", "id": app_id, "data": generated_data}
    except json.JSONDecodeError as e:
        print(f"[Generate] JSON parse error: {e}")
        print(f"[Generate] Response was: {response_text[:500] if 'response_text' in dir() else 'N/A'}...")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        print(f"[Generate] Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


class GenerateFromReportRequest(BaseModel):
    report_content: str
    globals_json: Optional[dict] = {}
    model: Optional[str] = None


@router.post("/generate_from_report")
async def generate_from_report(request: GenerateFromReportRequest):
    """Generate a new app using AI based on a structured report."""
    import yaml
    try:
        print(f"[GenerateFromReport] Starting app generation from report...")
        print(f"[GenerateFromReport] Report length: {len(request.report_content)} chars")
        
        # Load generation prompt
        prompt_file = PROJECT_ROOT / "prompts" / "ReportToAppPrompt.md"

        if not prompt_file.exists():
            raise HTTPException(status_code=500, detail="Report-to-App prompt not found")
        
        generation_prompt = prompt_file.read_text()
        generation_prompt = generation_prompt.replace("{{REPORT_CONTENT}}", request.report_content)
        
        # Prepare globals context (limit size if too large)
        globals_str = json.dumps(request.globals_json, indent=2)
        if len(globals_str) > 100000:
             print("[GenerateFromReport] Globals too large, truncating...")
             globals_str = globals_str[:100000] + "...(truncated)"
             
        generation_prompt = generation_prompt.replace("{{GLOBALS_CONTENT}}", globals_str)
        print(f"[GenerateFromReport] Prompt prepared, length: {len(generation_prompt)} chars")
        
        # Get model from settings
        config_dir = PROJECT_ROOT / "config"
        profile = yaml.safe_load((config_dir / "profiles.yaml").read_text())
        models_config = json.loads((config_dir / "models.json").read_text())
        
        model_key = profile.get("llm", {}).get("text_generation", "gemini")
        model_info = models_config.get("models", {}).get(model_key, {})
        model = model_info.get("model", "gemini-2.0-flash")
        
        # Allow request override
        if request.model:
            model = request.model
        print(f"[GenerateFromReport] Using model: {model} (from config key: {model_key})")
        
        # Call Gemini
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # No Google Search needed - we have the report
        print("[GenerateFromReport] Calling Gemini...")
        response = client.models.generate_content(
            model=model,
            contents=generation_prompt,
            config=types.GenerateContentConfig(
                temperature=0.3
            )
        )
        response_text = response.text.strip()
        print(f"[GenerateFromReport] Got response, length: {len(response_text)} chars")
        
        # Clean up response
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1).strip()
        else:
            json_start = response_text.find('{')
            if json_start > 0:
                response_text = response_text[json_start:].strip()
        
        # Parse JSON
        generated_data = json.loads(response_text)
        print(f"[GenerateFromReport] Parsed JSON successfully, {len(generated_data.get('cards', []))} cards")
        
        # Create app ID and folder
        app_id = f"app-{int(time.time() * 1000)}"
        apps_dir = PROJECT_ROOT / "apps"
        apps_dir.mkdir(exist_ok=True)
        
        app_folder = apps_dir / app_id
        app_folder.mkdir(exist_ok=True)
        
        # Add metadata
        generated_data["id"] = app_id
        if "name" not in generated_data:
            generated_data["name"] = "Report Dashboard"
        generated_data["description"] = "Generated from report"
        generated_data["lastModified"] = int(time.time() * 1000)
        generated_data["lastHydrated"] = int(time.time() * 1000)
        
        # Save to file
        ui_file = app_folder / "ui.json"
        ui_file.write_text(json.dumps(generated_data, indent=2))
        print(f"[GenerateFromReport] Saved generated app to {ui_file}")
        
        return {"status": "success", "id": app_id, "data": generated_data}
    except json.JSONDecodeError as e:
        print(f"[GenerateFromReport] JSON parse error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        print(f"[GenerateFromReport] Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{app_id}/hydrate")
async def hydrate_app(app_id: str, request: HydrateRequest = None):
    import yaml
    try:
        print(f"[Hydrate] Starting hydration for app: {app_id}")
        
        # Load the app
        app_folder = PROJECT_ROOT / "apps" / app_id
        ui_file = app_folder / "ui.json"
        
        if not ui_file.exists():
            raise HTTPException(status_code=404, detail="App not found")
        
        app_data = json.loads(ui_file.read_text())
        print(f"[Hydrate] Loaded app with {len(app_data.get('cards', []))} cards")
        
        # Load hydration prompt
        prompt_file = PROJECT_ROOT / "prompts" / "AppHydrationPrompt.md"

        if not prompt_file.exists():
            raise HTTPException(status_code=500, detail="Hydration prompt not found")
        
        hydration_prompt = prompt_file.read_text()
        
        # Add current date for context
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
        hydration_prompt = hydration_prompt.replace("{{CURRENT_DATE}}", current_date)
        hydration_prompt = hydration_prompt.replace("{{JSON_CONTENT}}", json.dumps(app_data, indent=2))
        
        # Add user preferences if provided
        user_prompt = ""
        if request and hasattr(request, 'user_prompt') and request.user_prompt:
            user_prompt = request.user_prompt
            print(f"[Hydrate] User preferences: {user_prompt[:100]}...")
        hydration_prompt = hydration_prompt.replace("{{USER_PROMPT}}", user_prompt)
        
        print(f"[Hydrate] Prompt prepared with date {current_date}, length: {len(hydration_prompt)} chars")
        
        # Get model from settings (same as agents)
        config_dir = PROJECT_ROOT / "config"
        profile = yaml.safe_load((config_dir / "profiles.yaml").read_text())
        models_config = json.loads((config_dir / "models.json").read_text())
        
        model_key = profile.get("llm", {}).get("text_generation", "gemini")
        model_info = models_config.get("models", {}).get(model_key, {})
        model = model_info.get("model", "gemini-2.0-flash")  # Fallback if not found
        
        # Allow request override
        if request and hasattr(request, 'model') and request.model:
            model = request.model
        print(f"[Hydrate] Using model: {model} (from config key: {model_key})")
        
        # Call Gemini for hydration with Google Search enabled for real-time data
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Enable Google Search grounding for real-time data
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        
        print("[Hydrate] Calling Gemini with Google Search enabled...")
        response = client.models.generate_content(
            model=model,
            contents=hydration_prompt,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.2  # Lower temperature for factual data
            )
        )
        response_text = response.text.strip()
        print(f"[Hydrate] Got response, length: {len(response_text)} chars")
        
        # Clean up response - extract JSON from markdown fences or explanatory text
        # Gemini often adds "Okay, here's the JSON:" or similar before the actual JSON
        # Try to find JSON within markdown code fences
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1).strip()
            print("[Hydrate] Extracted JSON from markdown fences")
        else:
            # Try to find JSON by looking for the opening brace
            json_start = response_text.find('{')
            if json_start > 0:
                response_text = response_text[json_start:].strip()
                print(f"[Hydrate] Trimmed explanatory text, JSON starts at char {json_start}")
        
        # Parse the hydrated JSON
        hydrated_data = json.loads(response_text)
        print(f"[Hydrate] Parsed JSON successfully, {len(hydrated_data.get('cards', []))} cards")
        
        # Update lastHydrated timestamp
        hydrated_data["lastHydrated"] = int(time.time() * 1000)
        hydrated_data["lastModified"] = int(time.time() * 1000)
        
        # Save back
        ui_file.write_text(json.dumps(hydrated_data, indent=2))
        print(f"[Hydrate] Saved hydrated app to {ui_file}")
        
        return {"status": "success", "id": app_id, "data": hydrated_data}
    except json.JSONDecodeError as e:
        print(f"[Hydrate] JSON parse error: {e}")
        print(f"[Hydrate] Response was: {response_text[:500] if 'response_text' in dir() else 'N/A'}...")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        print(f"[Hydrate] Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
