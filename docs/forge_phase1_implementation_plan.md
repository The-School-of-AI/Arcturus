# Forge Phase 1 — Implementation Plan: Artifact Schema + Outline-First Core (Days 1-5)

## Context

Forge (Project P04) is an AI-powered creation suite that generates professional presentations, documents, and spreadsheets from natural-language prompts. Phase 1 establishes the foundational layer that all subsequent phases build upon:

- **Canonical artifact schemas** for Slides / Docs / Sheets
- **Outline-first generation pipeline**: Prompt -> outline JSON -> approve -> draft content_tree
- **Revision model** with basic diff metadata
- **File-based storage** and **API endpoints**

Currently, no `studio/` directory, router, or schema exists. Export libraries (python-pptx, python-docx, openpyxl, weasyprint) are **not needed** until Phase 2+ and must not be added in Phase 1.

### Scope Boundaries

**In scope:**
- Schema models, validation, and serialization contracts for all three artifact types
- Outline-first orchestration flow (prompt -> outline -> approve -> draft)
- Revision object creation with computed change summaries
- File-based persistence layer
- API endpoints to exercise the full flow end-to-end
- Unit, contract, and pipeline tests

**Out of scope:**
- High-quality Slides/Docs/Sheets generation logic (Phase 2-5)
- Theme systems, charting, image generation, citations (Phase 2-5)
- Export engines: python-pptx, python-docx, openpyxl, WeasyPrint (Phase 2-5)
- Chat-driven edit loop and patch engine (Phase 6)
- Advanced collaboration, locking, or conflict resolution (Phase 6)
- Full frontend WYSIWYG editor components (separate frontend track)
- Preview adapter / renderer stubs (deferred until frontend needs them)

### Codebase Patterns Referenced

| Pattern | Source File | What to Replicate |
|---------|-----------|-------------------|
| Pydantic schemas | `core/schemas/ui_schema.py` | BaseModel classes with Field defaults, validation helpers |
| Router structure | `routers/apps.py` | APIRouter with prefix/tags, request models, file-based CRUD |
| Lazy singleton | `shared/state.py` | `_instance = None` + `get_*()` accessor pattern |
| LLM calls | `core/model_manager.py:ModelManager.generate_text()` | Async method, supports Gemini/Ollama via config |
| JSON parsing | `core/json_parser.py:parse_llm_json()` | 3-stage extraction (fenced -> balanced -> repair) |
| Skill class | `core/skills/base.py:Skill` | `name`, `description`, `get_system_prompt_additions()`, `get_metadata()` |
| Skill auto-discovery | `core/skills/manager.py:scan_and_register()` | Any `core/skills/library/{name}/skill.py` is auto-found |
| Router registration | `api.py` (lines 99-142) | `from routers import X; app.include_router(X.router, prefix="/api")` |

---

## 1. Directory & File Structure

```
Arcturus/
├── core/
│   ├── schemas/
│   │   └── studio_schema.py                     # NEW — all Forge Pydantic models
│   └── studio/
│       ├── __init__.py                          # NEW (package init)
│       ├── orchestrator.py                      # NEW — outline-first pipeline
│       ├── storage.py                           # NEW — file-based persistence
│       ├── revision.py                          # NEW — revision management
│       └── prompts.py                           # NEW — LLM prompt templates
├── core/skills/library/
│   └── forge_outline/
│       └── skill.py                             # NEW — skill stub for intent matching
├── routers/
│   └── studio.py                                # NEW — /api/studio/* endpoints
├── studio/                                      # NEW (runtime data dir, created by storage.py)
│   └── {artifact_id}/
│       ├── artifact.json
│       └── revisions/
│           └── {revision_id}.json
├── tests/
│   ├── test_studio_schema.py                    # NEW
│   ├── test_studio_storage.py                   # NEW
│   ├── test_studio_revision.py                  # NEW
│   └── test_studio_orchestrator.py              # NEW
├── api.py                                       # MODIFY — mount studio router
└── shared/state.py                              # MODIFY — add get_studio_storage()
```

**Total: 8 new files + 2 modified files + 4 test files**

---

## 2. Pydantic Schema Design

**File:** `core/schemas/studio_schema.py`

### 2.1 Enums

```python
from datetime import datetime
from enum import Enum

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
```

### 2.2 Content Tree Models

**SlideElement:**
```python
class SlideElement(BaseModel):
    id: str
    type: str  # title, subtitle, body, bullet_list, image, chart, code, quote
    content: Any = None
```

