"""Tool hardening helpers: whitelist check + simple sanitization."""
import logging
from typing import Any, Dict


def is_tool_allowed(tool_name: str, config: Dict[str, Any] = None) -> bool:
    if not tool_name:
        return False
    if config and isinstance(config.get("allowed_tools"), (list, tuple)):
        return tool_name in config.get("allowed_tools")
    logging.debug(f"tool_hardening: no whitelist configured, allowing {tool_name}")
    return True

def sanitize_tool_args(args: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(args, dict):
        return args
    sanitized = {}
    for k, v in args.items():
        if isinstance(v, str) and (";" in v or "rm -" in v or "--" in v):
            sanitized[k] = "[REDACTED]"
        else:
            sanitized[k] = v
    return sanitized