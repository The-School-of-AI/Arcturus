"""
agents/department_loader.py

Loads pre-built department configurations from agents/departments/*.yaml.
Each department defines a set of agent roles that SwarmRunner can pre-spawn.
"""

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_DEPARTMENTS_DIR = Path(__file__).parent / "departments"

AVAILABLE_DEPARTMENTS = ["research", "engineering", "content", "business"]


def load_department(name: str) -> dict[str, Any]:
    """
    Load a department configuration by name.

    Args:
        name: One of "research", "engineering", "content", "business"

    Returns:
        Department config dict with keys: name, description, agents

    Raises:
        FileNotFoundError: If the department YAML file does not exist.
        ValueError: If the department name is not recognised.
    """
    name = name.lower().strip()
    if name not in AVAILABLE_DEPARTMENTS:
        raise ValueError(
            f"Unknown department '{name}'. "
            f"Available: {AVAILABLE_DEPARTMENTS}"
        )

    config_path = _DEPARTMENTS_DIR / f"{name}.yaml"
    if not config_path.exists():
        raise FileNotFoundError(
            f"Department config not found: {config_path}"
        )

    with config_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    logger.info(
        f"Loaded department '{config['name']}' "
        f"with {len(config.get('agents', []))} agents."
    )
    return config


def get_department_roles(name: str) -> list[str]:
    """
    Convenience helper — returns just the list of role names for a department.

    Example:
        >>> get_department_roles("research")
        ["web_researcher", "academic_researcher", "data_analyst"]
    """
    config = load_department(name)
    return [agent["role"] for agent in config.get("agents", [])]


def list_departments() -> list[str]:
    """Returns names of all available departments."""
    return AVAILABLE_DEPARTMENTS