**Slide:**
```python
class Slide(BaseModel):
    id: str
    slide_type: str  # title, content, two_column, comparison, timeline, chart, image_text, quote, code, team
    title: Optional[str] = None
    elements: List[SlideElement] = Field(default_factory=list)
    speaker_notes: Optional[str] = None
```

**SlidesContentTree:**
```python
class SlidesContentTree(BaseModel):
    deck_title: str
    subtitle: Optional[str] = None
    slides: List[Slide]
    metadata: Optional[Dict[str, Any]] = None
```

**DocumentSection (recursive):**
```python
class DocumentSection(BaseModel):
    id: str
    heading: str
    level: int = 1
    content: Optional[str] = None
    subsections: List["DocumentSection"] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
```

**DocumentContentTree:**
```python
class DocumentContentTree(BaseModel):
    doc_title: str
    doc_type: str  # technical_spec, business_plan, research_paper, blog_post, report, proposal, white_paper
    abstract: Optional[str] = None
    sections: List[DocumentSection]
    bibliography: List[Dict[str, str]] = Field(default_factory=list)
    metadata: Optional[Dict[str, Any]] = None
```

**SheetTab:**
```python
class SheetTab(BaseModel):
    id: str
    name: str
    headers: List[str] = Field(default_factory=list)
    rows: List[List[Any]] = Field(default_factory=list)
    formulas: Dict[str, str] = Field(default_factory=dict)  # cell_ref -> formula string
    column_widths: List[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_column_widths(self):
        if self.column_widths and self.headers and len(self.column_widths) != len(self.headers):
            raise ValueError(
                f"column_widths length ({len(self.column_widths)}) "
                f"must match headers length ({len(self.headers)})"
            )
        return self
```

**SheetContentTree:**
```python
class SheetContentTree(BaseModel):
    workbook_title: str
    tabs: List[SheetTab]
    assumptions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
```

### 2.3 Outline Models

```python
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
```

### 2.4 Core Models

```python
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
```

> **Convention note:** All mutable defaults use `Field(default_factory=...)` instead of bare `= []` or `= {}`. This follows the pattern established in `remme/schemas/hub_schemas.py` and `core/schemas/ui_schema.py`.

> **Timestamp convention:** `created_at` and `updated_at` fields use `datetime` instead of `str`. Pydantic v2 serializes `datetime` fields to ISO 8601 strings in `model_dump(mode='json')`, and deserializes ISO strings back to `datetime` on construction. This follows the `remme/schemas/hub_schemas.py` pattern.

### 2.5 Validation Helpers

```python
# Union type for dispatching content tree validation
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
```

**Important:** Call `DocumentSection.model_rebuild()` after class definition to resolve forward references for the recursive `subsections` field.

---

## 3. Content Tree JSON Examples

### Slides
```json
{
  "deck_title": "Series A Pitch Deck",
  "subtitle": "Acme AI -- Transforming Enterprise Automation",
  "slides": [
    {
      "id": "s1",
      "slide_type": "title",
      "title": "Acme AI",
      "elements": [
        {"id": "e1", "type": "title", "content": "Acme AI"},
        {"id": "e2", "type": "subtitle", "content": "Series A Pitch Deck -- 2026"}
      ],
      "speaker_notes": "Introduce the company and team."
    },
    {
      "id": "s2",
      "slide_type": "content",
      "title": "The Problem",
      "elements": [
        {"id": "e3", "type": "body", "content": "Enterprises waste 40% of operational time..."},
        {"id": "e4", "type": "bullet_list", "content": ["Manual data entry", "Fragmented tools"]}
      ],
      "speaker_notes": "Emphasize pain points."
    }
  ],
  "metadata": {"audience": "investors", "tone": "professional"}
}
```

### Document
```json
{
  "doc_title": "Technical Specification: Microservices Migration",
  "doc_type": "technical_spec",
  "abstract": "This document outlines the migration plan...",
  "sections": [
    {
      "id": "sec1", "heading": "Introduction", "level": 1,
      "content": "The current monolithic system has reached its scalability limits...",
      "subsections": [
        {"id": "sec1a", "heading": "Current Architecture", "level": 2,
         "content": "Built on a single Django application...", "subsections": [], "citations": []}
      ],
      "citations": ["chen2024"]
    }
  ],
  "bibliography": [{"key": "chen2024", "title": "Microservices Patterns", "author": "Chen, Y."}],
  "metadata": {"audience": "engineering leads", "tone": "technical"}
}
```

