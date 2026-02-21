"""
Minimal input_scanner: pattern-based prompt-injection + canary detection.
"""
import os
import re
import requests
from typing import Any, Dict

LAKERA_GUARD_API_KEY = os.getenv("LAKERA_GUARD_API_KEY")
LAKERA_PROJECT_ID = os.getenv("LAKERA_PROJECT_ID", "project-XXXXXXXXXXX") # Default to a placeholder

INJECTION_PATTERNS = [
    r"ignore (previous|all) instructions",
    r"disregard (previous|prior) instructions",
    r"ignore your (system|developer) prompt",
    r"follow these new instructions instead",
    r"you are now .* assistant",
    r"shutdown|format disk|rm -rf",
    r"jailbreak",
    r"suddenly do this",
]

INJECTION_REGEX = re.compile("|".join(f"(?:{p})" for p in INJECTION_PATTERNS), re.I)
CANARY_TOKEN_REGEX = re.compile(r"CANARY_[A-F0-9]{8,}")

def scan_input_local(text: str) -> Dict[str, Any]:
    """The original local scanner."""
    if text is None:
        return {"allowed": False, "reason": "empty_input", "hits": []}
    try:
        hits = []
        canaries = CANARY_TOKEN_REGEX.findall(text)
        if canaries:
            hits.extend([f"canary:{c}" for c in canaries])
        if INJECTION_REGEX.search(text):
            hits.append("injection_pattern")
        collapsed = re.sub(r"[\W_]+", "", text).lower()
        if "ignorepreviousinstructions" in collapsed or "disregardpriorinstructions" in collapsed:
            hits.append("obfuscated_injection")
        allowed = len(hits) == 0
        reason = "ok" if allowed else ",".join(hits)
        return {"allowed": allowed, "reason": reason, "hits": hits}
    except Exception as e:
        return {"allowed": False, "reason": f"scanner_error:{e}", "hits": []}

def scan_input(text: str, session_context: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Scans input using Lakera Guard API if available, otherwise falls back to local scanner.
    """
    if not LAKERA_GUARD_API_KEY:
        return scan_input_local(text)

    if text is None:
        return {"allowed": False, "reason": "empty_input", "hits": []}

    try:
        session = requests.Session()
        response = session.post(
            "https://api.lakera.ai/v2/guard",
            json={"messages": [{"content": text, "role": "user"}], "project_id": LAKERA_PROJECT_ID},
            headers={"Authorization": f"Bearer {LAKERA_GUARD_API_KEY}"},
            timeout=5, # Add a timeout
        )
        response.raise_for_status()
        response_json = response.json()

        allowed = not response_json.get("flagged", False)
        reason = "ok"
        hits = []
        if not allowed:
            # Extract details from the response
            categories = response_json.get('results', [{}])[0].get('categories', {})
            for category, flagged in categories.items():
                if flagged:
                    hits.append(category)
            reason = ",".join(hits) if hits else "flagged_by_lakera"

        return {"allowed": allowed, "reason": reason, "hits": hits}
    except requests.exceptions.RequestException as e:
        # Fallback to local scanner in case of API error
        return scan_input_local(text)
    except Exception as e:
        return {"allowed": False, "reason": f"scanner_error:{e}", "hits": []}