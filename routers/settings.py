# Settings Router - Manages system configuration and dependencies (Ollama)
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from pathlib import Path
import os
import requests
import base64
import secrets
from dotenv import load_dotenv, set_key

# Import from config system
from config.settings_loader import reload_settings, save_settings, reset_settings, get_ollama_url
from shared.state import settings

# === API KEY REGISTRY ===
# Defines all managed environment variable keys, grouped by service.
# Only keys listed here can be read/written via the /apikeys endpoints (whitelist).

ENV_FILE = Path(__file__).parent.parent / ".env"

API_KEY_REGISTRY = {
    "core": {
        "label": "Core AI",
        "keys": [
            {"env": "GEMINI_API_KEY", "label": "Gemini API Key", "type": "secret"},
            {"env": "GOOGLE_CLOUD_PROJECT", "label": "Vertex AI Project ID", "type": "text"},
            {"env": "VERTEX_AI_API_KEY", "label": "Vertex AI API Key", "type": "secret"},
        ],
    },
    "neo4j": {
        "label": "Neo4j Knowledge Graph",
        "keys": [
            {"env": "NEO4J_ENABLED", "label": "Enabled (true/false)", "type": "text", "default": "true"},
            {"env": "NEO4J_URI", "label": "Connection URI", "type": "url", "default": "bolt://localhost:7687"},
            {"env": "NEO4J_USER", "label": "Username", "type": "text", "default": "neo4j"},
            {"env": "NEO4J_PASSWORD", "label": "Password", "type": "secret", "default": "arcturus-neo4j"},
        ],
    },
    "mnemo": {
        "label": "Mnemo Extraction",
        "keys": [
            {"env": "MNEMO_ENABLED", "label": "Enabled (true/false)", "type": "text", "default": "true"},
            {"env": "MNEMO_SECRET_KEY", "label": "JWT Secret Key", "type": "secret", "generate": True, "auto_init": True},
        ],
    },
    "gateway": {
        "label": "Gateway",
        "keys": [
            {"env": "ARCTURUS_GATEWAY_ADMIN_KEY", "label": "Admin Key", "type": "secret", "generate": True},
            {"env": "ARCTURUS_GATEWAY_WEBHOOK_SIGNING_SECRET", "label": "Webhook Signing Secret", "type": "secret", "generate": True},
            {"env": "ARCTURUS_GATEWAY_GITHUB_WEBHOOK_SECRET", "label": "GitHub Webhook Secret", "type": "secret", "generate": True},
            {"env": "ARCTURUS_GATEWAY_JIRA_WEBHOOK_TOKEN", "label": "Jira Webhook Token", "type": "secret", "generate": True},
            {"env": "ARCTURUS_GATEWAY_GMAIL_CHANNEL_TOKEN", "label": "Gmail Channel Token", "type": "secret", "generate": True},
        ],
    },
    "telegram": {
        "label": "Telegram",
        "keys": [
            {"env": "TELEGRAM_TOKEN", "label": "Bot Token", "type": "secret"},
        ],
    },
    "slack": {
        "label": "Slack",
        "keys": [
            {"env": "SLACK_BOT_TOKEN", "label": "Bot Token", "type": "secret"},
            {"env": "SLACK_SIGNING_SECRET", "label": "Signing Secret", "type": "secret"},
        ],
    },
    "discord": {
        "label": "Discord",
        "keys": [
            {"env": "DISCORD_BOT_TOKEN", "label": "Bot Token", "type": "secret"},
            {"env": "DISCORD_PUBLIC_KEY", "label": "Public Key", "type": "secret"},
        ],
    },
    "whatsapp": {
        "label": "WhatsApp",
        "keys": [
            {"env": "WHATSAPP_BRIDGE_URL", "label": "Bridge URL", "type": "url"},
            {"env": "WHATSAPP_BRIDGE_SECRET", "label": "Bridge Secret", "type": "secret"},
        ],
    },
    "google_chat": {
        "label": "Google Chat",
        "keys": [
            {"env": "GOOGLE_CHAT_WEBHOOK_URL", "label": "Webhook URL", "type": "url"},
            {"env": "GOOGLE_CHAT_SERVICE_ACCOUNT_TOKEN", "label": "Service Account Token", "type": "secret"},
            {"env": "GOOGLE_CHAT_VERIFICATION_TOKEN", "label": "Verification Token", "type": "secret"},
        ],
    },
    "imessage": {
        "label": "iMessage / BlueBubbles",
        "keys": [
            {"env": "BLUEBUBBLES_URL", "label": "Server URL", "type": "url"},
            {"env": "BLUEBUBBLES_PASSWORD", "label": "Password", "type": "secret"},
            {"env": "BLUEBUBBLES_WEBHOOK_SECRET", "label": "Webhook Secret", "type": "secret"},
        ],
    },
    "teams": {
        "label": "Microsoft Teams",
        "keys": [
            {"env": "TEAMS_APP_ID", "label": "App ID", "type": "text"},
            {"env": "TEAMS_APP_PASSWORD", "label": "App Password", "type": "secret"},
            {"env": "TEAMS_SERVICE_URL", "label": "Service URL", "type": "url"},
        ],
    },
    "signal": {
        "label": "Signal",
        "keys": [
            {"env": "SIGNAL_BRIDGE_URL", "label": "Bridge URL", "type": "url"},
            {"env": "SIGNAL_BRIDGE_SECRET", "label": "Bridge Secret", "type": "secret"},
            {"env": "SIGNAL_PHONE_NUMBER", "label": "Phone Number", "type": "text"},
            {"env": "SIGNAL_CLI_URL", "label": "CLI URL", "type": "url"},
        ],
    },
    "matrix": {
        "label": "Matrix",
        "keys": [
            {"env": "MATRIX_HOMESERVER_URL", "label": "Homeserver URL", "type": "url"},
            {"env": "MATRIX_USER_ID", "label": "User ID", "type": "text"},
            {"env": "MATRIX_ACCESS_TOKEN", "label": "Access Token", "type": "secret"},
        ],
    },
}