### Sheet
```json
{
  "workbook_title": "SaaS Financial Model",
  "tabs": [
    {
      "id": "tab1", "name": "Revenue Model",
      "headers": ["Month", "Users", "MRR", "Growth Rate"],
      "rows": [["Jan 2026", 1000, 50000, null], ["Feb 2026", 1100, 55000, null]],
      "formulas": {"D3": "=((C3-C2)/C2)*100"},
      "column_widths": [120, 80, 100, 100]
    }
  ],
  "assumptions": "10% monthly user growth. $50 ARPU.",
  "metadata": {"model_type": "financial", "currency": "USD"}
}
```

---

## 4. Storage Layer

**File:** `core/studio/storage.py`

### Design

Mirrors the `routers/apps.py` pattern of `PROJECT_ROOT / "apps" / app_id / "ui.json"`, but uses `PROJECT_ROOT / "studio"` as the root directory.

### Layout

```
studio/
└── {artifact_id}/
    ├── artifact.json         # Full Artifact model serialized via model_dump()
    └── revisions/
        └── {revision_id}.json  # Each Revision snapshot
```

### StudioStorage Class

```python
class StudioStorage:
    def __init__(self, base_dir: Path = None):
        """Initialize with configurable base_dir.
        Priority: explicit arg > FORGE_STUDIO_DIR env var > PROJECT_ROOT/studio default."""
        from shared.state import PROJECT_ROOT
        self.base_dir = base_dir or Path(os.environ.get("FORGE_STUDIO_DIR", "")) or PROJECT_ROOT / "studio"
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `save_artifact` | `(artifact: Artifact) -> None` | Serialize via `artifact.model_dump()`, write to `{id}/artifact.json` |
| `load_artifact` | `(artifact_id: str) -> Optional[Artifact]` | Read and parse; return `None` if not found |
| `list_artifacts` | `() -> List[Dict]` | Scan all artifact dirs, return `[{id, type, title, updated_at}]` sorted by `updated_at` desc |
| `delete_artifact` | `(artifact_id: str) -> None` | `shutil.rmtree()` the artifact directory |
| `save_revision` | `(revision: Revision) -> None` | Write to `{artifact_id}/revisions/{revision_id}.json` |
| `load_revision` | `(artifact_id: str, revision_id: str) -> Optional[Revision]` | Read specific revision |
| `list_revisions` | `(artifact_id: str) -> List[Dict]` | List all revisions sorted by `created_at` desc |

### Shared State Registration

Add to `shared/state.py` (after the existing `get_agent_runner()` block, before `settings = {}`):

```python
# Studio Storage instance
_studio_storage = None

def get_studio_storage():
    """Get the StudioStorage instance, creating it if needed."""
    global _studio_storage
    if _studio_storage is None:
        from core.studio.storage import StudioStorage
        _studio_storage = StudioStorage()
    return _studio_storage
```

This follows the exact pattern of `get_remme_store()` at `shared/state.py:29-35`.

---

## 5. Revision Model

**File:** `core/studio/revision.py`

### RevisionManager Class

```python
class RevisionManager:
    def __init__(self, storage: StudioStorage):
        self.storage = storage
```

| Method | Signature | Description |
|--------|-----------|-------------|
| `create_revision` | `(artifact_id, content_tree, change_summary, parent_revision_id=None) -> Revision` | Generate UUID, create `Revision` model, persist via `storage.save_revision()`, return it |
| `get_revision` | `(artifact_id, revision_id) -> Optional[Revision]` | Delegate to `storage.load_revision()` |
| `get_revision_history` | `(artifact_id) -> List[Dict]` | Delegate to `storage.list_revisions()` |

Revisions form a linked list via `parent_revision_id`. The `Artifact.revision_head_id` always points to the latest revision. In Phase 1, only the initial revision is created (upon outline approval). The edit loop in Phase 6 will create subsequent revisions.

### Change Summary Diff Utility

Also in `core/studio/revision.py`, a standalone function for computing structured change summaries. This avoids hardcoded strings like `"Initial draft"` and prepares the revision model for Phase 6's edit loop.

```python
def compute_change_summary(old_tree: dict | None, new_tree: dict | None) -> str:
    """Compute a human-readable summary of changes between two content trees.

    Compares top-level keys and reports added, removed, and changed counts.
    Returns a descriptive string suitable for Revision.change_summary.
    """
    if old_tree is None:
        return "Initial draft"
    if new_tree is None:
        return "Content removed"

    old_keys = set(old_tree.keys())
    new_keys = set(new_tree.keys())

    added = new_keys - old_keys
    removed = old_keys - new_keys
    changed = [k for k in old_keys & new_keys if old_tree[k] != new_tree[k]]

    parts = []
    if added:
        parts.append(f"{len(added)} added")
    if removed:
        parts.append(f"{len(removed)} removed")
    if changed:
        parts.append(f"{len(changed)} changed")

    return ", ".join(parts) if parts else "No changes"
