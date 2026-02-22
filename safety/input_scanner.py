"""
Minimal input_scanner: pattern-based prompt-injection + canary detection.
Enhanced with obfuscation detection (Unicode, base64, character substitution).
Supports hybrid mode (parallel execution) and fallback mode (sequential).
"""
import os
import re
import base64
import binascii
import unicodedata
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Tuple, Optional

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

# Character substitution patterns (leet speak, etc.)
CHAR_SUBSTITUTIONS = {
    '1': 'i', '3': 'e', '4': 'a', '5': 's', '7': 't', '0': 'o',
    '@': 'a', '!': 'i', '$': 's', '|': 'i'
}

def decode_base64(text: str) -> Tuple[str, bool]:
    """Attempt to decode base64 strings and return decoded text if valid."""
    # Look for base64-like patterns (alphanumeric + / + = padding)
    base64_pattern = re.compile(r'[A-Za-z0-9+/]{20,}={0,2}')
    matches = base64_pattern.findall(text)
    
    for match in matches:
        try:
            decoded = base64.b64decode(match).decode('utf-8', errors='ignore')
            if len(decoded) > 5:  # Only consider substantial decodings
                return decoded, True
        except Exception:
            continue
    
    return text, False


def decode_hex(text: str) -> Tuple[str, bool]:
    """Attempt to decode hex strings and return decoded text if valid."""
    # Look for hex-like patterns
    hex_pattern = re.compile(r'[0-9a-fA-F]{20,}')
    matches = hex_pattern.findall(text)
    
    for match in matches:
        try:
            decoded = bytes.fromhex(match).decode('utf-8', errors='ignore')
            if len(decoded) > 5:
                return decoded, True
        except Exception:
            continue
    
    return text, False


def normalize_unicode(text: str) -> str:
    """Normalize Unicode to detect obfuscated characters."""
    # Normalize to NFC form
    normalized = unicodedata.normalize('NFC', text)
    # Replace common Unicode lookalikes with ASCII equivalents
    replacements = {
        '\u200B': '',  # Zero-width space
        '\u200C': '',  # Zero-width non-joiner
        '\u200D': '',  # Zero-width joiner
        '\uFEFF': '',  # Zero-width no-break space
    }
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    return normalized


def detect_character_substitution(text: str) -> List[str]:
    """Detect leet speak and character substitution patterns."""
    hits = []
    # Normalize text for comparison
    normalized = text.lower()
    
    # Check for common substitution patterns
    substitution_patterns = [
        (r'1gn0r3', 'ignore'),
        (r'1gn0r3\s+pr3v10us', 'ignore previous'),
        (r'd15r3g4rd', 'disregard'),
        (r'pr3v10us', 'previous'),
        (r'1nstruct10ns', 'instructions'),
    ]
    
    for pattern, meaning in substitution_patterns:
        if re.search(pattern, normalized, re.I):
            hits.append(f"character_substitution:{meaning}")
    
    # Also check for mixed case obfuscation
    collapsed = re.sub(r'[\W_]+', '', normalized)
    if 'ignorepreviousinstructions' in collapsed or 'disregardpriorinstructions' in collapsed:
        hits.append("obfuscated_injection")
    
    return hits


def scan_input_local(text: str) -> Dict[str, Any]:
    """Enhanced local scanner with obfuscation detection."""
    if text is None:
        return {"allowed": False, "reason": "empty_input", "hits": []}
    try:
        hits = []
        
        # Normalize Unicode first
        text = normalize_unicode(text)
        
        # Check for canary tokens
        canaries = CANARY_TOKEN_REGEX.findall(text)
        if canaries:
            hits.extend([f"canary:{c}" for c in canaries])
        
        # Check direct injection patterns
        if INJECTION_REGEX.search(text):
            hits.append("injection_pattern")
        
        # Check for base64 encoding
        decoded_b64, is_b64 = decode_base64(text)
        if is_b64:
            # Scan decoded content
            if INJECTION_REGEX.search(decoded_b64):
                hits.append("base64_encoded_injection")
        
        # Check for hex encoding
        decoded_hex, is_hex = decode_hex(text)
        if is_hex:
            if INJECTION_REGEX.search(decoded_hex):
                hits.append("hex_encoded_injection")
        
        # Check for character substitution (leet speak)
        substitution_hits = detect_character_substitution(text)
        hits.extend(substitution_hits)
        
        # Check collapsed text for obfuscated patterns
        collapsed = re.sub(r"[\W_]+", "", text).lower()
        if "ignorepreviousinstructions" in collapsed or "disregardpriorinstructions" in collapsed:
            if "obfuscated_injection" not in hits:
                hits.append("obfuscated_injection")
        
        allowed = len(hits) == 0
        reason = "ok" if allowed else ",".join(hits)
        return {"allowed": allowed, "reason": reason, "hits": hits}
    except Exception as e:
        return {"allowed": False, "reason": f"scanner_error:{e}", "hits": []}