def _ensure_defaults():
    """Write default values to .env for keys that aren't already set.

    Called once at module load so Neo4j, Mnemo, etc. work out of the box.
    Users can still override any value via the Settings UI.
    """
    if not ENV_FILE.exists():
        ENV_FILE.touch()

    changed = False
    for group in API_KEY_REGISTRY.values():
        for key_def in group["keys"]:
            env_name = key_def["env"]
            # Skip if already present in environment
            if os.environ.get(env_name, "").strip():
                continue

            value = key_def.get("default")
            # Auto-generate a secret if flagged and not yet set
            if not value and key_def.get("auto_init"):
                value = base64.b64encode(secrets.token_bytes(32)).decode()

            if value:
                set_key(str(ENV_FILE), env_name, value)
                os.environ[env_name] = value
                changed = True

    if changed:
        load_dotenv(str(ENV_FILE), override=True)


# Auto-populate defaults on first import (server startup)
_ensure_defaults()


def _mask_value(value: str) -> str:
    """Return a masked preview of a value. Never returns the full value."""
    if not value:
        return None
    if len(value) <= 8:
        return "****"
    return f"{value[:4]}...{value[-4:]}"

router = APIRouter()


# === SETTINGS API ENDPOINTS ===

@router.get("/settings")
async def get_settings():
    """Get all current settings from config/settings.json"""
    try:
        # Force reload to get latest from disk
        current_settings = reload_settings()
        return {"status": "success", "settings": current_settings}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load settings: {str(e)}")


class UpdateSettingsRequest(BaseModel):
    settings: dict


