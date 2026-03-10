"""LLM-driven patch planner for Forge edit loop.

Translates a user instruction + content tree into a structured Patch dict.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from core.studio.editing.types import Patch

logger = logging.getLogger(__name__)


def build_target_map(artifact_type: str, content_tree: Dict[str, Any]) -> str:
    """Build a compact target summary for LLM context.

    Gives the LLM a quick reference of available targets (slide ids, section ids, tab names)
    so it can construct valid patches.
    """
    lines: List[str] = []

    if artifact_type == "slides":
        slides = content_tree.get("slides", [])
        lines.append(f"Deck: {content_tree.get('deck_title', 'Untitled')} ({len(slides)} slides)")
        for i, slide in enumerate(slides, 1):
            title = slide.get("title", "Untitled")
            slide_id = slide.get("id", f"s{i}")
            elements = slide.get("elements", [])
            elem_ids = [e.get("id", "?") for e in elements]
            lines.append(f"  Slide {i}: id={slide_id}, title={title!r}, elements=[{', '.join(elem_ids)}]")

    elif artifact_type == "document":
        lines.append(f"Document: {content_tree.get('doc_title', 'Untitled')}")
        _build_section_map(content_tree.get("sections", []), lines, indent=2)

    elif artifact_type == "sheet":
        lines.append(f"Workbook: {content_tree.get('workbook_title', 'Untitled')}")
        tabs = content_tree.get("tabs", [])
        for tab in tabs:
            name = tab.get("name", "Unnamed")
            headers = tab.get("headers", [])
            row_count = len(tab.get("rows", []))
            lines.append(f"  Tab: {name!r}, headers={headers}, rows={row_count}")

    return "\n".join(lines)


def _build_section_map(sections: List[Dict], lines: List[str], indent: int = 2) -> None:
    """Recursively build section map lines."""
    for section in sections:
        sec_id = section.get("id", "?")
        heading = section.get("heading", "Untitled")
        level = section.get("level", 1)
        prefix = " " * indent
        lines.append(f"{prefix}Section: id={sec_id}, level={level}, heading={heading!r}")
        _build_section_map(section.get("subsections", []), lines, indent + 2)


async def plan_patch(
    artifact_type: str,
    instruction: str,
    content_tree: Dict[str, Any],
    outline: Optional[Dict[str, Any]] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Call LLM to plan a patch from a user instruction.

    Returns a parsed Patch dict. Retries once on parse/validation failure.
    """
    from core.json_parser import parse_llm_json
    from core.model_manager import ModelManager
    from core.studio.prompts import get_edit_prompt, get_edit_repair_prompt

    target_map = build_target_map(artifact_type, content_tree)
    content_json = json.dumps(content_tree, indent=2)

    prompt = get_edit_prompt(artifact_type, instruction, content_json, target_map)

    mm = ModelManager()
    raw = await mm.generate_text(prompt)

    # First attempt
    first_error_msg = ""
    try:
        parsed = parse_llm_json(raw)
        patch = Patch(**parsed)
        return patch.model_dump(mode="json")
    except Exception as exc:
        first_error_msg = str(exc)
        logger.warning("First patch parse failed: %s — retrying with repair prompt", exc)

    # Retry with repair prompt
    repair_prompt = get_edit_repair_prompt(
        artifact_type, instruction, raw, first_error_msg, target_map
    )
    raw2 = await mm.generate_text(repair_prompt)

    try:
        parsed2 = parse_llm_json(raw2)
        patch2 = Patch(**parsed2)
        return patch2.model_dump(mode="json")
    except Exception as second_error:
        raise ValueError(
            f"Failed to plan patch after retry. "
            f"First error: {first_error_msg}. Second error: {second_error}"
        ) from second_error