def _scan_lakera(text: str) -> Dict[str, Any]:
    """Helper function to scan with Lakera Guard."""
    if not LAKERA_GUARD_API_KEY:
        return {"allowed": True, "reason": "lakera_not_configured", "hits": [], "provider": "lakera"}
    
    try:
        session = requests.Session()
        response = session.post(
            "https://api.lakera.ai/v2/guard",
            json={"messages": [{"content": text, "role": "user"}], "project_id": LAKERA_PROJECT_ID},
            headers={"Authorization": f"Bearer {LAKERA_GUARD_API_KEY}"},
            timeout=5,
        )
        response.raise_for_status()
        response_json = response.json()
        
        allowed = not response_json.get("flagged", False)
        reason = "ok"
        hits = []
        if not allowed:
            categories = response_json.get('results', [{}])[0].get('categories', {})
            for category, flagged in categories.items():
                if flagged:
                    hits.append(category)
            reason = ",".join(hits) if hits else "flagged_by_lakera"
        
        return {
            "allowed": allowed,
            "reason": reason,
            "hits": hits,
            "provider": "lakera"
        }
    except Exception as e:
        return {"allowed": True, "reason": f"lakera_error:{str(e)}", "hits": [], "provider": "lakera"}


def _scan_nemo(text: str, config: Dict[str, Any] = None) -> Dict[str, Any]:
    """Helper function to scan with Nemo Guardrails."""
    try:
        from safety.nemo_guardrails import scan_with_nemo
        return scan_with_nemo(text, mode="auto", config=config)
    except Exception as e:
        return {"allowed": True, "reason": f"nemo_error:{str(e)}", "hits": [], "provider": "nemo"}


def scan_input(text: str, session_context: Dict[str, Any] = None, mode: str = "hybrid") -> Dict[str, Any]:
    """
    Scans input using multi-provider defense.
    
    Modes:
    - "hybrid" (default): Run Lakera and Nemo in PARALLEL for true defense-in-depth
    - "fallback": Run Lakera → Nemo → Local sequentially (faster if Lakera flags)
    
    Implements defense-in-depth: if ANY provider flags, block.
    
    Args:
        text: Input text to scan
        session_context: Session context with safety config
        mode: "hybrid" (parallel) or "fallback" (sequential)
    """
    if text is None:
        return {"allowed": False, "reason": "empty_input", "hits": []}
    
    session_context = session_context or {}
    provider_config = session_context.get("safety_config", {})
    use_nemo = provider_config.get("use_nemo", True)
    scan_mode = provider_config.get("scan_mode", mode)  # Allow override from config
    
    results = []
    
    if scan_mode == "hybrid":
        # HYBRID MODE: Run Lakera and Nemo in parallel
        # This provides true defense-in-depth and faster response
        
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = {}
            
            # Submit Lakera scan
            if LAKERA_GUARD_API_KEY:
                futures["lakera"] = executor.submit(_scan_lakera, text)
            
            # Submit Nemo scan
            if use_nemo:
                futures["nemo"] = executor.submit(_scan_nemo, text, provider_config)
            
            # Collect all results (wait for all to complete)
            completed_futures = list(as_completed(futures.values()))
            for future in completed_futures:
                try:
                    result = future.result(timeout=6)  # Slightly longer than individual timeout
                    results.append(result)
                except Exception as e:
                    # Provider failed, add error result
                    results.append({"allowed": True, "reason": f"provider_error:{str(e)}", "hits": [], "provider": "unknown"})
            
            # Check if any provider flagged
            flagged_providers = []
            all_hits = []
            for r in results:
                all_hits.extend(r.get("hits", []))
                if not r.get("allowed", True):
                    flagged_providers.append(r.get("provider", "unknown"))
            
            # If any provider flags, block immediately
            if flagged_providers:
                return {
                    "allowed": False,
                    "reason": f"flagged_by:{','.join(flagged_providers)}",
                    "hits": list(set(all_hits)),
                    "providers": [r.get("provider") for r in results],
                    "mode": "hybrid"
                }
        
        # Both providers passed, add local scanner result
        local_result = scan_input_local(text)
        local_result["provider"] = "local"
        results.append(local_result)
        
    else:
        # FALLBACK MODE: Sequential execution (original behavior)
        # 1. Try Lakera Guard (primary, cloud-based, ML-powered)
        if LAKERA_GUARD_API_KEY:
            lakera_result = _scan_lakera(text)
            results.append(lakera_result)
            
            # If Lakera flags it, block immediately
            if not lakera_result.get("allowed", True):
                return lakera_result
        
        # 2. Try Nemo Guardrails (secondary, local, rule-based)
        if use_nemo:
            nemo_result = _scan_nemo(text, provider_config)
            results.append(nemo_result)
            
            # If Nemo flags it, block (defense-in-depth)
            if not nemo_result.get("allowed", True):
                all_hits = []
                for r in results:
                    all_hits.extend(r.get("hits", []))
                return {
                    "allowed": False,
                    "reason": f"flagged_by_multiple:{','.join(set([r.get('provider', 'unknown') for r in results if not r.get('allowed', True)]))}",
                    "hits": list(set(all_hits)),
                    "providers": [r.get("provider") for r in results],
                    "mode": "fallback"
                }
        
        # 3. Fallback to local scanner (always available)
        local_result = scan_input_local(text)
        local_result["provider"] = "local"
        results.append(local_result)
    
    # Aggregate results: if ANY provider flags, block
    all_hits = []
    flagged_providers = []
    for r in results:
        all_hits.extend(r.get("hits", []))
        if not r.get("allowed", True):
            flagged_providers.append(r.get("provider", "unknown"))
    
    if flagged_providers:
        return {
            "allowed": False,
            "reason": f"flagged_by:{','.join(flagged_providers)}",
            "hits": list(set(all_hits)),
            "providers": [r.get("provider") for r in results],
            "mode": scan_mode
        }
    
    # All providers passed
    return {
        "allowed": True,
        "reason": "ok",
        "hits": [],
        "providers": [r.get("provider") for r in results],
        "mode": scan_mode
    }