```

The orchestrator calls `compute_change_summary(None, content_tree)` for the initial draft (returns `"Initial draft"`), and future edit-loop revisions will pass the previous tree for a meaningful diff.

---

## 6. LLM Prompt Templates

**File:** `core/studio/prompts.py`

Two main functions:

### `get_outline_prompt(artifact_type, user_prompt, parameters) -> str`

Builds a system prompt requesting structured outline JSON. Includes:
- Role instruction ("You are a content architect...")
- Type-specific guidance:
  - **slides**: narrative arc, suggested slide count based on prompt
  - **document**: hierarchical sections with heading levels
  - **sheet**: tab descriptions, column planning
- Exact JSON schema for `Outline` output (title, items with id/title/description/children)
- Instruction to return only valid JSON

### `get_draft_prompt(artifact_type, outline) -> str`

Builds a system prompt requesting full content_tree JSON from an approved outline. Includes:
- The approved outline serialized as JSON context
- Type-specific content tree schema (matching the Pydantic models exactly)
- Instruction to populate all fields with substantive content
- Instruction to return only valid JSON

Each prompt template is a multi-line f-string with the schema examples from Section 3 embedded.

---

## 7. Outline-First Orchestrator

**File:** `core/studio/orchestrator.py`

### Dependencies
- `core/model_manager.py:ModelManager` — async LLM calls
- `core/json_parser.py:parse_llm_json` — robust JSON extraction
- `core/schemas/studio_schema.py` — all Pydantic models + `validate_content_tree()`
- `core/studio/storage.py:StudioStorage`
- `core/studio/revision.py:RevisionManager`
- `core/studio/prompts.py` — prompt templates

### ForgeOrchestrator Class

```python
class ForgeOrchestrator:
    def __init__(self, storage: StudioStorage):
        self.storage = storage
        self.revision_manager = RevisionManager(storage)
```

### Pipeline Flow

```
POST /api/studio/slides {prompt, parameters}
    |
    v
[Step 1] ForgeOrchestrator.generate_outline(prompt, artifact_type, parameters)
    |  - Build LLM prompt via get_outline_prompt()
    |  - Call ModelManager.generate_text(prompt)
    |  - Parse response via parse_llm_json(raw, required_keys=["title", "items"])
    |  - Construct Outline model (status="pending")
    |  - Generate artifact_id via uuid4()
    |  - Create Artifact with outline attached, content_tree=None
    |  - Save to StudioStorage
    v
Return {artifact_id, outline, status: "pending"}

POST /api/studio/{artifact_id}/outline/approve {approved: true}
    |
    v
[Step 2] ForgeOrchestrator.approve_and_generate_draft(artifact_id, modifications?)
    |  - Load artifact from StudioStorage
    |  - Raise ValueError if artifact not found or has no outline
    |  - Apply optional modifications to outline items
    |  - Mark outline status = "approved"
    |  - Build LLM prompt via get_draft_prompt(type, outline)
    |  - Call ModelManager.generate_text(prompt)
    |  - Parse + validate via parse_llm_json() -> validate_content_tree()
    |  - Compute change_summary via compute_change_summary(None, content_tree)
    |  - Create Revision via RevisionManager (content_tree_snapshot, change_summary)
    |  - Update Artifact (content_tree, revision_head_id)
    |  - Save to StudioStorage
    v
Return full Artifact with content_tree
```

### Key Design Decisions

- **Direct LLM call** (not through AgentLoop4) — matches how `routers/apps.py:generate_app()` calls `core/generator.py` directly. AgentLoop4 integration deferred to Phase 6 (edit loop).
- **ModelManager instantiation**: Use default constructor (reads model from `config/profiles.yaml` `llm.text_generation` key), same as existing agent code.
- **Error handling**: `ValueError` for missing artifact/outline (→ 404) or bad input (→ 400); `JsonParsingError` for unparseable LLM output; Pydantic `ValidationError` for schema mismatches (→ 422). Router catches all and returns differentiated HTTP status codes (400/404/422/500).

---

## 8. Router Endpoints

**File:** `routers/studio.py`

### Structure (follows `routers/apps.py` pattern)

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict

router = APIRouter(prefix="/studio", tags=["Studio"])
```

### Request/Response Models (defined in router file)

