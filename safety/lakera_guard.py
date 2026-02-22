"""
Lakera Guard integration for ML-powered prompt injection detection.

Requires environment variables:
    LAKERA_GUARD_API_KEY  — Bearer token from https://platform.lakera.ai
    LAKERA_PROJECT_ID     — Project ID (optional, defaults to placeholder)

If LAKERA_GUARD_API_KEY is not set, scan_lakera() returns allowed=True so the
pipeline downgrades gracefully to the local scanner.
"""
import os
from typing import Any, Dict

import requests

LAKERA_API_URL = "https://api.lakera.ai/v2/guard"
LAKERA_TIMEOUT = 5  # seconds


def is_configured() -> bool:
    """Return True if a Lakera API key is present in the environment."""
    return bool(os.getenv("LAKERA_GUARD_API_KEY"))


def scan_lakera(text: str) -> Dict[str, Any]:
    """
    Scan *text* with Lakera Guard.

    Returns a standard scanner dict:
        allowed  (bool)       — False if Lakera flagged the input.
        reason   (str)        — Short reason string.
        hits     (list[str])  — Flagged Lakera categories.
        provider (str)        — Always "lakera".

    Never raises; errors return allowed=True so the pipeline can fall through
    to local scanning.
    """
    LAKERA_GUARD_API_KEY = os.getenv("LAKERA_GUARD_API_KEY")
    LAKERA_PROJECT_ID = os.getenv("LAKERA_PROJECT_ID", "project-XXXXXXXXXXX")
    if not LAKERA_GUARD_API_KEY:
        return {"allowed": True, "reason": "lakera_not_configured", "hits": [], "provider": "lakera"}

    print(f"[Aegis/Lakera] → POST {LAKERA_API_URL} (text[:60]={text[:60]!r})", flush=True)
    try:
        response = requests.Session().post(
            LAKERA_API_URL,
            json={
                # Lakera v2: project_id is tied to the API key on the platform,
                # NOT sent in the request body. Only messages are required.
                "messages": [{"content": text, "role": "user"}],
            },
            headers={"Authorization": f"Bearer {LAKERA_GUARD_API_KEY}"},
            timeout=LAKERA_TIMEOUT,
        )
        response.raise_for_status()
        body = response.json()
        print(f"[Aegis/Lakera] ← {response.status_code} flagged={body.get('flagged')} body={str(body)[:200]}", flush=True)

        allowed = not body.get("flagged", False)
        hits: list[str] = []
        if not allowed:
            categories = body.get("results", [{}])[0].get("categories", {})
            hits = [cat for cat, flagged in categories.items() if flagged]

        return {
            "allowed": allowed,
            "reason": ",".join(hits) if hits else ("ok" if allowed else "flagged_by_lakera"),
            "hits": hits,
            "provider": "lakera",
        }
    except Exception as exc:
        print(f"[Aegis/Lakera] ✗ error: {exc}", flush=True)
        return {
            "allowed": True,
            "reason": f"lakera_error:{exc}",
            "hits": [],
            "provider": "lakera",
        }
