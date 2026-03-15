"""
Comprehensive output validation: prompt leakage, canary detection, instruction overrides.

Scans agent responses before returning to user to detect:
- System prompt leakage
- Canary token leaks
- Instruction override attempts in output
- PII leakage (delegates to PolicyEngine)
"""
import re
from typing import Dict, Any, List, Optional


# Patterns that indicate system prompt leakage
SYSTEM_PROMPT_MARKERS = [
    r"SYSTEM INSTRUCTIONS",
    r"INTERNAL_TOKEN:",
    r"CURRENT_DATE:",
    r"SYSTEM PROFILE",
    r"--- SYSTEM",
    r"\[INTERNAL_TOKEN:",
]

SYSTEM_PROMPT_REGEX = re.compile("|".join(f"(?:{m})" for m in SYSTEM_PROMPT_MARKERS), re.I)

# Patterns that indicate instruction override attempts in output
OUTPUT_OVERRIDE_PATTERNS = [
    r"ignore\s+(?:all|previous|prior)\s+instructions",
    r"new\s+instructions?:",
    r"follow\s+these\s+new",
    r"you\s+are\s+now\s+.*\s+assistant",
]

OUTPUT_OVERRIDE_REGEX = re.compile("|".join(f"(?:{p})" for p in OUTPUT_OVERRIDE_PATTERNS), re.I)


def scan_output(
    output: Any,
    session_context: Dict[str, Any] = None,
    input_data: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Comprehensive output validation.
    
    Args:
        output: Agent output (dict, string, or other)
        session_context: Session context containing canary tokens
        input_data: Original input data (may contain canary tokens)
        
    Returns:
        Dict with validation results:
        - allowed: bool
        - action: "allow", "redact", or "block"
        - reason: str
        - hits: List of detected issues
        - redacted_output: Cleaned output (if redaction needed)
    """
    session_context = session_context or {}
    input_data = input_data or {}
    
    # Extract text from output
    if isinstance(output, dict):
        text = output.get("text") or output.get("content") or output.get("output") or str(output)
    else:
        text = str(output)
    
    if not text:
        return {"allowed": True, "action": "allow", "reason": "empty_output", "hits": []}
    
    hits = []
    action = "allow"
    redacted_output = text
    
    # 1. Check for canary token leaks
    try:
        from safety.canary import detect_canary_leak
        
        # Check canary tokens from session context
        leaked_tokens = detect_canary_leak(text, session_context)
        if leaked_tokens:
            hits.append(f"canary_leak:{','.join(leaked_tokens)}")
            action = "block"  # Canary leak is critical
        
        # Check canary tokens from input data (per-agent canaries)
        if "_canary_tokens" in input_data:
            for canary in input_data["_canary_tokens"]:
                if canary in text:
                    hits.append(f"canary_leak:{canary}")
                    action = "block"
    except Exception as e:
        # Canary detection failed, but continue with other checks
        pass
    
    # 2. Check for system prompt leakage
    if SYSTEM_PROMPT_REGEX.search(text):
        hits.append("system_prompt_leakage")
        action = "block"  # System prompt leakage is critical
        # Redact the leaked markers
        redacted_output = SYSTEM_PROMPT_REGEX.sub("[REDACTED: System prompt marker]", redacted_output)
    
    # 3. Check for instruction override attempts in output
    if OUTPUT_OVERRIDE_REGEX.search(text):
        hits.append("instruction_override_in_output")
        # This is suspicious but might be false positive (user asking about instructions)
        # So we redact rather than block
        if action == "allow":
            action = "redact"
        redacted_output = OUTPUT_OVERRIDE_REGEX.sub("[REDACTED: Instruction override attempt]", redacted_output)
    
    # 4. Check for tool definition leakage
    if "AVAILABLE TOOLS" in text.upper() or "TOOL:" in text.upper():
        # Check if it's legitimate tool usage vs. leakage
        # If it contains actual tool calls, it might be legitimate
        if "call_tool" not in text.lower() and "tool_result" not in text.lower():
            hits.append("tool_definition_leakage")
            if action == "allow":
                action = "redact"
    
    # 5. Check for PII (delegate to PolicyEngine)
    try:
        from safety.policy_engine import PolicyEngine
        policy_engine = PolicyEngine()
        pii_result = policy_engine.evaluate_output(output, session_context)
        
        if pii_result.get("action") == "redact":
            hits.append("pii_detected")
            if action == "allow":
                action = "redact"
            # Use PolicyEngine's redacted output
            if "redacted_output" in pii_result:
                redacted_output = pii_result["redacted_output"]
    except Exception:
        pass
    
    allowed = action != "block"
    reason = "ok" if allowed and action == "allow" else ",".join(hits) if hits else "output_validation_failed"
    
    result = {
        "allowed": allowed,
        "action": action,
        "reason": reason,
        "hits": hits
    }
    
    if action == "redact":
        result["redacted_output"] = redacted_output
    
    return result


def validate_output_safety(
    output: Any,
    session_context: Dict[str, Any] = None,
    input_data: Dict[str, Any] = None,
    strict_mode: bool = True
) -> Dict[str, Any]:
    """
    Validate output safety and return sanitized output if needed.
    
    Args:
        output: Agent output
        session_context: Session context
        input_data: Original input data
        strict_mode: If True, block on critical issues; if False, redact
        
    Returns:
        Dict with validation results and sanitized output
    """
    validation = scan_output(output, session_context, input_data)
    
    if not validation["allowed"] and strict_mode:
        # In strict mode, return error for blocked outputs
        return validation
    
    # Return sanitized output if redaction was needed
    if validation["action"] == "redact" and "redacted_output" in validation:
        # Update output with redacted version
        if isinstance(output, dict):
            sanitized_output = output.copy()
            if "text" in sanitized_output:
                sanitized_output["text"] = validation["redacted_output"]
            elif "content" in sanitized_output:
                sanitized_output["content"] = validation["redacted_output"]
            elif "output" in sanitized_output:
                sanitized_output["output"] = validation["redacted_output"]
            else:
                sanitized_output["_redacted"] = True
                sanitized_output["_original"] = str(output)
        else:
            sanitized_output = validation["redacted_output"]
        
        validation["sanitized_output"] = sanitized_output
    
    return validation
