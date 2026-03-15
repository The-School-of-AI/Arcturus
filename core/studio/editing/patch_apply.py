"""Deterministic patch engine for Forge content trees.

Applies a patch (target + ops) to a content tree dict, producing a new tree.
Guarantees: deep-copy-first, idempotent ops, post-apply validation + normalization.
"""

import copy
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# --- Path parsing ---

_PATH_SEGMENT_RE = re.compile(r"([a-zA-Z_][a-zA-Z0-9_]*)((?:\[\d+\])*)")


def _parse_path(path: str) -> List[Tuple[str, Optional[int]]]:
    """Parse a JSONPath-like string into traversal steps.

    Examples:
        "title"            -> [("title", None)]
        "elements[1]"      -> [("elements", 1)]
        "slides[2].title"  -> [("slides", 2), ("title", None)]
        "rows[0][1]"       -> [("rows", 0), ("__idx__", 1)]
    """
    if "[?(" in path:
        raise ValueError(
            f"JSONPath filter expressions are not supported in path {path!r}. "
            "Use numeric indices (e.g. elements[0]) or target kind 'slide_element' with 'element_id'."
        )
    segments = []
    for part in path.split("."):
        m = _PATH_SEGMENT_RE.fullmatch(part)
        if not m:
            raise ValueError(f"Invalid path segment: {part!r} in path {path!r}")
        key = m.group(1)
        brackets = m.group(2)  # e.g. "[0][1]" or "" or "[2]"
        if not brackets:
            segments.append((key, None))
        else:
            indices = [int(x) for x in re.findall(r"\[(\d+)\]", brackets)]
            # First index is on the key itself
            segments.append((key, indices[0]))
            # Additional indices become separate traversal steps
            for extra_idx in indices[1:]:
                segments.append(("__idx__", extra_idx))
    return segments


def _navigate(tree: Any, segments: List[Tuple[str, Optional[int]]], create: bool = False) -> Tuple[Any, str | int]:
    """Navigate a tree to the parent of the final path segment.

    Returns (parent_container, final_key_or_index) so the caller can
    get/set/delete the target.
    """
    current = tree
    for _step, (key, idx) in enumerate(segments[:-1]):
        if key == "__idx__":
            # Chained index on a list
            if not isinstance(current, list):
                raise ValueError(f"Expected list for chained index but got {type(current).__name__}")
            if idx is None or idx < 0 or idx >= len(current):
                raise ValueError(f"Chained index {idx} out of range (length {len(current)})")
            current = current[idx]
            continue
        if isinstance(current, dict):
            if key not in current and create:
                current[key] = {} if idx is None else []
            current = current[key]
        else:
            raise ValueError(f"Cannot traverse into non-dict at path segment {key!r}")
        if idx is not None:
            if not isinstance(current, list):
                raise ValueError(f"Expected list at {key!r} but got {type(current).__name__}")
            if idx < 0 or idx >= len(current):
                raise ValueError(f"Index {idx} out of range for {key!r} (length {len(current)})")
            current = current[idx]

    # Final segment
    final_key, final_idx = segments[-1]
    if final_key == "__idx__":
        # Final step is a chained index
        if not isinstance(current, list):
            raise ValueError(f"Expected list for final chained index but got {type(current).__name__}")
        return current, final_idx
    if isinstance(current, dict):
        if final_idx is not None:
            container = current.get(final_key)
            if container is None:
                raise ValueError(f"Key {final_key!r} not found for indexed access")
            return container, final_idx
        return current, final_key
    raise ValueError(f"Cannot access {final_key!r} on {type(current).__name__}")


# --- Target resolution ---

