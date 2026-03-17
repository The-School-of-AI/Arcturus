"""
Centralized Gemini Client Factory

Supports two modes (configured in settings.json → gemini.mode):
  - "api_key"   → Uses GEMINI_API_KEY env var (Gemini Developer API)
  - "vertex_ai" → Uses Application Default Credentials / service account
                   (Vertex AI Gemini endpoint)

Usage:
    from config.gemini_client import get_gemini_client
    client = get_gemini_client()
"""

import os
from functools import lru_cache
from google import genai


def _load_gemini_settings() -> dict:
    """Load gemini section from settings.json."""
    try:
        from config.settings_loader import settings
        return settings.get("gemini", {})
    except Exception:
        return {}


def get_gemini_client() -> genai.Client:
    """
    Return a configured genai.Client based on settings.json → gemini.mode.

    - mode="api_key" (default): uses GEMINI_API_KEY env var
    - mode="vertex_ai": uses Vertex AI with project/location from settings
      Auth via GOOGLE_APPLICATION_CREDENTIALS or `gcloud auth application-default login`
    """
    cfg = _load_gemini_settings()
    mode = cfg.get("mode", "api_key")

    if mode == "vertex_ai":
        vertex = cfg.get("vertex_ai", {})
        project = vertex.get("project") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        location = vertex.get("location", "us-central1")
        # Vertex AI API key — mutually exclusive with project/location
        vertex_api_key = os.getenv("VERTEX_AI_API_KEY", "")
        if vertex_api_key:
            # API key mode: project/location not needed
            return genai.Client(vertexai=True, api_key=vertex_api_key)
        # Fallback: try gcloud CLI default project
        if not project:
            try:
                import subprocess
                result = subprocess.run(
                    ["gcloud", "config", "get-value", "project"],
                    capture_output=True, text=True, timeout=5
                )
                project = result.stdout.strip()
            except Exception:
                pass
        if not project:
            raise ValueError(
                "Vertex AI mode requires VERTEX_AI_API_KEY or "
                "GOOGLE_CLOUD_PROJECT env var or `gcloud config set project <id>`"
            )
        return genai.Client(vertexai=True, project=project, location=location)
    else:
        # Default: API key mode
        api_key_env = cfg.get("api_key_env", "GEMINI_API_KEY")
        api_key = os.getenv(api_key_env, "")
        return genai.Client(api_key=api_key)


# Singleton instance — lazily created on first import
_client = None


def get_shared_client() -> genai.Client:
    """
    Return a shared singleton client. Use this for most cases
    where a fresh client per-request is not needed.
    """
    global _client
    if _client is None:
        _client = get_gemini_client()
    return _client


def reset_client() -> None:
    """Reset the singleton client (e.g. after settings change)."""
    global _client
    _client = None


def is_gemini_configured() -> bool:
    """Check whether Gemini credentials are available (API key or Vertex AI)."""
    cfg = _load_gemini_settings()
    mode = cfg.get("mode", "api_key")
    if mode == "vertex_ai":
        vertex_api_key = os.getenv("VERTEX_AI_API_KEY", "")
        if vertex_api_key:
            return True
        vertex = cfg.get("vertex_ai", {})
        project = vertex.get("project") or os.getenv("GOOGLE_CLOUD_PROJECT", "")
        return bool(project)
    else:
        api_key_env = cfg.get("api_key_env", "GEMINI_API_KEY")
        return bool(os.getenv(api_key_env, "").strip())
