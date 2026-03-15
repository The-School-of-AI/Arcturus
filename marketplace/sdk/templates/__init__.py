"""
Template registry — maps template names to their subdirectories and metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

TEMPLATES_DIR = Path(__file__).parent


@dataclass(frozen=True)
class TemplateInfo:
    """Metadata for a single skill template."""
    name: str
    description: str
    permissions: List[str]
    directory: Path       # subdirectory inside TEMPLATES_DIR


# Central registry — one entry per template
TEMPLATE_REGISTRY: Dict[str, TemplateInfo] = {
    "default": TemplateInfo(
        name="default",
        description="Minimal scaffold — blank slate for any skill type",
        permissions=[],
        directory=TEMPLATES_DIR,        # root templates dir
    ),
    "prompt_only": TemplateInfo(
        name="prompt_only",
        description="Text-transformation skill — no external calls, no permissions",
        permissions=[],
        directory=TEMPLATES_DIR / "prompt_only",
    ),
    "tool_enabled": TemplateInfo(
        name="tool_enabled",
        description="API-calling skill — declares 'network' permission, uses httpx",
        permissions=["network"],
        directory=TEMPLATES_DIR / "tool_enabled",
    ),
    "agent_based": TemplateInfo(
        name="agent_based",
        description="Orchestrator skill — delegates to other marketplace skills via MarketplaceBridge",
        permissions=[],
        directory=TEMPLATES_DIR / "agent_based",
    ),
}


def get_template(name: str) -> TemplateInfo:
    """Return TemplateInfo for *name*, raising ValueError if unknown."""
    if name not in TEMPLATE_REGISTRY:
        known = ", ".join(f"'{k}'" for k in TEMPLATE_REGISTRY)
        raise ValueError(
            f"Unknown template '{name}'. Available templates: {known}"
        )
    return TEMPLATE_REGISTRY[name]


def list_templates() -> List[TemplateInfo]:
    """Return all registered templates."""
    return list(TEMPLATE_REGISTRY.values())