def _resolve_target(artifact_type: str, tree: Dict[str, Any], target: Dict[str, Any]) -> Any:
    """Resolve a target dict to the subtree anchor node."""
    kind = target.get("kind")
    if not kind:
        raise ValueError("Target must include a 'kind' field")

    if artifact_type == "slides":
        slides = tree.get("slides", [])
        if kind == "deck":
            # Deck-level target — ops apply to the top-level tree (e.g. deck_title)
            return tree
        elif kind == "slide_index":
            index = target.get("index")
            if index is None:
                raise ValueError("slide_index target requires 'index'")
            # 1-based to 0-based
            idx = index - 1
            if idx < 0 or idx >= len(slides):
                candidates = [f"slide_index={i+1} ({s.get('title', 'untitled')})" for i, s in enumerate(slides)]
                raise ValueError(
                    f"Slide index {index} out of range (1-{len(slides)}). "
                    f"Available: {', '.join(candidates[:5])}"
                )
            return slides[idx]
        elif kind == "slide_id":
            slide_id = target.get("id")
            for s in slides:
                if s.get("id") == slide_id:
                    return s
            candidates = [f"{s.get('id')} ({s.get('title', 'untitled')})" for s in slides]
            raise ValueError(f"Slide id {slide_id!r} not found. Available: {', '.join(candidates[:5])}")
        elif kind == "slide_element":
            element_id = target.get("element_id")
            for s in slides:
                for e in s.get("elements", []):
                    if e.get("id") == element_id:
                        return e
            raise ValueError(f"Element id {element_id!r} not found in any slide")
        else:
            raise ValueError(f"Unknown slide target kind: {kind!r}")

    elif artifact_type == "document":
        if kind == "section_id":
            section_id = target.get("id")
            result = _find_section_by_id(tree.get("sections", []), section_id)
            if result is None:
                candidates = _collect_section_ids(tree.get("sections", []))
                raise ValueError(f"Section id {section_id!r} not found. Available: {', '.join(candidates[:10])}")
            return result
        elif kind == "heading_contains":
            text = target.get("text", "")
            result = _find_section_by_heading(tree.get("sections", []), text)
            if result is None:
                candidates = _collect_section_headings(tree.get("sections", []))
                raise ValueError(f"No section heading contains {text!r}. Available: {', '.join(candidates[:10])}")
            return result
        else:
            raise ValueError(f"Unknown document target kind: {kind!r}")

    elif artifact_type == "sheet":
        tabs = tree.get("tabs", [])
        if kind == "tab_name":
            name = target.get("name") or target.get("tab_name")
            for t in tabs:
                if t.get("name") == name:
                    return t
            candidates = [t.get("name", "unnamed") for t in tabs]
            raise ValueError(f"Tab {name!r} not found. Available: {', '.join(candidates)}")
        elif kind == "cell_range":
            tab_name = target.get("tab_name") or target.get("name")
            for t in tabs:
                if t.get("name") == tab_name:
                    return t
            candidates = [t.get("name", "unnamed") for t in tabs]
            raise ValueError(f"Tab {tab_name!r} not found for cell_range. Available: {', '.join(candidates)}")
        else:
            raise ValueError(f"Unknown sheet target kind: {kind!r}")

    else:
        raise ValueError(f"Unknown artifact type: {artifact_type!r}")


def _find_section_by_id(sections: List[Dict], section_id: str) -> Optional[Dict]:
    for s in sections:
        if s.get("id") == section_id:
            return s
        found = _find_section_by_id(s.get("subsections", []), section_id)
        if found:
            return found
    return None


def _find_section_by_heading(sections: List[Dict], text: str) -> Optional[Dict]:
    text_lower = text.lower()
    for s in sections:
        if text_lower in (s.get("heading", "")).lower():
            return s
        found = _find_section_by_heading(s.get("subsections", []), text)
        if found:
            return found
    return None


def _collect_section_ids(sections: List[Dict]) -> List[str]:
    ids = []
    for s in sections:
        if s.get("id"):
            ids.append(s["id"])
        ids.extend(_collect_section_ids(s.get("subsections", [])))
    return ids


def _collect_section_headings(sections: List[Dict]) -> List[str]:
    headings = []
    for s in sections:
        if s.get("heading"):
            headings.append(s["heading"])
        headings.extend(_collect_section_headings(s.get("subsections", [])))
    return headings


# --- Op execution ---

def _apply_set(subtree: Any, segments: List[Tuple[str, Optional[int]]], value: Any) -> Optional[str]:
    """Apply a SET operation. Returns a warning string if no-op."""
    parent, key = _navigate(subtree, segments)
    if isinstance(parent, dict):
        if parent.get(key) == value:
            return f"SET no-op: {key!r} already equals the target value"
        parent[key] = value
    elif isinstance(parent, list):
        if not isinstance(key, int):
            raise ValueError(f"Expected integer index for list, got {key!r}")
        if key < 0 or key >= len(parent):
            raise ValueError(f"List index {key} out of range (length {len(parent)})")
        if parent[key] == value:
            return f"SET no-op: index {key} already equals the target value"
        parent[key] = value
    else:
        raise ValueError(f"Cannot SET on {type(parent).__name__}")
    return None


