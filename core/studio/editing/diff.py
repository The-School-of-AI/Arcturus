"""Type-aware diff computation for Forge content trees.

Compares two content tree dicts and produces structured diff output
grouped by artifact-type-aware containers (slides / sections / tabs).
"""

from typing import Any, Dict, List, Optional


def compute_revision_diff(
    artifact_type: str,
    before_tree: dict[str, Any],
    after_tree: dict[str, Any],
    max_paths: int = 50,
) -> dict[str, Any]:
    """Compute a structured diff between two content trees.

    Returns:
        {
            "stats": {"paths_changed": N, "slides_changed": N, ...},
            "highlights": [{"kind": "slide", "slide_index": 3, "change": "Updated title"}],
            "paths": [{"path": "slides[2].title", "before": "old", "after": "new"}],
        }
    """
    paths: list[dict[str, Any]] = []
    _collect_changed_paths(before_tree, after_tree, "", paths, max_paths)

    # Group by container
    slides_changed: set = set()
    sections_changed: set = set()
    tabs_changed: set = set()
    highlights: list[dict[str, Any]] = []

    for p in paths:
        path_str = p["path"]
        if artifact_type == "slides":
            idx = _extract_slide_index(path_str)
            if idx is not None and idx not in slides_changed:
                slides_changed.add(idx)
                change_desc = _describe_slide_change(before_tree, after_tree, idx)
                highlights.append({"kind": "slide", "slide_index": idx + 1, "change": change_desc})
        elif artifact_type == "document":
            sec_id = _extract_section_id(path_str, before_tree, after_tree)
            if sec_id and sec_id not in sections_changed:
                sections_changed.add(sec_id)
                highlights.append({"kind": "section", "section_id": sec_id, "change": _describe_section_change(sec_id)})
        elif artifact_type == "sheet":
            tab_name = _extract_tab_name(path_str, before_tree, after_tree)
            if tab_name and tab_name not in tabs_changed:
                tabs_changed.add(tab_name)
                highlights.append({"kind": "tab", "tab_name": tab_name, "change": f"Modified tab '{tab_name}'"})

    # Also detect top-level changes not inside containers
    for p in paths:
        path_str = p["path"]
        if not any(path_str.startswith(prefix) for prefix in ("slides[", "sections[", "tabs[")):
            if not any(h.get("kind") == "metadata" for h in highlights):
                highlights.append({"kind": "metadata", "change": "Updated metadata or top-level fields"})
                break

    stats = {
        "paths_changed": len(paths),
        "slides_changed": len(slides_changed),
        "sections_changed": len(sections_changed),
        "tabs_changed": len(tabs_changed),
    }

    return {"stats": stats, "highlights": highlights, "paths": paths}


def summarize_diff_highlights(highlights: list[dict[str, Any]]) -> str:
    """Generate human-readable change_summary text from diff highlights."""
    if not highlights:
        return "No changes detected"

    parts = []
    for h in highlights:
        kind = h.get("kind", "")
        change = h.get("change", "Modified")
        if kind == "slide":
            parts.append(f"Slide {h.get('slide_index', '?')}: {change}")
        elif kind == "section":
            parts.append(f"Section {h.get('section_id', '?')}: {change}")
        elif kind == "tab":
            parts.append(f"Tab '{h.get('tab_name', '?')}': {change}")
        else:
            parts.append(change)

    return "; ".join(parts)


# --- Internal helpers ---

def _collect_changed_paths(
    before: Any,
    after: Any,
    prefix: str,
    paths: list[dict[str, Any]],
    max_paths: int,
) -> None:
    """Recursively walk two trees, collecting changed leaf paths."""
    if len(paths) >= max_paths:
        return

    if before == after:
        return

    # Both are dicts — compare keys
    if isinstance(before, dict) and isinstance(after, dict):
        all_keys = set(before.keys()) | set(after.keys())
        for key in sorted(all_keys):
            child_path = f"{prefix}.{key}" if prefix else key
            b_val = before.get(key)
            a_val = after.get(key)
            if b_val != a_val:
                if isinstance(b_val, (dict, list)) and isinstance(a_val, (dict, list)):
                    _collect_changed_paths(b_val, a_val, child_path, paths, max_paths)
                else:
                    paths.append({"path": child_path, "before": _summarize(b_val), "after": _summarize(a_val)})
                if len(paths) >= max_paths:
                    return
        return

    # Both are lists — compare element by element
    if isinstance(before, list) and isinstance(after, list):
        max_len = max(len(before), len(after))
        for i in range(max_len):
            child_path = f"{prefix}[{i}]"
            b_val = before[i] if i < len(before) else None
            a_val = after[i] if i < len(after) else None
            if b_val != a_val:
                if isinstance(b_val, (dict, list)) and isinstance(a_val, (dict, list)):
                    _collect_changed_paths(b_val, a_val, child_path, paths, max_paths)
                else:
                    paths.append({"path": child_path, "before": _summarize(b_val), "after": _summarize(a_val)})
            if len(paths) >= max_paths:
                return
        return

    # Leaf-level change
    paths.append({"path": prefix, "before": _summarize(before), "after": _summarize(after)})


def _summarize(value: Any) -> Any:
    """Summarize a value for diff display — truncate long strings."""
    if isinstance(value, str) and len(value) > 100:
        return value[:100] + "..."
    return value


def _extract_slide_index(path: str) -> int | None:
    """Extract 0-based slide index from a path like 'slides[2].title'."""
    if path.startswith("slides["):
        try:
            idx_str = path.split("[")[1].split("]")[0]
            return int(idx_str)
        except (ValueError, IndexError):
            pass
    return None


def _extract_section_id(path: str, before: dict, after: dict) -> str | None:
    """Extract section id from a path like 'sections[0].content'."""
    if path.startswith("sections["):
        try:
            idx_str = path.split("[")[1].split("]")[0]
            idx = int(idx_str)
            after_sections = after.get("sections", [])
            before_sections = before.get("sections", [])
            sections = after_sections if idx < len(after_sections) else before_sections
            if idx < len(sections):
                return sections[idx].get("id", f"section_{idx}")
        except (ValueError, IndexError):
            pass
    return None


def _extract_tab_name(path: str, before: dict, after: dict) -> str | None:
    """Extract tab name from a path like 'tabs[0].headers'."""
    if path.startswith("tabs["):
        try:
            idx_str = path.split("[")[1].split("]")[0]
            idx = int(idx_str)
            after_tabs = after.get("tabs", [])
            before_tabs = before.get("tabs", [])
            tabs = after_tabs if idx < len(after_tabs) else before_tabs
            if idx < len(tabs):
                return tabs[idx].get("name", f"tab_{idx}")
        except (ValueError, IndexError):
            pass
    return None


def _describe_slide_change(before: dict, after: dict, idx: int) -> str:
    """Describe what changed in a slide."""
    before_slides = before.get("slides", [])
    after_slides = after.get("slides", [])

    if idx >= len(before_slides):
        return "Added new slide"
    if idx >= len(after_slides):
        return "Removed slide"

    bs = before_slides[idx]
    as_ = after_slides[idx]

    changes = []
    if bs.get("title") != as_.get("title"):
        changes.append("title")
    if bs.get("elements") != as_.get("elements"):
        changes.append("content")
    if bs.get("speaker_notes") != as_.get("speaker_notes"):
        changes.append("notes")

    return "Updated " + " + ".join(changes) if changes else "Modified"


def _describe_section_change(section_id: str) -> str:
    """Describe what changed in a section."""
    return "Updated section content"
