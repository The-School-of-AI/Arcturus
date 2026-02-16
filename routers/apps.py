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


class RenameAppRequest(BaseModel):
    name: str


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


@router.post("/{app_id}/rename")
async def rename_app_endpoint(app_id: str, request: RenameAppRequest):
    try:
        app_folder = PROJECT_ROOT / "apps" / app_id
        if not app_folder.exists():
            raise HTTPException(status_code=404, detail="App not found")
        
        ui_file = app_folder / "ui.json"
        if not ui_file.exists():
            raise HTTPException(status_code=404, detail="UI configuration not found")
            
        data = json.loads(ui_file.read_text())
        data["name"] = request.name
        data["lastModified"] = int(time.time() * 1000)
        
        ui_file.write_text(json.dumps(data, indent=2))
        return {"status": "success", "id": app_id, "name": request.name}
    except Exception as e:
        if isinstance(e, HTTPException): raise e
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
@router.post("/generate")
async def generate_app(request: GenerateAppRequest):
    """Generate a new app using AI based on user prompt."""
    try:
        from core.generator import AppGenerator
        generator = AppGenerator(project_root=PROJECT_ROOT)
        
        # Generate both frontend and backend
        result = await generator.generate_app(
            name=request.name, 
            prompt=request.prompt, 
            model_override=request.model
        )
        
        return {
            "status": "success", 
            "id": result["id"], 
            "data": result["frontend"]
        }
    except Exception as e:
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
        
        # Determine mode: Refinement vs Hydration
        is_refining = False
        user_prompt = ""
        prompt_text = ""
        
        from core.skills.library.apphydrationprompt.skill import ApphydrationpromptSkill
        from core.skills.library.apprefinementprompt.skill import ApprefinementpromptSkill

        if request and hasattr(request, 'user_prompt') and request.user_prompt:
            print("[Hydrate] User prompt detected -> Using REFINEMENT mode")
            is_refining = True
            user_prompt = request.user_prompt
            skill = ApprefinementpromptSkill()
            prompt_template = skill.prompt_text
            
            # Refinement prompt replacements
            prompt_text = prompt_template.replace("{{USER_PROMPT}}", user_prompt)
            prompt_text = prompt_text.replace("{{JSON_CONTENT}}", json.dumps(app_data, indent=2))
            
        else:
            print("[Hydrate] No user prompt -> Using HYDRATION mode")
            skill = ApphydrationpromptSkill()
            prompt_template = skill.prompt_text
            
            # Hydration prompt replacements
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S %Z")
            prompt_text = prompt_template.replace("{{CURRENT_DATE}}", current_date)
            prompt_text = prompt_text.replace("{{JSON_CONTENT}}", json.dumps(app_data, indent=2))
            prompt_text = prompt_text.replace("{{USER_PROMPT}}", "") # Empty user prompt for hydration
        
        print(f"[Hydrate] Prompt prepared, length: {len(prompt_text)} chars")
        
        # Get model from settings (same as agents)
        config_dir = PROJECT_ROOT / "config"
        profile = yaml.safe_load((config_dir / "profiles.yaml").read_text())
        models_config = json.loads((config_dir / "models.json").read_text())
        
        model_key = profile.get("llm", {}).get("text_generation", "gemini")
        model_info = models_config.get("models", {}).get(model_key, {})
        model = model_info.get("model", "gemini-2.5-flash")  # Fallback if not found
        
        # Allow request override
        if request and hasattr(request, 'model') and request.model:
            model = request.model
        print(f"[Hydrate] Using model: {model} (from config key: {model_key})")
        
        # Call Gemini for hydration/refinement with Google Search enabled
        from google import genai
        from google.genai import types
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        
        # Enable Google Search grounding for real-time data
        google_search_tool = types.Tool(google_search=types.GoogleSearch())
        
        print("[Hydrate] Calling Gemini with Google Search enabled...")
        response = client.models.generate_content(
            model=model,
            contents=prompt_text,
            config=types.GenerateContentConfig(
                tools=[google_search_tool],
                temperature=0.4 if is_refining else 0.2  # Higher temp for creative refinement
            )
        )
        response_text = response.text.strip()
        print(f"[Hydrate] Got response, length: {len(response_text)} chars")
        
        # Clean up response - extract JSON from markdown fences or explanatory text
        json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_text, re.DOTALL)
        if json_match:
            response_text = json_match.group(1).strip()
            print("[Hydrate] Extracted JSON from markdown fences")
        else:
            # Try to find JSON by looking for the opening brace
            json_start = response_text.find('{')
            if json_start >= 0:
                response_text = response_text[json_start:].strip()
                print(f"[Hydrate] Trimmed explanatory text, JSON starts at char {json_start}")
        
        # Parse the JSON
        new_app_data = json.loads(response_text)
        print(f"[Hydrate] Parsed JSON successfully, {len(new_app_data.get('cards', []))} cards")
        
        # Update timestamps
        new_app_data["lastHydrated"] = int(time.time() * 1000)
        new_app_data["lastModified"] = int(time.time() * 1000)
        
        # If refining, we might have completely new structure. If hydrating, structure should preserve IDs mostly
        # but in both cases we trust the output (since prompt handles constraints).
        
        # Save back to file
        ui_file.write_text(json.dumps(new_app_data, indent=2))
        print(f"[Hydrate] Saved updated app to {ui_file}")
        
        return {"status": "success", "id": app_id, "data": new_app_data}
        
    except json.JSONDecodeError as e:
        print(f"[Hydrate] JSON parse error: {e}")
        # print(f"[Hydrate] Response was: {response_text[:500] if 'response_text' in locals() else 'N/A'}...")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response as JSON: {str(e)}")
    except Exception as e:
        print(f"[Hydrate] Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