def _apply_insert_after(subtree: Any, segments: List[Tuple[str, Optional[int]]], item: Any, id_key: Optional[str]) -> Optional[str]:
    """Apply an INSERT_AFTER operation. Returns a warning string if no-op."""
    parent, key = _navigate(subtree, segments)
    if isinstance(parent, dict):
        target_list = parent.get(key)
    elif isinstance(parent, list) and isinstance(key, int):
        target_list = parent
    else:
        target_list = None

    if not isinstance(target_list, list):
        raise ValueError(f"INSERT_AFTER target must be a list, got {type(target_list).__name__ if target_list else 'None'}")

    # Idempotency check: if id_key is set and item with that key already exists, skip
    if id_key and isinstance(item, dict) and id_key in item:
        for existing in target_list:
            if isinstance(existing, dict) and existing.get(id_key) == item[id_key]:
                return f"INSERT_AFTER no-op: item with {id_key}={item[id_key]!r} already exists"

    target_list.append(item)
    return None


def _apply_delete(subtree: Any, segments: List[Tuple[str, Optional[int]]]) -> Optional[str]:
    """Apply a DELETE operation. Returns a warning string if no-op."""
    try:
        parent, key = _navigate(subtree, segments)
    except (ValueError, KeyError, IndexError):
        path_str = ".".join(f"{k}[{i}]" if i is not None else k for k, i in segments)
        return f"DELETE no-op: path {path_str!r} not found"

    if isinstance(parent, dict):
        if key not in parent:
            return f"DELETE no-op: key {key!r} not found"
        del parent[key]
    elif isinstance(parent, list):
        if not isinstance(key, int):
            return f"DELETE no-op: expected integer index, got {key!r}"
        if key < 0 or key >= len(parent):
            return f"DELETE no-op: index {key} out of range (length {len(parent)})"
        parent.pop(key)
    else:
        return f"DELETE no-op: cannot delete from {type(parent).__name__}"
    return None


# --- LLM value coercion ---

# Element types whose `content` field is a plain string.
# chart, table, stat_callout have dict/list content — never coerce those.
_STRING_CONTENT_ELEMENT_TYPES = frozenset({
    "title", "subtitle", "body", "kicker", "takeaway",
    "image", "quote", "code", "source_citation", "tag_badge",
})

def _extract_string_from_dict(value: Any) -> Optional[str]:
    """Try to extract a string from a dict the LLM produced for a string field.

    Common LLM patterns:
      {"text": "actual value", "text_color": "blue"}
      {"value": "actual value"}
      {"content": "actual value"}
    """
    if not isinstance(value, dict):
        return None
    for key in ("text", "value", "content"):
        if key in value and isinstance(value[key], str):
            return value[key]
    return None


def _coerce_llm_value_types(artifact_type: str, tree: Dict[str, Any]) -> List[str]:
    """Fix common LLM type mistakes in-place: dict-for-string, etc.

    The LLM sometimes "enriches" plain string fields into dicts like
    {"text": "...", "text_color": "blue"}.  This coercion extracts the
    string before Pydantic validation rejects the tree.

    Returns a list of warnings for every field that was coerced.
    """
    coerce_warnings: List[str] = []

    if artifact_type == "slides":
        # Top-level string fields
        for key in ("deck_title", "subtitle"):
            if isinstance(tree.get(key), dict):
                extracted = _extract_string_from_dict(tree[key])
                if extracted is not None:
                    coerce_warnings.append(f"Coerced {key} from dict to string")
                    tree[key] = extracted

        # Per-slide string fields
        for i, slide in enumerate(tree.get("slides", [])):
            if not isinstance(slide, dict):
                continue
            for key in ("title", "speaker_notes"):
                if isinstance(slide.get(key), dict):
                    extracted = _extract_string_from_dict(slide[key])
                    if extracted is not None:
                        coerce_warnings.append(f"Coerced slides[{i}].{key} from dict to string")
                        slide[key] = extracted
            # Element-level coercion
            for el in slide.get("elements", []):
                if not isinstance(el, dict):
                    continue
                # id and type must be strings
                for key in ("id", "type"):
                    if isinstance(el.get(key), dict):
                        extracted = _extract_string_from_dict(el[key])
                        if extracted is not None:
                            coerce_warnings.append(f"Coerced element {key} from dict to string")
                            el[key] = extracted
                # content: coerce dict→string only for element types where
                # content is expected to be a plain string (not chart/table dicts)
                el_type = el.get("type", "")
                if (
                    el_type in _STRING_CONTENT_ELEMENT_TYPES
                    and isinstance(el.get("content"), dict)
                ):
                    extracted = _extract_string_from_dict(el["content"])
                    if extracted is not None:
                        coerce_warnings.append(
                            f"Coerced element ({el_type}).content from dict to string"
                        )
                        el["content"] = extracted

    elif artifact_type == "document":
        for key in ("doc_title", "abstract", "doc_type"):
            if isinstance(tree.get(key), dict):
                extracted = _extract_string_from_dict(tree[key])
                if extracted is not None:
                    coerce_warnings.append(f"Coerced {key} from dict to string")
                    tree[key] = extracted
        _coerce_document_sections(tree.get("sections", []), coerce_warnings)

    elif artifact_type == "sheet":
        if isinstance(tree.get("workbook_title"), dict):
            extracted = _extract_string_from_dict(tree["workbook_title"])
            if extracted is not None:
                coerce_warnings.append("Coerced workbook_title from dict to string")
                tree["workbook_title"] = extracted

    return coerce_warnings