```python
class CreateArtifactRequest(BaseModel):
    prompt: str
    title: Optional[str] = None
    parameters: Optional[Dict] = Field(default_factory=dict)
    model: Optional[str] = None

    # title: If provided, overrides the LLM-generated outline title. If None, the LLM's title is used.
    # model: Passed to ModelManager as an override. If None, uses default from config/profiles.yaml.
    #        Follows the same pattern as routers/apps.py:GenerateAppRequest.model.

class ApproveOutlineRequest(BaseModel):
    approved: bool = True
    modifications: Optional[Dict] = None
```

### Phase 1 Endpoints

| Method | Path | Handler | Description |
|--------|------|---------|-------------|
| `POST` | `/studio/slides` | `create_slides()` | Create slides artifact; returns outline for approval |
| `POST` | `/studio/documents` | `create_document()` | Create document artifact; returns outline |
| `POST` | `/studio/sheets` | `create_sheet()` | Create sheet artifact; returns outline |
| `POST` | `/studio/{artifact_id}/outline/approve` | `approve_outline()` | Approve outline -> generates draft content_tree |
| `GET`  | `/studio/{artifact_id}` | `get_artifact()` | Retrieve full artifact |
| `GET`  | `/studio` | `list_artifacts()` | List all artifacts |
| `GET`  | `/studio/{artifact_id}/revisions` | `list_revisions()` | List revisions for artifact |
| `GET`  | `/studio/{artifact_id}/revisions/{revision_id}` | `get_revision()` | Get specific revision |

All three `POST /studio/{type}` handlers delegate to the same `ForgeOrchestrator.generate_outline()`, passing the appropriate `ArtifactType` enum value.

### Error Handling Pattern (from `routers/apps.py`)

```python
from pydantic import ValidationError

try:
    result = await orchestrator.generate_outline(...)
    return result
except ValidationError as e:
    raise HTTPException(status_code=422, detail=str(e))
except ValueError as e:
    detail = str(e)
    if "not found" in detail.lower():
        raise HTTPException(status_code=404, detail=detail)
    raise HTTPException(status_code=400, detail=detail)
except Exception as e:
    raise HTTPException(status_code=500, detail=str(e))
```

### Registration in `api.py`

Add after existing router imports (after line 142 in `api.py`):

```python
from routers import studio as studio_router
app.include_router(studio_router.router, prefix="/api")
```

---

## 9. Skill Integration

**File:** `core/skills/library/forge_outline/skill.py`

Follows the pattern from `core/skills/library/browser/skill.py`:

```python
from core.skills.base import Skill

class ForgeOutlineSkill(Skill):
    name = "forge_outline"
    description = "Generates structured outlines for slides, documents, and sheets."

    @property
    def prompt_text(self) -> str:
        return """You are the Forge Outline Agent. Your job is to create structured
outlines for presentations, documents, and spreadsheets based on user prompts.

When the user asks to create slides, a document, or a spreadsheet, generate
a structured outline with sections/slides/tabs appropriate for the content type.

Supported artifact types: slides, document, sheet.
"""

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text

    def get_metadata(self):
        from core.skills.base import SkillMetadata
        return SkillMetadata(
            name=self.name,
            description=self.description,
            intent_triggers=[
                "create slides", "make a presentation", "pitch deck",
                "create document", "write a report", "technical spec",
                "create spreadsheet", "financial model", "create sheet",
            ]
        )
```

No new agent config entries needed. The `SkillManager.scan_and_register()` auto-discovers this folder on startup.

---

## 10. Test Plan

Tests are organized into three categories: **unit tests** (model/logic correctness), **contract tests** (serialization invariants across boundaries), and **pipeline tests** (end-to-end flow with mocked LLM). All files follow the flat `tests/test_*.py` convention per CLAUDE.md.

### `tests/test_studio_schema.py` — Unit + Contract Tests (20+ test cases)

**Unit tests — model validation:**

| Test | What It Verifies |
|------|-----------------|
| `test_slides_content_tree_valid` | Valid SlidesContentTree with multiple slides passes |
| `test_slides_content_tree_empty_slides` | Empty slides list is accepted |
| `test_document_content_tree_valid` | Valid DocumentContentTree with nested sections |
| `test_document_recursive_sections` | 3-level nested subsections parse correctly |
| `test_sheet_content_tree_valid` | Valid SheetContentTree with formulas |
| `test_validate_content_tree_slides` | `validate_content_tree(ArtifactType.slides, data)` returns SlidesContentTree |
| `test_validate_content_tree_document` | Same for document type |
| `test_validate_content_tree_sheet` | Same for sheet type |
| `test_validate_content_tree_malformed` | Malformed data raises `ValidationError` |
| `test_validate_content_tree_unknown_type` | Unknown type raises `ValueError` |
| `test_artifact_creation` | Artifact model with all fields populated |
| `test_artifact_defaults` | Artifact with minimal fields uses defaults |
| `test_revision_creation` | Revision model with all fields |
| `test_outline_creation` | Outline with nested OutlineItems |

