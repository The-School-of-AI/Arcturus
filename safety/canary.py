"""Canary token generation and helpers."""
import secrets
from typing import Any, Dict


def generate_canary(prefix: str = "CANARY") -> str:
    token = secrets.token_hex(8).upper()
    return f"{prefix}_{token}"

def attach_canary_to_context(context: Dict[str, Any], key: str = "canary_tokens") -> str:
    token = generate_canary()
    ctx = context or {}
    tokens = ctx.get(key, [])
    tokens.append(token)
    ctx[key] = tokens
    return token


def detect_canary_leak(text: str, session_context: Dict[str, Any]) -> list[str]:
    """
    Scans the given text for any canary tokens present in the session context.

    Args:
        text: The text to scan (e.g., an agent's output).
        session_context: The session graph's context, which should contain the 'canary_tokens' list.

    Returns:
        A list of any canary tokens found in the text.
    """
    leaked_tokens = []
    canary_tokens = session_context.get("canary_tokens", [])
    if not text or not canary_tokens:
        return leaked_tokens

    for token in canary_tokens:
        if token in text:
            leaked_tokens.append(token)

    return leaked_tokens