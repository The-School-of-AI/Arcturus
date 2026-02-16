"""
Centralized Settings Loader

This module provides a single point of access for all runtime configuration.
All backend modules should import settings from here instead of defining their own.

Usage:
    from config.settings_loader import settings, save_settings, reset_settings
    
    # Access settings
    model = settings["models"]["embedding"]
    
    # Update settings
    settings["rag"]["top_k"] = 5
    save_settings()
    
    # Reset to defaults
    reset_settings()
"""

import json
from pathlib import Path

# Paths
CONFIG_DIR = Path(__file__).parent
SETTINGS_FILE = CONFIG_DIR / "settings.json"
DEFAULTS_FILE = CONFIG_DIR / "settings.defaults.json"

# --- Settings Cache ---
_settings_cache = None

def load_settings() -> dict:
    """Load settings from file. Uses cache if already loaded."""
    global _settings_cache
    if _settings_cache is None:
        if SETTINGS_FILE.exists():
            _settings_cache = json.loads(SETTINGS_FILE.read_text())
        elif DEFAULTS_FILE.exists():
            # Fall back to defaults if settings.json doesn't exist
            _settings_cache = json.loads(DEFAULTS_FILE.read_text())
            save_settings()  # Create settings.json from defaults
        else:
            raise FileNotFoundError(f"No settings files found in {CONFIG_DIR}")
        
        # ✅ Validation Step
        required_keys = ["models", "ollama", "rag"]
        missing = [k for k in required_keys if k not in _settings_cache]
        if missing:
            raise KeyError(f"Missing required settings keys: {missing}")
            
    return _settings_cache

def save_settings() -> None:
    """Save current settings to file."""
    global _settings_cache
    if _settings_cache is not None:
        SETTINGS_FILE.write_text(json.dumps(_settings_cache, indent=2))

def reset_settings() -> dict:
    """Reset settings to defaults."""
    global _settings_cache
    if DEFAULTS_FILE.exists():
        _settings_cache = json.loads(DEFAULTS_FILE.read_text())
        save_settings()
    return _settings_cache

def reload_settings() -> dict:
    """Force reload settings from disk (useful after external changes)."""
    global _settings_cache
    _settings_cache = None
    return load_settings()

# --- Convenience Accessors ---
# These provide direct access to commonly used settings

def get_ollama_url(endpoint: str = "generate") -> str:
    """Get full Ollama URL for a specific endpoint."""
    base = load_settings()["ollama"]["base_url"]
    if endpoint == "base":
        return base  # Just return base URL without path
    endpoints = {
        "generate": "/api/generate",
        "chat": "/api/chat",
        "embed": "/api/embed",
        "embeddings": "/api/embeddings"
    }
    return f"{base}{endpoints.get(endpoint, '/api/' + endpoint)}"

def get_model(purpose: str) -> str:
    """Get model name for a specific purpose."""
    return load_settings()["models"].get(purpose, "gemma3:4b")

def get_timeout() -> int:
    """Get Ollama timeout in seconds."""
    return load_settings()["ollama"]["timeout"]

# --- Initialize on import ---
settings = load_settings()
