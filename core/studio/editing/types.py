"""Pydantic models for the Forge edit loop: patches, targets, and operations."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field


class PatchOpType(str, Enum):
    """Supported patch operation types."""

    SET = "SET"
    INSERT_AFTER = "INSERT_AFTER"
    DELETE = "DELETE"


class PatchOp(BaseModel):
    """A single mutation operation within a patch."""

    op: PatchOpType
    path: str = Field(..., description="Dot-notation path with numeric indices (e.g. 'title', 'elements[1].content')")
    value: Any = Field(default=None, description="New value for SET operations")
    item: Any = Field(default=None, description="Item to insert for INSERT_AFTER operations")
    id_key: Optional[str] = Field(default=None, description="Key used for idempotency checks on INSERT_AFTER")


class SlideTarget(BaseModel):
    """Target specifier for slide-based patches."""

    kind: Literal["deck", "slide_index", "slide_id", "slide_element"]
    index: Optional[int] = Field(default=None, description="1-based slide index")
    id: Optional[str] = Field(default=None, description="Slide id (e.g. 's3')")
    element_id: Optional[str] = Field(default=None, description="Element id within a slide")


class SectionTarget(BaseModel):
    """Target specifier for document section patches."""

    kind: Literal["section_id", "heading_contains"]
    id: Optional[str] = Field(default=None, description="Section id (e.g. 'sec1')")
    text: Optional[str] = Field(default=None, description="Heading text substring to match")


class TabTarget(BaseModel):
    """Target specifier for sheet tab patches."""

    kind: Literal["tab_name", "cell_range"]
    name: Optional[str] = Field(default=None, description="Tab name to target")
    tab_name: Optional[str] = Field(default=None, description="Tab name (alias for name)")
    a1: Optional[str] = Field(default=None, description="A1-style cell range (e.g. 'B2:D10')")


Target = Union[SlideTarget, SectionTarget, TabTarget]


class Patch(BaseModel):
    """A complete patch envelope describing one edit operation."""

    artifact_type: Literal["slides", "document", "sheet"]
    target: Dict[str, Any] = Field(..., description="Target specifier dict (parsed into SlideTarget/SectionTarget/TabTarget)")
    ops: List[PatchOp] = Field(..., min_length=1, description="List of operations to apply")
    summary: str = Field(..., description="Human-readable summary of what this patch does")
