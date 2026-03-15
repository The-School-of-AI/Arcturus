"""
Instruction hierarchy enforcement: system > tool > user priority validation.

This module ensures that user input cannot override system instructions or tool definitions.
"""
import re
from typing import Dict, Any, Tuple, List


# Patterns that indicate attempts to override system instructions
OVERRIDE_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|all|system|developer)\s+instructions?",
    r"disregard\s+(?:all\s+)?(?:previous|prior|all|system|developer)\s+instructions?",
    r"forget\s+(?:all\s+)?(?:previous|prior|all|system|developer)\s+instructions?",
    r"override\s+(?:all\s+)?(?:previous|prior|all|system|developer)\s+instructions?",
    r"replace\s+(?:all\s+)?(?:previous|prior|all|system|developer)\s+instructions?",
    r"you\s+are\s+now\s+.*\s+assistant",
    r"new\s+instructions?:",
    r"follow\s+these\s+new\s+instructions",
    r"system\s+prompt:",
    r"developer\s+prompt:",
    r"ignore\s+the\s+above",
    r"disregard\s+the\s+above",
]

OVERRIDE_REGEX = re.compile("|".join(f"(?:{p})" for p in OVERRIDE_PATTERNS), re.I)

# Patterns that indicate attempts to modify tool definitions
TOOL_OVERRIDE_PATTERNS = [
    r"new\s+tool:",
    r"add\s+tool:",
    r"modify\s+tool:",
    r"tool\s+definition:",
    r"available\s+tools?:",
    r"you\s+can\s+now\s+use",
]

TOOL_OVERRIDE_REGEX = re.compile("|".join(f"(?:{p})" for p in TOOL_OVERRIDE_PATTERNS), re.I)


def sanitize_user_prompt(user_prompt: str) -> Tuple[str, List[str]]:
    """
    Sanitize user prompt to remove attempts to override system instructions.
    
    Args:
        user_prompt: The user-provided prompt text
        
    Returns:
        Tuple of (sanitized_prompt, detected_violations)
    """
    violations = []
    sanitized = user_prompt
    
    # Check for instruction override attempts
    if OVERRIDE_REGEX.search(user_prompt):
        violations.append("instruction_override_attempt")
        # Remove the violating patterns (replace with placeholder)
        sanitized = OVERRIDE_REGEX.sub("[REDACTED: Instruction override attempt]", sanitized)
    
    # Check for tool override attempts
    if TOOL_OVERRIDE_REGEX.search(user_prompt):
        violations.append("tool_override_attempt")
        sanitized = TOOL_OVERRIDE_REGEX.sub("[REDACTED: Tool override attempt]", sanitized)
    
    # Check for obfuscated attempts (character substitution)
    collapsed = re.sub(r"[\W_]+", "", user_prompt).lower()
    obfuscated_patterns = [
        ("ignorepreviousinstructions", "ignore previous instructions"),
        ("disregardpriorinstructions", "disregard prior instructions"),
        ("ignoreallinstructions", "ignore all instructions"),
    ]
    
    for obfuscated, original in obfuscated_patterns:
        if obfuscated in collapsed:
            violations.append(f"obfuscated_override_attempt:{original}")
            # Note: We can't easily remove obfuscated patterns, so we flag them
    
    return sanitized, violations


def validate_prompt_hierarchy(
    system_prompt: str,
    tool_prompt: str,
    user_prompt: str
) -> Dict[str, Any]:
    """
    Validate that the prompt hierarchy is maintained (system > tool > user).
    
    Args:
        system_prompt: System-level instructions
        tool_prompt: Tool definitions
        user_prompt: User input
        
    Returns:
        Dict with validation results:
        - valid: bool
        - violations: List of violation types
        - sanitized_user_prompt: Cleaned user prompt
    """
    violations = []
    
    # Sanitize user prompt
    sanitized_user, user_violations = sanitize_user_prompt(user_prompt)
    violations.extend(user_violations)
    
    # Check if user prompt contains system prompt markers (potential leakage)
    if "[INTERNAL_TOKEN:" in user_prompt or "SYSTEM INSTRUCTIONS" in user_prompt:
        violations.append("system_prompt_leakage_attempt")
    
    # Check if user prompt attempts to inject tool definitions
    if "AVAILABLE TOOLS" in user_prompt.upper() or "TOOL:" in user_prompt.upper():
        violations.append("tool_injection_attempt")
    
    # Validate that system prompt is not empty
    if not system_prompt or len(system_prompt.strip()) < 10:
        violations.append("empty_system_prompt")
    
    valid = len(violations) == 0
    
    return {
        "valid": valid,
        "violations": violations,
        "sanitized_user_prompt": sanitized_user,
        "action": "block" if not valid else "allow"
    }


def enforce_hierarchy(
    system_prompt: str,
    tool_prompt: str,
    user_prompt: str,
    strict_mode: bool = True
) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Enforce instruction hierarchy by sanitizing and validating prompts.
    
    Args:
        system_prompt: System-level instructions
        tool_prompt: Tool definitions
        user_prompt: User input
        strict_mode: If True, block on violations; if False, sanitize and continue
        
    Returns:
        Tuple of (sanitized_system, sanitized_tool, sanitized_user, validation_result)
    """
    validation = validate_prompt_hierarchy(system_prompt, tool_prompt, user_prompt)
    
    if not validation["valid"]:
        if strict_mode:
            # In strict mode, return error
            return system_prompt, tool_prompt, user_prompt, validation
        
        # In non-strict mode, use sanitized version
        user_prompt = validation["sanitized_user_prompt"]
        validation["action"] = "sanitize"
    
    return system_prompt, tool_prompt, user_prompt, validation