**Contract tests — round-trip serialization (critical invariant: `model_dump() -> reconstruct -> equality`):**

These tests verify that no schema drift occurs across serialize/deserialize boundaries. This invariant must hold across all phases — if a future phase changes a model, these tests catch any breakage.

| Test | What It Verifies |
|------|-----------------|
| `test_slides_roundtrip` | `SlidesContentTree(**tree.model_dump()) == tree` |
| `test_document_roundtrip` | `DocumentContentTree(**tree.model_dump()) == tree` |
| `test_sheet_roundtrip` | `SheetContentTree(**tree.model_dump()) == tree` |
| `test_artifact_roundtrip` | `Artifact(**artifact.model_dump()) == artifact` |
| `test_revision_roundtrip` | `Revision(**revision.model_dump()) == revision` |
| `test_outline_roundtrip` | `Outline(**outline.model_dump()) == outline` (including nested OutlineItems) |

### `tests/test_studio_storage.py` — Storage Round-Trips (10+ test cases)

All tests use `tmp_path` pytest fixture for isolation (pass `base_dir=tmp_path / "studio"` to `StudioStorage`).

| Test | What It Verifies |
|------|-----------------|
| `test_save_load_artifact` | Save then load returns equal artifact |
| `test_load_nonexistent_returns_none` | Loading missing ID returns None |
| `test_list_artifacts_empty` | Empty dir returns empty list |
| `test_list_artifacts_sorted` | Multiple artifacts listed by updated_at desc |
| `test_delete_artifact` | Deleted artifact no longer loadable |
| `test_save_load_revision` | Save then load revision round-trip |
| `test_load_nonexistent_revision` | Returns None |
| `test_list_revisions` | Multiple revisions listed by created_at desc |
| `test_list_revisions_empty` | No revisions returns empty list |
| `test_artifact_dir_created` | Saving artifact creates directory structure |

### `tests/test_studio_revision.py` — Revision Management + Diff Utility (10+ test cases)

**RevisionManager tests:**

| Test | What It Verifies |
|------|-----------------|
| `test_create_revision` | RevisionManager creates and persists a revision |
| `test_revision_has_generated_id` | Revision gets a UUID id |
| `test_revision_chain` | Second revision has parent_revision_id pointing to first |
| `test_get_revision` | Can retrieve by ID |
| `test_revision_history` | History returns all revisions in order |

**`compute_change_summary()` tests:**

| Test | What It Verifies |
|------|-----------------|
| `test_diff_initial_draft` | `compute_change_summary(None, tree)` returns `"Initial draft"` |
| `test_diff_content_removed` | `compute_change_summary(tree, None)` returns `"Content removed"` |
| `test_diff_no_changes` | Same old/new tree returns `"No changes"` |
| `test_diff_added_keys` | New keys detected and counted |
| `test_diff_removed_and_changed` | Mixed changes produce combined summary like `"1 removed, 2 changed"` |

### `tests/test_studio_orchestrator.py` — Pipeline Tests (8+ test cases, mocked LLM)

Uses `unittest.mock.AsyncMock` to patch `ModelManager.generate_text()` with canned JSON responses.

| Test | What It Verifies |
|------|-----------------|
| `test_generate_outline_creates_artifact` | Outline generation creates an artifact with `outline.status == "pending"` |
| `test_generate_outline_persisted` | Artifact is persisted to storage |
| `test_approve_generates_draft` | Approval creates content_tree and revision |
| `test_approve_nonexistent_raises` | ValueError for missing artifact_id |
| `test_approve_no_outline_raises` | ValueError when artifact has no outline |
| `test_generate_outline_malformed_json` | Mock LLM returns unparseable text → raises appropriate error, no artifact persisted |
| `test_approve_invalid_content_tree` | Mock LLM returns valid JSON that fails Pydantic validation → 422 error, no revision created |
| `test_approve_already_approved` | Approve an already-approved outline → idempotent behavior (re-generates draft with new revision) |

**Mock setup pattern:**

