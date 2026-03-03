"""Template registry for Spark page templates.

This module manages page templates used by the page generator.
Each template defines the structure, sections, and rendering instructions
for different types of content pages.
"""
from __future__ import annotations

import yaml
from pathlib import Path
from typing import Dict, Any, List

TEMPLATES_DIR = Path(__file__).parent

def load_template(template_name: str) -> Dict[str, Any]:
    """Load a template configuration by name."""
    template_path = TEMPLATES_DIR / f"{template_name}.yaml"
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_name}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def list_templates() -> List[str]:
    """List all available template names."""
    return [p.stem for p in TEMPLATES_DIR.glob("*.yaml")]

def get_template_sections(template_name: str) -> List[str]:
    """Get the section types required for a template."""
    template = load_template(template_name)
    return template.get("sections", [])

def get_template_metadata(template_name: str) -> Dict[str, Any]:
    """Get template metadata like title pattern, description, etc."""
    template = load_template(template_name)
    return template.get("metadata", {})