@router.put("/settings")
async def update_settings(request: UpdateSettingsRequest):
    """Update settings and save to config/settings.json
    
    Note: Some settings require re-indexing (chunk_size, chunk_overlap, etc.)
    or server restart to take effect.
    """
    try:
        # Use shared global settings
        global settings 
        
        # Deep merge incoming settings with existing
        def deep_merge(base: dict, update: dict) -> dict:
            for key, value in update.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict) and value:
                    deep_merge(base[key], value)
                else:
                    base[key] = value
            return base
        
        # Reload potentially stale global settings just in case
        settings = reload_settings()
        deep_merge(settings, request.settings)
        save_settings()

        # Reset Gemini client singleton if gemini settings changed
        if "gemini" in request.settings:
            try:
                from config.gemini_client import reset_client
                reset_client()
            except Exception:
                pass
        
        # Identify settings that require action
        warnings = []
        rag_keys = ["chunk_size", "chunk_overlap", "max_chunk_length", "semantic_word_limit"]
        if "rag" in request.settings:
            for key in rag_keys:
                if key in request.settings["rag"]:
                    warnings.append(f"Changed '{key}' - requires re-indexing documents to take effect")
        
        if "models" in request.settings:
            # Agent models take effect on next run, but RAG models might need more
            warnings.append("Agent model changes will take effect on the next run.")
            warnings.append("RAG model changes take effect on next document processing or server restart")
        
        return {
            "status": "success",
            "message": "Settings saved successfully",
            "warnings": warnings if warnings else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save settings: {str(e)}")


@router.post("/settings/reset")
async def reset_to_defaults():
    """Reset all settings to default values from config/settings.defaults.json"""
    try:
        reset_settings()
        return {"status": "success", "message": "Settings reset to defaults"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to reset settings: {str(e)}")


@router.post("/settings/restart")
async def restart_server():
    """Return instructions for manual restart.
    
    Note: Automatic restart doesn't work reliably with npm run dev:all / concurrently.
    The proper way is to manually Ctrl+C and restart.
    """
    return {
        "status": "manual_required",
        "message": "Automatic restart is not supported. Please manually restart the server.",
        "instructions": [
            "1. Press Ctrl+C in the terminal running npm run dev:all",
            "2. Run: npm run dev:all",
            "3. Refresh the browser"
        ]
    }


# === GEMINI API ENDPOINTS ===

@router.get("/gemini/models")
async def get_gemini_models():
    """List available Gemini models from the configured API (Vertex AI or API key)."""
    try:
        from config.gemini_client import get_gemini_client, _load_gemini_settings
        cfg = _load_gemini_settings()
        mode = cfg.get("mode", "api_key")
        client = get_gemini_client()

        models = []
        for model in client.models.list():
            name = getattr(model, 'name', '') or ''
            # Normalize model ID — API key: "models/gemini-2.5-flash", Vertex: "publishers/google/models/gemini-2.5-flash"
            model_id = name
            for prefix in ("publishers/google/models/", "models/"):
                if model_id.startswith(prefix):
                    model_id = model_id[len(prefix):]
                    break

            # Skip non-Gemini and embedding-only models
            if not model_id.startswith("gemini"):
                continue

            # Skip embedding models by name
            if "embedding" in model_id or "aqa" in model_id:
                continue

            # Check generation support if available
            supported = getattr(model, 'supported_generation_methods', None)
            if supported and 'generateContent' not in supported:
                continue

            display = getattr(model, 'display_name', '') or model_id
            desc = getattr(model, 'description', '') or ''
            models.append({
                "value": model_id,
                "label": display,
                "description": desc[:120],
            })

        # Sort: newer/better models first (2.5-pro, 2.5-flash before 2.0, 1.5)
        models.sort(key=lambda m: m["value"], reverse=True)

        return {"status": "success", "mode": mode, "models": models}
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {"status": "error", "error": str(e), "models": []}


# === OLLAMA API ENDPOINTS ===

@router.get("/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models from local instance"""
    try:
        ollama_url = get_ollama_url("base")
        response = requests.get(f"{ollama_url}/api/tags", timeout=10)
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="Failed to connect to Ollama")
        
        data = response.json()
        models = []
        for model in data.get("models", []):
            name = model.get("name", "")
            size_bytes = model.get("size", 0)
            size_gb = round(size_bytes / (1024**3), 2) if size_bytes else 0
            
            # Get family info from Ollama response
            details = model.get("details", {})
            families = details.get("families", [])
            
            # Infer capabilities from model name AND family
            capabilities = set()
            name_lower = name.lower()
            
            # Embedding models
            if "embed" in name_lower or "nomic" in name_lower or "nomic-bert" in families:
                capabilities.add("embedding")
            
            # Vision/multimodal models - check for explicit vision families or name patterns
            vision_families = ["clip", "qwen3vl", "llava"]
            vision_names = ["vl", "vision", "llava", "moondream", "gemma3"]  # gemma3 supports vision
            
            if any(f in families for f in vision_families) or any(v in name_lower for v in vision_names):
                capabilities.add("text")
                capabilities.add("image")
            else:
                capabilities.add("text")
            
            models.append({
                "name": name,
                "size_gb": size_gb,
                "capabilities": list(capabilities),
                "modified_at": model.get("modified_at", "")
            })
        
        return {"status": "success", "models": models}
        
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="Ollama is not running. Please start Ollama.")

class PullModelRequest(BaseModel):
    name: str

@router.post("/ollama/pull")
async def pull_ollama_model(request: PullModelRequest):
    """Pull a new model from Ollama registry (starts async download)"""
    try:
        ollama_url = get_ollama_url("base")
        # Use streaming=False for now, just initiate the pull
        response = requests.post(
            f"{ollama_url}/api/pull",
            json={"name": request.name, "stream": False},
            timeout=600  # 10 min timeout for large models
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Failed to pull model: {response.text}")
        
        return {"status": "success", "message": f"Model '{request.name}' pulled successfully"}
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="Model pull timed out - try from terminal")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gemini/status")
async def get_gemini_status():
    """Check if Gemini is configured (API key or Vertex AI)."""
    try:
        from config.gemini_client import is_gemini_configured, _load_gemini_settings
        cfg = _load_gemini_settings()
        mode = cfg.get("mode", "api_key")

        api_key = os.environ.get("GEMINI_API_KEY", "")
        vertex_project = cfg.get("vertex_ai", {}).get("project") or os.environ.get("GOOGLE_CLOUD_PROJECT", "")
        vertex_location = cfg.get("vertex_ai", {}).get("location", "us-central1")

        return {
            "status": "success",
            "mode": mode,
            "configured": is_gemini_configured(),
            "api_key_preview": f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else None,
            "vertex_project": vertex_project or None,
            "vertex_location": vertex_location,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === API KEYS MANAGEMENT ===

@router.get("/apikeys/status")
async def get_apikeys_status():
    """Return configured status for all managed API keys (never returns full values)."""
    result = {}
    for group_id, group in API_KEY_REGISTRY.items():
        keys_status = []
        for key_def in group["keys"]:
            env_name = key_def["env"]
            value = os.environ.get(env_name, "").strip()
            entry = {
                "env": env_name,
                "label": key_def["label"],
                "type": key_def["type"],
                "configured": bool(value),
                "preview": _mask_value(value) if value else None,
            }
            if key_def.get("generate"):
                entry["generate"] = True
            if key_def.get("default"):
                entry["has_default"] = True
            keys_status.append(entry)
        result[group_id] = {
            "label": group["label"],
            "keys": keys_status,
            "configured_count": sum(1 for k in keys_status if k["configured"]),
            "total_count": len(keys_status),
        }
    return {"status": "success", "groups": result}


class UpdateApiKeysRequest(BaseModel):
    keys: Dict[str, str]


@router.put("/apikeys")
async def update_apikeys(request: UpdateApiKeysRequest):
    """Save API keys to .env file and reload into environment.

    Only allows keys listed in API_KEY_REGISTRY (whitelist).
    Empty string values unset the key.
    """
    # Build whitelist of allowed env var names
    allowed_keys = set()
    for group in API_KEY_REGISTRY.values():
        for key_def in group["keys"]:
            allowed_keys.add(key_def["env"])

    # Validate all submitted keys are in the whitelist
    disallowed = set(request.keys.keys()) - allowed_keys
    if disallowed:
        raise HTTPException(
            status_code=400,
            detail=f"Keys not allowed: {', '.join(sorted(disallowed))}",
        )

    # Ensure .env file exists
    if not ENV_FILE.exists():
        ENV_FILE.touch()

    # Write each key to .env file
    updated = []
    for env_name, value in request.keys.items():
        value = value.strip()
        if value:
            set_key(str(ENV_FILE), env_name, value)
            os.environ[env_name] = value
        else:
            # Unset: remove from .env and os.environ
            set_key(str(ENV_FILE), env_name, "")
            os.environ.pop(env_name, None)
        updated.append(env_name)

    # Force reload dotenv to pick up changes
    load_dotenv(str(ENV_FILE), override=True)

    # Reset Gemini client singleton if relevant keys changed
    gemini_keys = {"GEMINI_API_KEY", "GOOGLE_CLOUD_PROJECT", "VERTEX_AI_API_KEY"}
    if gemini_keys & set(updated):
        try:
            from config.gemini_client import reset_client
            reset_client()
        except Exception:
            pass

    return {
        "status": "success",
        "message": f"Updated {len(updated)} key(s)",
        "updated": updated,
    }