```python
@pytest.fixture
def mock_model_manager(monkeypatch):
    async def fake_generate(self, prompt):
        # Return canned outline or draft JSON depending on prompt content
        if "outline" in prompt.lower():
            return json.dumps({"title": "Test Deck", "items": [{"id": "1", "title": "Intro", "description": "Opening slide"}]})
        else:
            return json.dumps({"deck_title": "Test Deck", "slides": [...]})
    monkeypatch.setattr("core.model_manager.ModelManager.generate_text", fake_generate)

@pytest.fixture
def deterministic_ids(monkeypatch):
    """Patch uuid4 for deterministic artifact/revision IDs."""
    call_count = 0
    def fake_uuid4():
        nonlocal call_count
        call_count += 1
        return f"test-uuid-{call_count:04d}"
    monkeypatch.setattr("uuid.uuid4", fake_uuid4)
```

Note: Orchestrator tests use the `deterministic_ids` fixture to assert exact `artifact_id` and `revision_id` values.

### Optional: FastAPI Integration Tests (nice-to-have)

No existing router in the codebase has `TestClient`-based integration tests (`routers/apps.py` has 15+ endpoints with zero). If time permits on Day 5, add a `tests/test_studio_api.py` using `httpx.AsyncClient` (already in `pyproject.toml`) to verify route wiring and HTTP status code mapping:

| Test | What It Verifies |
|------|-----------------|
| `test_create_slides_returns_201` | `POST /api/studio/slides` with valid prompt returns outline |
| `test_get_nonexistent_returns_404` | `GET /api/studio/missing-id` returns 404 |
| `test_approve_validation_error_returns_422` | Approval with malformed content tree returns 422 |
| `test_list_artifacts_empty` | `GET /api/studio` returns empty list on clean state |

This is **not required** for Phase 1 exit criteria — manual curl tests on Day 4 provide equivalent coverage. These can also be added retroactively in a later phase.

---

## 11. Files to Modify

### `api.py` (line ~142)

Add after the existing `optimizer` router import block:

```python
from routers import studio as studio_router
app.include_router(studio_router.router, prefix="/api")
```

### `shared/state.py` (after line 69, before `settings = {}`)

Add `get_studio_storage()` lazy singleton (see Section 4).

### `.gitignore`

Add `studio/` to prevent runtime artifact data from being committed. This directory is created at runtime by `StudioStorage`.

---

## 12. Dependencies

**No new pip dependencies required.** All needed packages are already in `pyproject.toml`:

- `pydantic` — schema models
- `fastapi` — router
- `json-repair` — used by `core/json_parser.py`
- `google-genai` — Gemini LLM calls via `core/model_manager.py`
- `pytest` — testing
- `pytest-asyncio` — async test support (verify present: `uv pip list | grep asyncio`)

---

## 13. Day-by-Day Execution Sequence

### Day 1: Schema Foundation

1. Create `core/schemas/studio_schema.py` with all Pydantic models (enums, content trees, Artifact, Revision, Outline, validation helpers)
2. Create `tests/test_studio_schema.py`
3. Run: `python -m pytest tests/test_studio_schema.py -q`

**Exit gate:** All 15+ schema tests pass.

### Day 2: Storage + Revision Layer

1. Create `core/studio/__init__.py` (empty)
2. Create `core/studio/storage.py` (StudioStorage class)
3. Create `core/studio/revision.py` (RevisionManager class)
4. Create `tests/test_studio_storage.py` and `tests/test_studio_revision.py`
5. Run: `python -m pytest tests/test_studio_storage.py tests/test_studio_revision.py -q`

**Exit gate:** All 15+ storage/revision tests pass.

### Day 3: Prompts + Orchestrator

1. Create `core/studio/prompts.py` (outline + draft prompt templates)
2. Create `core/studio/orchestrator.py` (ForgeOrchestrator class)
3. Create `tests/test_studio_orchestrator.py` (with mocked LLM)
4. Run: `python -m pytest tests/test_studio_orchestrator.py -q`

**Exit gate:** All 8+ orchestrator tests pass with mocked LLM.

### Day 4: Router + API Integration

1. Create `routers/studio.py` with all Phase 1 endpoints
2. Modify `api.py` — add `studio_router` import + `include_router` (after line 142)
3. Modify `shared/state.py` — add `get_studio_storage()` singleton
4. Create `core/skills/library/forge_outline/skill.py`
5. Add `studio/` to `.gitignore`
6. Run: `python -m pytest tests/test_studio_*.py -q`
7. Manual E2E test:

