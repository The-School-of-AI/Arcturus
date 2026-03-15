"""Jailbreak detection using pattern matching."""
import re
from typing import Any, Dict, List

JAILBREAK_PATTERNS: List[str] = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|all)\s+instructions",
    r"disregard\s+(?:all\s+)?(?:previous|prior)\s+instructions",
    r"bypass\s+safety",
    r"you\s+are\s+now\s+.*\s+assistant",
]


def detect_jailbreak(text: str) -> Dict[str, Any]:
    """
    Detects jailbreak attempts using pattern matching.

    Returns a dict with:
        is_jailbreak (bool): True if any pattern matched.
        hits (list[str]):    List of matched pattern strings.
    """
    if not text:
        return {"is_jailbreak": False, "hits": []}

    hits = [p for p in JAILBREAK_PATTERNS if re.search(p, text, re.I)]
    return {"is_jailbreak": bool(hits), "hits": hits}