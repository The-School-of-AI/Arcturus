"""LLM-driven patch planner for Forge edit loop.

Translates a user instruction + content tree into a structured Patch dict.
"""

import json
import logging
import re
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


_ELEMENT_FILTER_PATH_RE = re.compile(
    r'^elements\[\?\(@\.id\s*==\s*["\']([a-zA-Z0-9_-]+)["\']\)\]\.(.+)$'
)


def _find_element_in_tree(content_tree: Dict[str, Any], element_id: str) -> bool:
    """Check whether an element_id exists in any slide of the content tree."""
    for slide in content_tree.get("slides", []):
        for el in slide.get("elements", []):
            if el.get("id") == element_id:
                return True
    return False


def _validate_and_normalize_patch(
    patch_dict: Dict[str, Any], content_tree: Dict[str, Any]
) -> Dict[str, Any]:
    """Validate op paths and canonicalize JSONPath filter expressions.

    If the LLM produced filter paths like ``elements[?(@.id == "e7")].content``,
    rewrite them to use ``slide_element`` targeting with a simple relative path.
    Raises ``ValueError`` for paths that can't be parsed or canonicalized.
    """
    from core.studio.editing.patch_apply import _parse_path

    ops = patch_dict.get("ops", [])
    if not ops:
        return patch_dict

    # Phase 1: detect filter paths and collect canonicalization candidates
    filter_matches: List[tuple] = []  # (op_index, element_id, remainder)
    has_non_filter = False

    for i, op in enumerate(ops):
        path = op.get("path", "")
        m = _ELEMENT_FILTER_PATH_RE.match(path)
        if m:
            filter_matches.append((i, m.group(1), m.group(2)))
        elif "[?(" in path:
            # Filter syntax that doesn't match our safe pattern — reject
            raise ValueError(
                f"JSONPath filter expressions are not supported in path {path!r}. "
                "Use numeric indices (e.g. elements[0]) or target kind 'slide_element' with 'element_id'."
            )
        else:
            has_non_filter = True

    if not filter_matches:
        # No filter paths — just validate all paths parse correctly
        for op in ops:
            _parse_path(op.get("path", ""))
        return patch_dict

    # Phase 2: canonicalize only if ALL ops target the same element and none are mixed
    element_ids = {eid for _, eid, _ in filter_matches}

    if has_non_filter or len(element_ids) > 1:
        paths = [op.get("path", "") for op in ops]
        raise ValueError(
            f"Cannot canonicalize mixed filter/non-filter paths or multiple element ids: {paths}. "
            "Use target kind 'slide_element' with 'element_id' and simple relative paths."
        )

    target_element_id = element_ids.pop()

    # Verify the element exists
    if not _find_element_in_tree(content_tree, target_element_id):
        raise ValueError(
            f"Element id {target_element_id!r} from filter path not found in content tree."
        )

    # Rewrite target and ops
    patch_dict["target"] = {"kind": "slide_element", "element_id": target_element_id}
    for i, _eid, remainder in filter_matches:
        patch_dict["ops"][i]["path"] = remainder

    # Re-validate all rewritten paths
    for op in patch_dict["ops"]:
        _parse_path(op.get("path", ""))

    logger.info(
        "Canonicalized filter paths → slide_element target (element_id=%s)",
        target_element_id,
    )
    return patch_dict


async def plan_patch_repair(
    artifact_type: str,
    instruction: str,
    content_tree: Dict[str, Any],
    failed_patch: Dict[str, Any],
    error_message: str,
) -> Dict[str, Any]:
    """Re-plan a patch after the first one failed during apply.

    Sends the failed patch + error message to the LLM via a repair prompt
    so it can correct the operation (e.g. switch INSERT_AFTER to SET).
    """
    from core.json_parser import parse_llm_json
    from core.model_manager import ModelManager
    from core.studio.prompts import get_edit_repair_prompt

    target_map = build_target_map(artifact_type, content_tree)
    failed_json = json.dumps(failed_patch, indent=2)

    repair_prompt = get_edit_repair_prompt(
        artifact_type, instruction, failed_json, error_message, target_map
    )

    mm = ModelManager()
    raw = await mm.generate_text(repair_prompt)

    try:
        parsed = parse_llm_json(raw)
        patch = Patch(**parsed)
        patch_dict = patch.model_dump(mode="json")
        patch_dict = _validate_and_normalize_patch(patch_dict, content_tree)
        return patch_dict
    except Exception as exc:
        raise ValueError(f"Repair patch failed: {exc}") from exc


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
        patch_dict = patch.model_dump(mode="json")
        patch_dict = _validate_and_normalize_patch(patch_dict, content_tree)
        return patch_dict
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
        patch_dict2 = patch2.model_dump(mode="json")
        patch_dict2 = _validate_and_normalize_patch(patch_dict2, content_tree)
        return patch_dict2
    except Exception as second_error:
        raise ValueError(
            f"Failed to plan patch after retry. "
            f"First error: {first_error_msg}. Second error: {second_error}"
        ) from second_error
