from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, model_validator


# === Enums ===

class ArtifactType(str, Enum):
    slides = "slides"
    document = "document"
    sheet = "sheet"


class OutlineStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AssetKind(str, Enum):
    image = "image"
    chart = "chart"
    font = "font"
    theme = "theme"


# === Content Tree Models ===

class SlideElement(BaseModel):
    id: str
    type: str  # title, subtitle, body, bullet_list, image, chart, code, quote
    content: Any = None


class Slide(BaseModel):
    id: str
    slide_type: str  # title, content, two_column, comparison, timeline, chart, image_text, quote, code, team
    title: Optional[str] = None
    elements: List[SlideElement] = Field(default_factory=list)
    speaker_notes: Optional[str] = None


class SlidesContentTree(BaseModel):
    deck_title: str
    subtitle: Optional[str] = None
    slides: List[Slide]
    metadata: Optional[Dict[str, Any]] = None


class DocumentSection(BaseModel):
    id: str
    heading: str
    level: int = 1
    content: Optional[str] = None
    subsections: List["DocumentSection"] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)


class DocumentContentTree(BaseModel):
    doc_title: str
    doc_type: str  # technical_spec, business_plan, research_paper, blog_post, report, proposal, white_paper
    abstract: Optional[str] = None
    sections: List[DocumentSection]
    bibliography: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None


class SheetTab(BaseModel):
    id: str
    name: str
    headers: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    formulas: Dict[str, str] = Field(default_factory=dict)
    column_widths: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_column_widths(self):
        if self.column_widths and self.headers and len(self.column_widths) != len(self.headers):
            raise ValueError(
                f"column_widths length ({len(self.column_widths)}) "
                f"must match headers length ({len(self.headers)})"
            )
        return self


class SheetContentTree(BaseModel):
    workbook_title: str
    tabs: List[SheetTab]
    assumptions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# === Outline Models ===

class OutlineItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    children: List["OutlineItem"] = Field(default_factory=list)


class Outline(BaseModel):
    artifact_type: ArtifactType
    title: str
    items: List[OutlineItem]
    status: OutlineStatus = OutlineStatus.pending
    parameters: Dict[str, Any] = Field(default_factory=dict)


# === Core Models ===

class Artifact(BaseModel):
    id: str
    type: ArtifactType
    title: str
    created_at: datetime
    updated_at: datetime
    schema_version: str = "1.0"
    content_tree: Optional[Dict[str, Any]] = None
    theme_id: Optional[str] = None
    revision_head_id: Optional[str] = None
    outline: Optional[Outline] = None


class Revision(BaseModel):
    id: str
    artifact_id: str
    parent_revision_id: Optional[str] = None
    change_summary: str
    content_tree_snapshot: Dict[str, Any]
    created_at: datetime


class Asset(BaseModel):
    id: str
    artifact_id: str
    kind: AssetKind
    uri: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Resolve forward references for recursive models
DocumentSection.model_rebuild()
OutlineItem.model_rebuild()


# === Validation Helpers ===

ContentTree = Union[SlidesContentTree, DocumentContentTree, SheetContentTree]

_CONTENT_TREE_MAP = {
    ArtifactType.slides: SlidesContentTree,
    ArtifactType.document: DocumentContentTree,
    ArtifactType.sheet: SheetContentTree,
}


def validate_content_tree(artifact_type: ArtifactType, data: Dict[str, Any]) -> ContentTree:
    """Validate raw dict against the correct content tree model for the given type."""
    model_cls = _CONTENT_TREE_MAP.get(artifact_type)
    if model_cls is None:
        raise ValueError(f"Unknown artifact type: {artifact_type}")
    return model_cls(**data)


def validate_artifact(data: Dict[str, Any]) -> Artifact:
    """Validate raw dict against the Artifact model."""
    return Artifact(**data)
