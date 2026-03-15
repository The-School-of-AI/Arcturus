"""Forge editing module — chat-driven iterative editing for Slides/Docs/Sheets."""

from core.studio.editing.diff import compute_revision_diff, summarize_diff_highlights
from core.studio.editing.patch_apply import apply_patch_to_content_tree
from core.studio.editing.types import (
    Patch,
    PatchOp,
    PatchOpType,
    SectionTarget,
    SlideTarget,
    TabTarget,
)

__all__ = [
    "Patch",
    "PatchOp",
    "PatchOpType",
    "SectionTarget",
    "SlideTarget",
    "TabTarget",
    "apply_patch_to_content_tree",
    "compute_revision_diff",
    "summarize_diff_highlights",
]
