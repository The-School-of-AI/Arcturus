from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field


# === Enums ===

class ArtifactType(str, Enum):
    slides = "slides"
    document = "document"
    sheet = "sheet"


class OutlineStatus(str, Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ExportFormat(str, Enum):
    pptx = "pptx"
    docx = "docx"
    pdf = "pdf"
    html = "html"
    xlsx = "xlsx"
    csv = "csv"


class ExportStatus(str, Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"


class AssetKind(str, Enum):
    image = "image"
    chart = "chart"
    font = "font"
    theme = "theme"


class ChartType(str, Enum):
    bar = "bar"
    line = "line"
    pie = "pie"
    funnel = "funnel"
    scatter = "scatter"


# === Chart Models ===

class ChartSeries(BaseModel):
    name: str
    values: List[float]


class ScatterPoint(BaseModel):
    x: float
    y: float


class ChartSpec(BaseModel):
    chart_type: Optional[ChartType] = None
    title: Optional[str] = None
    categories: List[str] = Field(default_factory=list)
    series: List[ChartSeries] = Field(default_factory=list)
    points: List[ScatterPoint] = Field(default_factory=list)
    x_label: Optional[str] = None
    y_label: Optional[str] = None


# === Content Tree Models ===

class SlideElement(BaseModel):
    id: str
    type: str  # title, subtitle, body, bullet_list, image, chart, code, quote
    content: Any = None


class Slide(BaseModel):
    id: str
    slide_type: str  # title, content, two_column, comparison, timeline, chart, image_text, quote, code, team, agenda, table
    title: Optional[str] = None
    elements: List[SlideElement] = Field(default_factory=list)
    speaker_notes: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    html: Optional[str] = None  # LLM-generated HTML for direct preview rendering


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


# === Sheet Analysis Models ===


class SheetNumericSummary(BaseModel):
    column: str
    count: int
    null_count: int
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    min_val: Optional[float] = None
    max_val: Optional[float] = None


class SheetCorrelation(BaseModel):
    column_a: str
    column_b: str
    pearson_r: float


class SheetTrend(BaseModel):
    column: str
    direction: str  # "up", "down", "flat"
    slope: float


class SheetAnomaly(BaseModel):
    column: str
    row_index: int
    value: float
    z_score: float


class SheetAnalysisReport(BaseModel):
    summary_stats: List[SheetNumericSummary] = Field(default_factory=list)
    correlations: List[SheetCorrelation] = Field(default_factory=list)
    trends: List[SheetTrend] = Field(default_factory=list)
    anomalies: List[SheetAnomaly] = Field(default_factory=list)
    pivot_preview: Optional[Dict[str, Any]] = None
    warnings: List[str] = Field(default_factory=list)


class SheetContentTree(BaseModel):
    workbook_title: str
    tabs: List[SheetTab]
    assumptions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    analysis_report: Optional[SheetAnalysisReport] = None


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


# === Export Models ===

class ExportJob(BaseModel):
    id: str
    artifact_id: str
    format: ExportFormat
    status: ExportStatus = ExportStatus.pending
    output_uri: Optional[str] = None
    file_size_bytes: Optional[int] = None
    validator_results: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class ExportJobSummary(BaseModel):
    id: str
    format: str
    status: str
    created_at: datetime


# === Theme Models ===

class SlideThemeColors(BaseModel):
    primary: str
    secondary: str
    accent: str
    background: str
    text: str
    text_light: str
    title_background: Optional[str] = None


class SlideTheme(BaseModel):
    id: str
    name: str
    colors: SlideThemeColors
    font_heading: str
    font_body: str
    description: Optional[str] = None
    base_theme_id: Optional[str] = None
    variant_seed: Optional[int] = None
    background_style: Optional[str] = None


# === Core Models ===

class Artifact(BaseModel):
    id: str
    type: ArtifactType
    title: str
    created_at: datetime
    updated_at: datetime
    schema_version: str = "1.0"
    model: Optional[str] = None
    creation_prompt: Optional[str] = None
    slide_mode: Optional[str] = None  # "artistic" (default) or "business"
    content_tree: Optional[Dict[str, Any]] = None
    theme_id: Optional[str] = None
    custom_theme: Optional[Dict[str, Any]] = None
    revision_head_id: Optional[str] = None
    outline: Optional[Outline] = None
    exports: List[ExportJobSummary] = Field(default_factory=list)


class Revision(BaseModel):
    id: str
    artifact_id: str
    parent_revision_id: Optional[str] = None
    change_summary: str
    content_tree_snapshot: Dict[str, Any]
    created_at: datetime
    edit_instruction: Optional[str] = Field(default=None, description="User instruction that triggered this edit")
    patch: Optional[Dict[str, Any]] = Field(default=None, description="Patch that was applied to produce this revision")
    diff: Optional[Dict[str, Any]] = Field(default=None, description="Computed diff between previous and current content trees")
    restored_from_revision_id: Optional[str] = Field(default=None, description="If this revision was created by a restore, the source revision ID")


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