```bash
# Start server
uv run api.py

# Create slides outline
curl -X POST http://localhost:8000/api/studio/slides \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a 10-slide pitch deck for an AI startup"}'

# Approve outline (use artifact_id from response)
curl -X POST http://localhost:8000/api/studio/{artifact_id}/outline/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}'

# Retrieve artifact
curl http://localhost:8000/api/studio/{artifact_id}

# List all artifacts
curl http://localhost:8000/api/studio
```

**Exit gate:** Endpoints return correct responses, outline -> approval -> draft flow works.

### Day 5: Polish + Full Test Suite

1. Run `scripts/test_all.sh quick` — ensure no regressions
2. Fix any lint issues
3. Verify all Phase 1 exit criteria (table below)
4. Run all Forge tests together: `python -m pytest tests/test_studio_*.py -v`

---

## 14. Exit Criteria

| Criterion | How to Verify |
|-----------|---------------|
| Can create artifact of each type passing schema validation | `test_studio_schema.py` — unit tests for valid slides/doc/sheet |
| Malformed payloads return controlled errors | `test_studio_schema.py` — malformed data raises `ValidationError` |
| content_tree round-trip serialization (contract) | `test_studio_schema.py` — contract tests: `model_dump()` -> reconstruct -> equality for all types |
| Outline-first flow: outline -> approve -> draft | `test_studio_orchestrator.py` — full pipeline with mocked LLM |
| Revision created on draft generation with computed summary | `test_studio_orchestrator.py` + `test_studio_revision.py` — revision exists with meaningful change_summary |
| Change summary diff utility works correctly | `test_studio_revision.py` — `compute_change_summary()` tests for initial, removed, no-change, and mixed scenarios |
| Storage persists and retrieves correctly | `test_studio_storage.py` — save/load round-trips |
| No regressions in existing tests | `scripts/test_all.sh quick` passes |

---

## 15. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM returns malformed JSON | `core/json_parser.py` has 3-stage extraction + `json-repair`. Use it for all LLM responses. |
| Content tree schema drift between outline and draft | Draft prompt includes exact JSON schema. Validate with Pydantic immediately after parsing. |
| Recursive `DocumentSection` Pydantic issues | Pydantic v2 handles recursive models natively. Call `DocumentSection.model_rebuild()` after class definition if needed. |
| Rate limiting on Gemini during manual testing | Orchestrator tests mock LLM. Manual tests use small prompts. `ModelManager._wait_for_rate_limit()` handles 15 RPM limit. |
| `studio/` dir conflicts with git | Directory created at runtime, added to `.gitignore`. |
| `core/schemas/__init__.py` might not exist | Check if it exists; create as empty file if not. |
| `datetime` fields serialize differently than `str` | `model_dump()` returns `datetime` objects; use `model_dump(mode='json')` for ISO 8601 strings. Contract tests verify round-trip serialization. |

---

## Appendix A: Key Existing Files Referenced

| File | Line(s) | What It Provides |
|------|---------|-----------------|
| `core/schemas/ui_schema.py` | 1-43 | Pydantic schema pattern (BaseModel, Field, validation helper) |
| `core/model_manager.py` | 113-120 | `ModelManager.generate_text(prompt) -> str` (async) |
| `core/json_parser.py` | 34-74 | `parse_llm_json(text, required_keys) -> dict` |
| `routers/apps.py` | 1-16 | Router pattern (APIRouter, prefix, tags, request models) |
| `routers/apps.py` | 55-81 | `list_apps()` — file-based listing pattern |
| `routers/apps.py` | 84-96 | `get_app()` — file-based retrieval pattern |
| `shared/state.py` | 29-35 | `get_remme_store()` — lazy singleton pattern |
| `core/skills/base.py` | 16-58 | `Skill` base class (name, description, get_metadata, get_system_prompt_additions) |
| `core/skills/manager.py` | 33-73 | `scan_and_register()` — auto-discovery from `core/skills/library/*/skill.py` |
| `api.py` | 99-142 | Router import + `include_router()` registration pattern |

## Appendix B: Handoff to Phase 2

Phase 2 (Slides MVP, Days 6-8) can start once Phase 1 provides:
- Stable schema models that validate all three content tree types
- Working outline-to-draft lifecycle via `ForgeOrchestrator`
- Reliable revision scaffolding for change tracking
- API endpoints that can be extended for theme support, export, and edit loop
- `studio/` storage directory conventions established

Phase 2 will add:
- `studio/slides/` — slide generation engine with themes
- python-pptx dependency for PPTX export
- Theme assets and template system
- Enhanced slide-specific prompts for higher quality output