def _coerce_document_sections(sections: List[Any], warnings: List[str]) -> None:
    """Recursively coerce string fields in document sections."""
    for sec in sections:
        if not isinstance(sec, dict):
            continue
        for key in ("heading", "content", "id"):
            if isinstance(sec.get(key), dict):
                extracted = _extract_string_from_dict(sec[key])
                if extracted is not None:
                    warnings.append(f"Coerced section {key} from dict to string")
                    sec[key] = extracted
        _coerce_document_sections(sec.get("subsections", []), warnings)


# --- Post-apply normalization ---

def _normalize_after_patch(artifact_type: str, tree_dict: Dict[str, Any]) -> Dict[str, Any]:
    """Apply type-specific normalization after patching."""
    if artifact_type == "slides":
        from core.schemas.studio_schema import SlidesContentTree
        from core.studio.slides.generator import enforce_slide_count
        from core.studio.slides.notes import repair_speaker_notes
        model = SlidesContentTree(**tree_dict)
        model = enforce_slide_count(model)
        model = repair_speaker_notes(model)
        return model.model_dump(mode="json")

    elif artifact_type == "document":
        from core.schemas.studio_schema import DocumentContentTree
        from core.studio.documents.generator import normalize_document_content_tree
        model = DocumentContentTree(**tree_dict)
        model = normalize_document_content_tree(model)
        return model.model_dump(mode="json")

    elif artifact_type == "sheet":
        from core.schemas.studio_schema import SheetContentTree
        from core.studio.sheets.generator import normalize_sheet_content_tree
        model = SheetContentTree(**tree_dict)
        model = normalize_sheet_content_tree(model)
        return model.model_dump(mode="json")

    return tree_dict


# --- Main entry point ---

def apply_patch_to_content_tree(
    artifact_type: str,
    content_tree_dict: Dict[str, Any],
    patch: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[str]]:
    """Apply a patch to a content tree dict.

    Args:
        artifact_type: "slides", "document", or "sheet"
        content_tree_dict: The current content tree (will NOT be mutated)
        patch: Patch dict with "target", "ops", and "summary" keys

    Returns:
        (new_content_tree_dict, warnings) — the patched tree and any warning messages

    Raises:
        ValueError: On invalid target, path, or schema-breaking patch
    """
    # 1. Deep copy — never mutate the original
    new_tree = copy.deepcopy(content_tree_dict)
    warnings: List[str] = []

    # 2. Resolve target
    target = patch.get("target", {})
    subtree = _resolve_target(artifact_type, new_tree, target)

    # 3. Apply ops in order
    ops = patch.get("ops", [])
    for op_dict in ops:
        op_type = op_dict.get("op")
        path = op_dict.get("path", "")
        segments = _parse_path(path)

        if op_type == "SET":
            warning = _apply_set(subtree, segments, op_dict.get("value"))
            if warning:
                warnings.append(warning)

        elif op_type == "INSERT_AFTER":
            warning = _apply_insert_after(
                subtree, segments, op_dict.get("item"), op_dict.get("id_key")
            )
            if warning:
                warnings.append(warning)

        elif op_type == "DELETE":
            warning = _apply_delete(subtree, segments)
            if warning:
                warnings.append(warning)

        else:
            raise ValueError(f"Unknown op type: {op_type!r}")

    # 4. Coerce common LLM mistakes (dict-for-string, etc.) before validation
    coerce_warnings = _coerce_llm_value_types(artifact_type, new_tree)
    warnings.extend(coerce_warnings)

    # 5. Post-apply validation
    from core.schemas.studio_schema import ArtifactType, validate_content_tree
    try:
        at = ArtifactType(artifact_type)
        validate_content_tree(at, new_tree)
    except Exception as e:
        raise ValueError(f"Patch produced invalid content tree: {e}") from e

    # 6. Post-apply normalization
    new_tree = _normalize_after_patch(artifact_type, new_tree)

    return new_tree, warnings
