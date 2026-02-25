# Forge Phase 4 - Implementation Plan: Docs MVP + DOCX/PDF Export (Days 11-13)

## Context

Phase 1 (Days 1-5) established the Forge studio foundation: canonical Pydantic schemas in `core/schemas/studio_schema.py`, outline-first orchestration in `core/studio/orchestrator.py`, file-based artifact/revision persistence in `core/studio/storage.py`, prompt templates in `core/studio/prompts.py`, and the core Studio API routes in `routers/studio.py`.

Phase 2 (Days 6-8) delivered the Slides MVP: deterministic slide planning, curated theme support, PPTX export, export job lifecycle tracking, and export/download endpoints.

Phase 3 (Days 9-10) completed the Slides quality pass: 100+ themes via variants, native charts, speaker notes repair, and blocking slide layout-quality validation.

With Phase 3 complete, the platform now has:

- A working outline-first flow for all three artifact types (`slides`, `document`, `sheet`)
- Document schema support (`DocumentContentTree`, `DocumentSection`) and basic document draft generation via LLM
- A mature export pipeline pattern (job creation, storage, validation, download) but only for slide PPTX export

Phase 4 focuses on turning the existing document outline/draft capability into a usable Docs MVP with reliable export outputs.

This plan is derived from:

- `docs/forge_20_day_plan.md` (Phase 4 scope, gates, exit criteria)
- `docs/forge_specs.md` (FR-D1, FR-D2, FR-D3, FR-D6, FR-S4)
- Current Phase 3 implementation state in `core/studio/`, `routers/studio.py`, `platform-frontend/src/features/studio/`

### Phase 4 Goals (from plan/specs)

- Document generator MVP for core types:
  - Technical Spec
  - Report
  - Proposal
- Outline-first workflow fully functional for documents
- Export:
  - DOCX via `python-docx`
  - PDF via `WeasyPrint`
- Citation plumbing:
  - Store provenance slots (minimal, forward-compatible)

### Scope Boundaries

**In scope:**

- Harden document outline generation with doc-type-aware structure normalization
- Improve document draft prompt/schema guidance for Phase 4 core types
- Add document post-generation normalization (section levels/ids/content/citations)
- Add minimal citation/provenance slot plumbing in document content metadata
- Add document export support in orchestrator/router for `docx` and `pdf`
- Implement DOCX export and PDF export validators
- Add minimal frontend export hooks so document artifacts can be exported from Studio UI
- Add unit/acceptance/integration tests for document generation + export

**Out of scope:**

- Markdown, LaTeX, Google Docs export (future phase)
- Collaborative document editing/annotations (Phase 6+)
- Full citation style formatting (APA/MLA/Chicago/IEEE rendering fidelity)
- Oracle-backed automatic citation enrichment beyond placeholder/provenance slot storage
- Rich WYSIWYG document editor (Phase 6+)
- Sheet generation/export (Phase 5)
- Slides PDF/HTML export (future phase)

### Codebase Patterns Referenced

| Pattern | Source File | What to Replicate |
|---------|-------------|-------------------|
| Backward-safe schema evolution with optional fields | `core/schemas/studio_schema.py` | Add DOCX/PDF formats and document metadata fields without breaking existing artifacts |
| Export job lifecycle (pending -> completed/failed) | `core/studio/orchestrator.py` | Reuse identical job creation, persistence, and summary-update flow for docs |
| File-based export persistence layout | `core/studio/storage.py` | Reuse `{artifact_id}/exports/{job_id}.{fmt}` for docx/pdf outputs |
| Router request validation + error translation | `routers/studio.py` | Keep `HTTPException` mapping and UUID validation behavior |
| Prompt specialization by artifact type | `core/studio/prompts.py` | Extend document prompts without impacting slide-specific prompt improvements |
| Studio UI outline-first workspace split | `platform-frontend/src/features/studio/StudioWorkspace.tsx` | Reuse existing outline viewer + typed content viewer; add doc export affordance only |

---

## 1. Directory & File Structure

```
Arcturus/
├── core/
│   ├── schemas/
│   │   └── studio_schema.py                                   # MODIFY - ExportFormat (docx/pdf), document metadata conventions
│   └── studio/
│       ├── orchestrator.py                                    # MODIFY - document export dispatch + validation + format gating
│       ├── prompts.py                                         # MODIFY - doc-type-aware outline/draft guidance, citation slot instructions
│       └── documents/
│           ├── __init__.py                                    # NEW - package exports
│           ├── types.py                                       # NEW - Phase 4 doc type registry + required outline sections
│           ├── generator.py                                   # NEW - outline normalization + draft normalization for documents
│           ├── citations.py                                   # NEW - bibliography normalization + provenance slot helpers
│           ├── exporter_docx.py                               # NEW - DOCX export via python-docx
│           ├── exporter_pdf.py                                # NEW - PDF export via WeasyPrint (HTML/CSS render path)
│           ├── validator.py                                   # NEW - validate_docx(), validate_pdf()
│           └── templates/
│               ├── document_base.html.j2                      # NEW - HTML template for PDF rendering
│               └── document_base.css                          # NEW - print CSS for WeasyPrint
├── routers/
│   └── studio.py                                              # MODIFY - accept docx/pdf export, dynamic media types, param gating
├── platform-frontend/
│   └── src/
│       ├── features/studio/StudioWorkspace.tsx               # MODIFY - enable export button for document artifacts
│       ├── features/forge/components/ExportPanel.tsx         # MODIFY - document export mode or separate lightweight doc format picker
│       ├── lib/api.ts                                         # MODIFY - document export format calls (already generic signature)
│       └── store/index.ts                                     # MODIFY - generalized startExport(format, options) flow
├── tests/
│   ├── test_studio_documents_types.py                         # NEW - doc type registry + outline template enforcement
│   ├── test_studio_documents_generator.py                     # NEW - document draft normalization + citation slot normalization
│   ├── test_studio_documents_exporter_docx.py                 # NEW - DOCX rendering tests
│   ├── test_studio_documents_exporter_pdf.py                  # NEW - PDF rendering tests
│   ├── test_studio_documents_validator.py                     # NEW - DOCX/PDF open-validation tests
│   ├── test_studio_orchestrator.py                            # MODIFY - document export lifecycle tests (+ new mock cases)
│   ├── test_studio_export_router.py                           # MODIFY - docx/pdf router support + dynamic download media type
│   ├── test_studio_schema.py                                  # MODIFY - ExportFormat + document metadata/provenance slots schema tests
│   ├── acceptance/p04_forge/test_exports_open_and_render.py   # MODIFY - add DOCX/PDF acceptance cases (test_22+)
│   └── integration/test_forge_research_to_slides.py           # MODIFY - add document pipeline integration scenarios (naming remains legacy)
└── docs/
    └── forge_phase4_implementation_plan.md                    # THIS DOCUMENT
```

**Total (planned):** 10 new backend/template files + 4 modified backend/router files + 4 modified frontend files + 5 new test files + 5 modified test files

Notes:

- The integration test filename remains slides-oriented (`test_forge_research_to_slides.py`) for continuity with the SPS gate file path; Phase 4 extends it with document scenarios.
- Document export UI may be implemented as a lightweight format picker instead of reusing the slide theme picker directly. The plan below supports either approach.

---

## 2. Schema Additions

**File:** `core/schemas/studio_schema.py`

Phase 4 requires only small schema changes because document content models already exist. The main gaps are export formats and a typed convention for citation/provenance metadata.

### 2.1 `ExportFormat` Enum Expansion

Current code only supports `pptx`.

Phase 4 update:

```python
class ExportFormat(str, Enum):
    pptx = "pptx"
    docx = "docx"
    pdf = "pdf"
```

Rationale:

- Enables router/orchestrator parsing of document export formats
- Preserves the existing export job model and storage layout
- Avoids format-specific router branches outside the orchestrator dispatch

### 2.2 Document Metadata Convention (Minimal Citation Plumbing)

`DocumentContentTree.metadata` already exists and is optional (`Dict[str, Any]`). To minimize migration risk, Phase 4 uses a documented, normalized metadata contract instead of a large typed model rewrite.

Planned normalized keys (all optional):

```python
metadata = {
    "audience": "...",
    "tone": "...",
    "doc_type_display": "Technical Spec",
    "citation_style": "inline_bracket",      # Phase 4 internal/minimal style
    "provenance_slots": [
        {
            "slot_id": "prov1",
            "citation_key": "src_api_docs",
            "title": "API Reference",
            "url": "https://example.com/api",
            "author": "Vendor Docs",
            "retrieved_at": "2026-02-25T12:00:00Z",
            "source_type": "web",
            "status": "placeholder"          # placeholder | linked
        }
    ],
    "export_hints": {
        "toc": False,
        "page_numbers": True
    }
}
```

Why metadata instead of new top-level schema models in Phase 4:

- Backward-compatible with current `DocumentContentTree`
- Avoids breaking existing document tests and serialized artifacts
- Keeps Phase 4 focused on MVP generation/export
- Provides clear upgrade path to typed `ResearchProvenance` models in later phases

### 2.3 Bibliography Entry Normalization Convention

`bibliography` currently accepts `List[Dict[str, str]]`. Phase 4 keeps this type but standardizes expected keys in `core/studio/documents/citations.py`:

- `key` (required)
- `title` (required)
- `author` (optional)
- `url` (optional)
- `publisher` (optional)
- `published_at` (optional)
- `retrieved_at` (optional)
- `provenance_slot_id` (optional)

This is a behavior contract and helper normalization layer, not a hard schema break.

### 2.4 Backward Compatibility Rules

- Existing slide artifacts and exports continue to deserialize unchanged.
- Existing document artifacts without `metadata.provenance_slots` remain valid.
- Existing document `bibliography` entries with only `key/title/author` remain valid.
- Existing router tests that expect `"pdf"` to be unsupported must be updated (behavior changes in Phase 4).

---

## 3. Document Type Registry and Outline Enforcement

**New file:** `core/studio/documents/types.py`

Phase 4 requires reliable outline structure for three document types. LLM outline generation alone is not sufficient for deterministic test gates. We add a lightweight registry plus normalization pass.

### 3.1 Phase 4 Supported Document Types

Canonical values (generator/export-supported in Phase 4):

- `technical_spec`
- `report`
- `proposal`

Existing schema values not in the Phase 4 MVP remain accepted in raw content, but generation defaults will map unsupported values to `report` unless later phases add dedicated templates.

### 3.2 Registry Model

Suggested structure:

```python
DOC_TYPE_TEMPLATES = {
    "technical_spec": {
        "display_name": "Technical Spec",
        "required_sections": [
            "Executive Summary",
            "Problem Statement",
            "Requirements",
            "Proposed Solution",
            "Implementation Plan",
            "Risks and Mitigations",
        ],
        "optional_sections": ["Architecture", "Testing Strategy", "Appendix"],
        "min_sections": 5,
        "max_sections": 12,
        "allow_deep_subsections": True,
    },
    "report": {
        "display_name": "Report",
        "required_sections": [
            "Executive Summary",
            "Background",
            "Findings",
            "Recommendations",
            "Conclusion",
        ],
        "optional_sections": ["Methodology", "Appendix"],
        "min_sections": 4,
        "max_sections": 10,
        "allow_deep_subsections": True,
    },
    "proposal": {
        "display_name": "Proposal",
        "required_sections": [
            "Executive Summary",
            "Objectives",
            "Scope",
            "Approach",
            "Timeline",
            "Budget",
        ],
        "optional_sections": ["Assumptions", "Risks", "Next Steps"],
        "min_sections": 5,
        "max_sections": 10,
        "allow_deep_subsections": True,
    },
}
```

### 3.3 Outline Type Resolution

Phase 4 adds helper functions to infer/resolve the effective doc type:

- `resolve_document_type(parameters: dict, user_prompt: str) -> str`
- `get_doc_type_template(doc_type: str) -> dict`

Priority order:

1. `outline.parameters["doc_type"]` if valid
2. `parameters["doc_type"]` from request
3. Prompt keyword heuristics (`spec`, `report`, `proposal`)
4. Default to `report`

### 3.4 Outline Normalization Pass

**New helper (in `core/studio/documents/generator.py`):**

- `normalize_document_outline(outline: Outline) -> Outline`

Responsibilities:

- Ensure `outline.parameters["doc_type"]` is set to a Phase 4-supported value
- Clamp top-level section count within template bounds
- Insert missing required sections (append with deterministic ids)
- Normalize section titles to consistent casing
- Remove empty/null child arrays and malformed descriptions
- Limit nesting depth (practical max depth 3 for Phase 4)

This pass should run immediately after `generate_outline()` builds the `Outline` model and before saving the artifact.

### 3.5 Determinism Strategy for Tests

Unlike slides, documents do not need seed-based layout planning in Phase 4. Deterministic behavior is achieved by:

- Template-driven required section insertion
- Stable heading/id normalization
- Stable ordering rules (preserve LLM order; append required missing sections at end in template order)

---

## 4. Document Draft Normalization and Citation Plumbing

**New files:** `core/studio/documents/generator.py`, `core/studio/documents/citations.py`

The current document draft path validates schema but does not enforce document quality conventions. Phase 4 adds a deterministic post-generation normalization step before persistence.

### 4.1 Draft Normalization Entry Point

Suggested public function:

```python
def normalize_document_content_tree(
    content_tree: DocumentContentTree,
    *,
    outline: Outline,
    artifact_id: str | None = None,
) -> DocumentContentTree:
    ...
```

Responsibilities:

- Ensure `doc_type` is supported (fallback to `report` if unsupported)
- Ensure `abstract` exists and is non-empty (synthesize from first section if needed)
- Normalize section ids and heading levels recursively
- Ensure every top-level outline item maps to a top-level section (best-effort title alignment)
- Remove empty placeholder content (`TBD`, `Lorem ipsum`, etc.) and replace with deterministic fallback text
- Normalize bibliography entries and citation keys
- Populate `metadata.provenance_slots` placeholders from bibliography when missing

### 4.2 Section Structure Rules (Phase 4)

- Top-level sections must be `level == 1`
- Subsections increment by 1 relative to parent (max depth 3 recommended)
- Duplicate section ids are re-numbered deterministically (`sec1`, `sec2`, `sec2a`, ...)
- Empty `subsections` is always `[]`
- `content` may be empty only when `subsections` exists and contains content (rare)
- Each section should contain at least one substantive paragraph by export time

### 4.3 Citation/Bibliography Normalization

**`core/studio/documents/citations.py` helpers:**

- `normalize_bibliography(entries: list[dict]) -> list[dict]`
- `extract_citation_keys_from_sections(sections) -> set[str]`
- `reconcile_citations_and_bibliography(...) -> tuple[sections, bibliography]`
- `build_provenance_slots(bibliography, existing_slots=None) -> list[dict]`

Behavior:

- Deduplicate bibliography by `key` (fallback to slug from title)
- Guarantee all `section.citations` keys exist in bibliography
- Add placeholder bibliography entries for orphan citation keys
- Add placeholder provenance slots for bibliography entries without provenance linkage
- Preserve any existing `metadata.provenance_slots` entries if user/Oracle data already exists

### 4.4 Minimal Provenance Slot Contract (Phase 4)

Phase 4 does not implement a standalone `ResearchProvenance` persistence table/model yet. Instead:

- Provenance slots are stored in `DocumentContentTree.metadata.provenance_slots`
- Each slot links to bibliography via `citation_key`
- `status` field indicates whether the slot is:
  - `placeholder` (LLM-generated citation with no verified source)
  - `linked` (mapped to a real Oracle/source record in later phases)

This satisfies the "store provenance slots even if minimal" requirement while avoiding Phase 6 research/edit-loop scope.

### 4.5 Orchestrator Integration Point

In `approve_and_generate_draft()`:

```python
if artifact.type == ArtifactType.document:
    from core.studio.documents.generator import (
        normalize_document_content_tree,
        normalize_document_outline,
    )
    artifact.outline = normalize_document_outline(artifact.outline)
    content_tree_model = normalize_document_content_tree(
        content_tree_model,
        outline=artifact.outline,
        artifact_id=artifact.id,
    )
```

Note:

- Outline normalization should also run in `generate_outline()` so users review the normalized outline.
- Running it again before draft generation is acceptable and keeps behavior idempotent.

---

## 5. DOCX Exporter (`python-docx`)

**New file:** `core/studio/documents/exporter_docx.py`

Phase 4 DOCX export should prioritize correctness, readability, and consistent structure over advanced styling.

### 5.1 Design Approach

- Use `python-docx` to build documents programmatically
- Map `DocumentContentTree` to:
  - Title
  - Abstract / Executive Summary paragraph
  - Heading hierarchy
  - Body paragraphs
  - Citations inline (`[citation_key]`) for Phase 4
  - Bibliography section (simple list)
- Return output path after save

### 5.2 Public API

```python
def export_to_docx(content_tree: DocumentContentTree, output_path: Path) -> Path:
    ...
```

Design notes:

- Match the slides exporter style (`export_to_pptx(...) -> Path`)
- Create parent directory if missing
- Raise `ValueError` for empty/invalid section trees before writing

### 5.3 Rendering Rules

Document title and front matter:

- Add title as document heading level 0 (or custom title style)
- Add a metadata subtitle line (doc type display + generated timestamp optional)
- Add abstract under heading "Abstract" unless already represented as first section

Sections:

- Recursive renderer `render_section(doc, section, level)`
- `level == 1` -> Heading 1, `level == 2` -> Heading 2, etc. (clamped to Word-supported levels)
- Split `content` into paragraphs on blank lines
- Preserve bullet-like lines (`-`, `*`, `1.`) as simple paragraph styles in Phase 4 (no full list parsing required)

Citations:

- Append inline citation list at end of section body paragraph(s), example: `... [src_api_docs, src_benchmark_2025]`
- No footnote/endnote objects in Phase 4 (keeps implementation low-risk)

Bibliography:

- Add final `Heading 1: Bibliography`
- Render one paragraph per entry:
  - `[{key}] Title. Author. URL`
- Include available fields only (skip missing)

### 5.4 Safety and Reliability

- Sanitize control characters unsupported by XML/docx
- Clamp excessively long headings (e.g., 512 chars)
- Ensure at least one body paragraph exists if sections are empty (fallback explanatory text)
- Fail fast on malformed recursive structures (e.g., cycles are impossible in Pydantic model but guard anyway)

### 5.5 Styling (MVP)

Keep styling simple and stable:

- Default Word styles (Normal, Heading 1-3)
- 11pt body font, 1.15 line spacing (optional if easy)
- Page margins default
- No custom embedded fonts/themes in Phase 4

Rationale: the gate is "opens without corruption", not design polish.

---

## 6. PDF Exporter (`WeasyPrint`)

**New files:** `core/studio/documents/exporter_pdf.py`, `core/studio/documents/templates/document_base.html.j2`, `core/studio/documents/templates/document_base.css`

Phase 4 PDF export will use an HTML intermediate representation rendered by WeasyPrint. This keeps the output readable and creates a direct path to future HTML export.

### 6.1 Design Approach

- Convert `DocumentContentTree` to a structured HTML view model
- Render HTML using Jinja2 template
- Apply print-focused CSS
- Convert HTML -> PDF using WeasyPrint

### 6.2 Public API

```python
def export_to_pdf(content_tree: DocumentContentTree, output_path: Path) -> Path:
    ...
```

Helper functions:

- `_document_to_html_model(content_tree) -> dict`
- `_render_html(content_tree) -> str`

### 6.3 HTML Template Structure (MVP)

Template sections:

- Document header (`title`, `doc_type`, optional metadata summary)
- Abstract block
- Recursive section rendering (`h1/h2/h3`, paragraphs)
- Bibliography block
- Optional footer page numbers via CSS `@page`

Example skeleton:

```html
<html>
  <head>
    <meta charset="utf-8" />
    <style>{{ css }}</style>
  </head>
  <body>
    <header class="doc-header">...</header>
    <section class="abstract">...</section>
    <main class="doc-body">...</main>
    <section class="bibliography">...</section>
  </body>
</html>
```

### 6.4 CSS Rules (MVP)

Minimum print CSS:

- Page size: A4 or Letter (pick one default, configurable later; Letter recommended for US default)
- Margins: 0.75in-1in
- Font stack: serif body, sans-serif headings (system fonts)
- Heading spacing and widow/orphan avoidance where supported
- `page-break-inside: avoid` for short sections/tables (future-proof, harmless now)
- Monospace styling for inline code snippets if present in content

### 6.5 WeasyPrint Runtime Handling

PDF export should fail with a controlled error when WeasyPrint/native dependencies are unavailable.

Planned behavior:

- Import WeasyPrint lazily in exporter module or function
- On ImportError / runtime shared-library error:
  - raise `RuntimeError("PDF export unavailable: WeasyPrint runtime dependencies not installed")`
- Orchestrator catches and records export job failure cleanly

This keeps router responses stable and testable while making environment issues explicit.

### 6.6 Why HTML Intermediate Is Required in Phase 4

- Reuses Jinja2 already in project dependencies
- Simplifies PDF rendering compared to low-level drawing libs
- Creates direct extension hook for future HTML export (spec requirement)
- Makes PDF styling deterministic and reviewable in plain templates/CSS

---

## 7. Document Export Validators

**New file:** `core/studio/documents/validator.py`

Phase 4 mirrors the slide "export then validate" pattern. Validators are format-specific and intentionally conservative.

### 7.1 Validator API

```python
def validate_docx(output_path: Path, *, content_tree: DocumentContentTree | None = None) -> dict:
    ...

def validate_pdf(output_path: Path, *, content_tree: DocumentContentTree | None = None) -> dict:
    ...
```

Suggested result contract (parallel to slide validator shape):

```python
{
    "valid": True,
    "format": "docx",
    "errors": [],
    "warnings": [],
    "page_count": 7,                    # for pdf if available
    "paragraph_count": 42,              # for docx if available
    "heading_count": 8,
    "text_present": True,
    "bibliography_present": True,
}
```

### 7.2 DOCX Validation Strategy

Use `python-docx` to open and inspect:

- File exists and opens without exception
- At least one non-empty paragraph
- Title/heading count > 0
- If `content_tree` provided:
  - Heading count roughly matches expected sections (+ bibliography)
  - Bibliography heading present when `bibliography` non-empty

Controlled failure examples:

- Corrupt zip/document XML
- Zero-paragraph output
- Empty file

### 7.3 PDF Validation Strategy

Use `PyMuPDF` (`fitz`, already available via project deps) to validate openability:

- File exists and opens without exception
- `page_count >= 1`
- Extracted text length > minimal threshold
- If `content_tree` provided:
  - Title text appears in first page text (best effort)
  - Bibliography heading appears if bibliography exists

We do not attempt pixel/layout quality validation for docs in Phase 4.

### 7.4 Blocking Policy (Phase 4)

Document export is **blocking** on format open-validation:

- `valid == True` -> export job `completed`
- `valid == False` -> export job `failed`

Warnings are non-blocking (e.g., unusually short document, missing optional metadata).

---

## 8. Orchestrator Changes

**File:** `core/studio/orchestrator.py`

The orchestrator already supports document draft generation. Phase 4 extends it with document normalization and export dispatch.

### 8.1 Draft Path: Document Normalization

Update `approve_and_generate_draft()`:

- After `validate_content_tree()` for document artifacts:
  - Run `normalize_document_content_tree(...)`
- Ensure normalized content is what gets persisted and revisioned

No changes to the revision model or storage schema are required.

### 8.2 Export Dispatch Matrix

Current behavior: slide-only export (`pptx`) with slide theme + layout validation.

Phase 4 behavior:

| Artifact Type | Supported Formats | Exporter | Validator |
|---------------|-------------------|----------|-----------|
| `slides` | `pptx` | `core.studio.slides.exporter.export_to_pptx` | `core.studio.slides.validator.validate_pptx` |
| `document` | `docx` | `core.studio.documents.exporter_docx.export_to_docx` | `core.studio.documents.validator.validate_docx` |
| `document` | `pdf` | `core.studio.documents.exporter_pdf.export_to_pdf` | `core.studio.documents.validator.validate_pdf` |
| `sheet` | none (Phase 4) | n/a | n/a |

### 8.3 Parameter Gating by Artifact Type

Slides-only export options should not silently affect document exports.

Policy:

- `theme_id`: ignored or rejected for documents. Recommended: reject with `ValueError` for clarity.
- `strict_layout`: ignored or rejected for documents. Recommended: reject to avoid misleading behavior.
- `generate_images`: rejected for documents.

Recommended error messages:

- `"theme_id is only supported for slides exports"`
- `"strict_layout is only supported for slides PPTX exports"`
- `"generate_images is only supported for slides PPTX exports"`

### 8.4 Export Job Lifecycle (Unchanged Pattern)

Retain the Phase 2-3 export job lifecycle exactly:

1. Validate artifact exists and has `content_tree`
2. Create pending `ExportJob`
3. Persist job + append summary to artifact
4. Run exporter
5. Run format validator
6. Mark completed or failed with `validator_results` / `error`
7. Persist job and refresh artifact export summary status

Consistency here reduces regression risk and keeps polling UI behavior unchanged.

### 8.5 Pseudocode: New Document Export Branch

```python
if artifact.type == ArtifactType.document:
    from core.schemas.studio_schema import DocumentContentTree
    from core.studio.documents.exporter_docx import export_to_docx
    from core.studio.documents.exporter_pdf import export_to_pdf
    from core.studio.documents.validator import validate_docx, validate_pdf

    if export_format not in {ExportFormat.docx, ExportFormat.pdf}:
        raise ValueError(f"Export format {export_format.value} only supports slides artifacts")

    doc_tree = DocumentContentTree(**artifact.content_tree)
    doc_tree = normalize_document_content_tree(doc_tree, outline=artifact.outline, artifact_id=artifact.id)

    output_path = self.storage.get_export_file_path(...)
    if export_format == ExportFormat.docx:
        export_to_docx(doc_tree, output_path)
        validation = validate_docx(output_path, content_tree=doc_tree)
    else:
        export_to_pdf(doc_tree, output_path)
        validation = validate_pdf(output_path, content_tree=doc_tree)
```

### 8.6 Error Message Cleanup (Optional but Recommended)

Current unsupported-format messages are slide-centric. In Phase 4, revise messages to be artifact-aware, for example:

- `"Export format pdf is not supported for artifact type slides"`
- `"Export format pptx is not supported for artifact type document"`
- `"Exports are not yet supported for artifact type sheet"`

This improves API clarity and test precision.

---

## 9. Router Changes

**File:** `routers/studio.py`

The router already exposes the right endpoints. Phase 4 mostly updates format parsing behavior and download response metadata.

### 9.1 `ExportArtifactRequest` Behavior

Current request model is slides-oriented:

```python
class ExportArtifactRequest(BaseModel):
    format: str = "pptx"
    theme_id: Optional[str] = None
    strict_layout: bool = False
    generate_images: bool = False
```

Phase 4 keeps this shape for backward compatibility, but document export behavior is enforced in the orchestrator.

Why keep the same request model in Phase 4:

- Avoids breaking the existing slides export UI/client code
- Minimizes API churn while adding document formats
- Defers format-specific request models until a future typed export API redesign

### 9.2 Export Format Parsing

With `ExportFormat.docx/pdf` added, router behavior changes from rejecting `"pdf"` to accepting it and delegating support checks by artifact type to the orchestrator.

Test impact:

- Update `tests/test_studio_export_router.py` cases that currently assert `"pdf"` is unsupported at enum parse time
- Replace with artifact-type-specific unsupported combo tests

### 9.3 Dynamic Download Media Type

Current `download_export()` always returns PPTX media type. Phase 4 must return a media type based on `job.format`.

Planned helper:

```python
_EXPORT_MEDIA_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
}
```

Then:

- `media_type = _EXPORT_MEDIA_TYPES.get(job.format.value, "application/octet-stream")`
- `filename = f"{artifact_id}.{job.format.value}"`

### 9.4 Route Ordering

No changes required to route ordering. The existing static-before-parameterized ordering comments remain correct.

---

## 10. Prompt Improvements (Documents)

**File:** `core/studio/prompts.py`

Phase 4 does not require a new prompt module, but the document prompts need stronger constraints to pass deterministic structure and export gates.

### 10.1 Outline Prompt: Phase 4 Doc Type Focus

Update document outline guidance to:

- Emphasize supported Phase 4 types (`technical_spec`, `report`, `proposal`)
- Instruct the model to infer and include a doc type in descriptions/structure via `parameters["doc_type"]`
- Require required core sections for each type
- Keep heading hierarchy practical (max depth 3)

Example additions to document outline guidance:

```text
- Phase 4 supported doc types: technical_spec, report, proposal
- If unsure, default to report
- Ensure the outline contains the required core sections for the selected doc type
- Limit nesting to 3 levels maximum
- Each top-level item should be a major section with 1-2 sentence description
```

### 10.2 Draft Prompt: Stronger Document Schema Rules

Current document draft guidance is minimal. Add explicit rules for:

- Matching `doc_type` to the approved outline parameters
- Multi-paragraph, substantive section bodies (no filler)
- Citation keys and bibliography synchronization
- Bibliography entry fields (`key`, `title`, optional `author/url`)
- Placeholder provenance compatibility via metadata keys

Suggested additions:

```text
- Use the approved outline's document type (technical_spec|report|proposal)
- Every citation key referenced in sections must appear in bibliography
- If no real sources are available, create placeholder bibliography entries with stable citation keys
- Do not leave sections empty; write specific, concrete content
- Avoid placeholders like TBD, Lorem ipsum, To be added
- metadata.provenance_slots may be included and should reference bibliography citation_key values
```

### 10.3 Document-Type-Aware Draft Examples (Optional but Recommended)

Add a short doc-type hint block based on `outline.parameters["doc_type"]`:

- `technical_spec`: requirements, architecture, implementation, risks
- `report`: background, findings, recommendations, conclusion
- `proposal`: objectives, scope, approach, timeline, budget

This should be additive and not alter slide prompts.

---

## 11. Frontend Outline-First UI Hooks (Minimal Phase 4)

Phase 4 requires "outline-first UI hooks" for documents, not a full document editor. The current Studio UI already supports:

- Creating document artifacts
- Viewing outlines and approving/rejecting
- Rendering a basic `DocumentViewer`

The missing piece is document export access and export job visibility/behavior parity.

### 11.1 `StudioWorkspace.tsx` - Enable Document Export Button

**File:** `platform-frontend/src/features/studio/StudioWorkspace.tsx`

Current behavior only shows export for `slides`.

Phase 4 change:

- Show export control for `artifact.type === "document"` as well
- Keep slide-specific theme picker behavior unchanged

Implementation options:

1. Extend existing `ExportButton` to accept `artifactType`
2. Add a separate lightweight `DocumentExportButton`

Recommended for speed: extend `ExportButton` with an `artifactType` prop and switch UI mode internally.

### 11.2 `ExportPanel.tsx` - Document Export Mode

**File:** `platform-frontend/src/features/forge/components/ExportPanel.tsx`

Current component is slide/theme-centric (theme picker + strict layout + image generation toggles).

Phase 4 document mode should:

- Offer format choices: `DOCX`, `PDF`
- Hide slide-only controls:
  - Theme picker
  - Strict layout toggle
  - Generate images toggle
- Reuse existing export job polling, status display, and download link rendering

Low-risk approach:

- Add `artifactType` prop
- Branch UI:
  - `slides` -> current behavior
  - `document` -> simple dialog with 2 buttons or segmented control

### 11.3 `store/index.ts` - Generalize `startExport(...)`

**File:** `platform-frontend/src/store/index.ts`

Current `startExport(...)` hardcodes `"pptx"`.

Phase 4 change:

- Accept `format` parameter
- Accept optional slides-only args (`themeId`, `strictLayout`, `generateImages`)
- Preserve polling behavior and auto-download on completion

Proposed signature:

```ts
startExport: async (
  artifactId: string,
  format: "pptx" | "docx" | "pdf",
  options?: {
    themeId?: string;
    strictLayout?: boolean;
    generateImages?: boolean;
  }
) => Promise<void>
```

### 11.4 `lib/api.ts` - Reuse Existing Generic Format Support

**File:** `platform-frontend/src/lib/api.ts`

`api.exportArtifact(...)` already accepts a generic `format: string`. Minimal changes:

- Ensure document export callers pass `"docx"` / `"pdf"`
- Optionally avoid sending slides-only params for document exports

### 11.5 UI Scope Guardrails (Phase 4)

Not in scope for Phase 4:

- Rich document editing UI
- Citation editing UI
- Provenance browser
- Side-by-side PDF preview

The UI goal is export access from the existing outline-first document workflow.

---

## 12. Dependencies and Environment

### 12.1 Python Dependencies

**File:** `pyproject.toml`

Add:

- `python-docx`
- `weasyprint`

Example (version pins illustrative):

```toml
"python-docx>=1.1.2",
"weasyprint>=62.3",
```

Validation uses existing dependencies where possible:

- `python-docx` for DOCX open-validation
- `PyMuPDF` (`fitz`, via existing `pymupdf4llm` / `pymupdf`) for PDF open-validation

### 12.2 WeasyPrint Runtime Notes (CI / Local)

WeasyPrint may require system libraries depending on environment. Phase 4 plan must include CI readiness work:

- Verify CI image/runtime has required shared libraries for WeasyPrint
- If missing, add CI setup step (preferred)
- Export should fail with controlled error if runtime is unavailable

This is not optional for the Phase 4 gate because PDF export must open without corruption.

### 12.3 No Frontend Dependency Changes Required (Likely)

Phase 4 document export UI can reuse existing modal/dialog infrastructure and HTTP client code. No new frontend npm packages are expected.

---

## 13. Test Plan

Phase 4 test coverage should follow the same pattern used in Phases 2-3: focused unit/component tests plus acceptance/integration extensions using the existing project gate files.

### `tests/test_studio_documents_types.py` - 12 tests (NEW)

Covers doc type registry and outline normalization:

- Resolve `doc_type` from parameters
- Keyword inference fallback from prompt
- Default fallback to `report`
- Required section insertion for `technical_spec`
- Required section insertion for `proposal`
- Required section insertion for `report`
- Section count clamping (min/max)
- Stable id assignment for inserted sections
- Depth clamp to max 3
- Unsupported `doc_type` fallback behavior
- Idempotent normalization (running twice yields same result)
- Preserve user-provided section order when valid

### `tests/test_studio_documents_generator.py` - 16 tests (NEW)

Covers document draft normalization:

- Abstract synthesized when missing
- Empty/placeholder text normalization
- Section level normalization
- Duplicate section id repair
- Citation key extraction from sections
- Bibliography deduplication by key
- Orphan citation key placeholder bibliography entry insertion
- Provenance slot auto-build from bibliography
- Preserve existing linked provenance slots
- Unsupported `doc_type` normalization fallback
- Outline-to-section alignment best-effort behavior
- Recursive subsection normalization
- Empty sections with subsections remain valid
- Normalization idempotence
- Metadata merge preserves existing keys
- Content tree remains Pydantic-valid after normalization

### `tests/test_studio_documents_exporter_docx.py` - 12 tests (NEW)

Covers DOCX export:

- Creates file and parent directories
- Opens with `python-docx`
- Title/abstract rendering
- Recursive heading rendering (levels 1-3)
- Paragraph split rendering
- Bibliography section rendering
- Citation keys rendered inline
- Handles empty bibliography
- Rejects empty section list (or inserts safe fallback, whichever implementation chooses)
- Sanitizes invalid control chars
- Non-ASCII content round-trip safety (if supported by implementation)
- Deterministic export succeeds on normalized tree

### `tests/test_studio_documents_exporter_pdf.py` - 10 tests (NEW)

Covers PDF export:

- Creates file and parent directories
- PDF opens with `fitz`
- Page count >= 1
- Title text present
- Bibliography text present when expected
- Recursive section rendering text present
- Handles empty bibliography
- Controlled failure when WeasyPrint unavailable (monkeypatched import/runtime)
- CSS/template render path invoked
- Deterministic export succeeds on normalized tree

### `tests/test_studio_documents_validator.py` - 12 tests (NEW)

Covers validators directly:

- `validate_docx()` success path
- `validate_docx()` corrupt file failure
- `validate_docx()` empty file failure
- `validate_docx()` detects missing bibliography heading warning
- `validate_pdf()` success path
- `validate_pdf()` corrupt file failure
- `validate_pdf()` empty file failure
- `validate_pdf()` no text extracted failure
- `validate_pdf()` title best-effort check warning/failure behavior
- Result contract includes `valid/errors/warnings`
- Result contract includes counts when available
- Validator functions never throw on malformed input (return structured failure)

### `tests/test_studio_orchestrator.py` - +12 tests (MODIFY)

Add/modify document pipeline tests:

- Document outline normalization runs before save
- Document draft normalization runs before revision persistence
- Document export `docx` completes successfully
- Document export `pdf` completes successfully (with mocked exporter/validator)
- Document export invalid format for document (`pptx`) fails cleanly
- Sheet export still unsupported in Phase 4
- Document export updates export job summary status
- Document export failure preserves artifact `content_tree` / `revision_head_id`
- Document export rejects `theme_id`
- Document export rejects `generate_images`
- Document export rejects `strict_layout`
- Document export stores validator results on success/failure

### `tests/test_studio_export_router.py` - +10 tests (MODIFY)

Add/modify router tests:

- Accept `docx` format parsing and dispatch
- Accept `pdf` format parsing and dispatch
- Artifact-type-specific unsupported combo returns 400 (delegated orchestrator error)
- Download DOCX uses correct media type
- Download PDF uses correct media type
- Download filename extension matches job format
- Slides-only params on doc export return 400 (if enforced in orchestrator)
- Invalid `export_job_id` still rejected
- Global export lookup returns docx/pdf jobs
- Existing PPTX route behavior unchanged

### `tests/test_studio_schema.py` - +6 tests (MODIFY)

- `ExportFormat("docx")` accepted
- `ExportFormat("pdf")` accepted
- Document metadata with `provenance_slots` passes
- Minimal bibliography normalization-compatible keys survive round-trip
- Legacy document tree without metadata still valid
- Document content tree round-trip preserves provenance slot metadata

### Acceptance Tests - `tests/acceptance/p04_forge/test_exports_open_and_render.py` - +4 tests (MODIFY)

Add tests (next numbering after Phase 3 currently ends at `test_21`):

- `test_22_document_docx_export_produces_openable_file`
- `test_23_document_pdf_export_produces_openable_file`
- `test_24_document_export_job_status_and_validator_results`
- `test_25_document_export_rejects_unsupported_format_combo` (e.g., document -> pptx)

These satisfy the Phase 4 acceptance gate for DOCX/PDF open-without-corruption.

### Integration Tests - `tests/integration/test_forge_research_to_slides.py` - +4 tests (MODIFY)

Despite the filename, extend with document scenarios:

- Outline -> document draft -> DOCX export pipeline
- Outline -> document draft -> PDF export pipeline
- Document draft normalization creates provenance slots from bibliography placeholders
- Export failure (mock WeasyPrint runtime missing) surfaces graceful error + failed job state

### Test Count Summary (Planned)

- New test files: 5
- Modified test files: 5
- New tests added: ~84-94

This keeps Phase 4 coverage comparable to Phases 2-3 while focusing on the new document surface area.

### Gate Commands

```bash
# Phase 4 new document unit/component tests
uv run pytest \
  tests/test_studio_documents_types.py \
  tests/test_studio_documents_generator.py \
  tests/test_studio_documents_exporter_docx.py \
  tests/test_studio_documents_exporter_pdf.py \
  tests/test_studio_documents_validator.py

# Modified core/router/schema tests
uv run pytest \
  tests/test_studio_orchestrator.py \
  tests/test_studio_export_router.py \
  tests/test_studio_schema.py

# Acceptance + integration project gates
uv run pytest \
  tests/acceptance/p04_forge/test_exports_open_and_render.py \
  tests/integration/test_forge_research_to_slides.py

# Baseline non-regression
scripts/test_all.sh quick
```

---

## 14. Day-by-Day Execution Sequence (Days 11-13)

### Day 11: Document Structure and Draft Normalization

Primary goal: make outline-first document generation deterministic and Phase 4-core-type aware.

Tasks:

1. Add `ExportFormat.docx/pdf` in `core/schemas/studio_schema.py`
2. Implement `core/studio/documents/types.py` registry and type resolution helpers
3. Implement `normalize_document_outline()` in `core/studio/documents/generator.py`
4. Implement bibliography/provenance normalization helpers in `core/studio/documents/citations.py`
5. Strengthen document prompt guidance in `core/studio/prompts.py`
6. Wire outline normalization into `generate_outline()` (document only)
7. Wire document draft normalization into `approve_and_generate_draft()`
8. Add/green:
   - `tests/test_studio_documents_types.py`
   - `tests/test_studio_documents_generator.py`
   - relevant `tests/test_studio_orchestrator.py` cases

Checkpoint:

- Document outlines consistently include required sections for `technical_spec`, `report`, `proposal`
- Approved document drafts produce normalized content trees and revisions

### Day 12: DOCX/PDF Exporters + Validators + Orchestrator Export Dispatch

Primary goal: backend document export pipeline working end-to-end with open-validation.

Tasks:

1. Implement `export_to_docx()` in `core/studio/documents/exporter_docx.py`
2. Implement HTML template/CSS + `export_to_pdf()` in `core/studio/documents/exporter_pdf.py`
3. Implement `validate_docx()` and `validate_pdf()` in `core/studio/documents/validator.py`
4. Extend orchestrator export dispatch for document `docx`/`pdf`
5. Enforce artifact-type/format compatibility and slides-only param gating
6. Add/green:
   - `tests/test_studio_documents_exporter_docx.py`
   - `tests/test_studio_documents_exporter_pdf.py`
   - `tests/test_studio_documents_validator.py`
   - document export cases in `tests/test_studio_orchestrator.py`

Checkpoint:

- Backend can export a stored document artifact to DOCX/PDF
- Export jobs correctly persist `completed`/`failed` and validator results

### Day 13: Router + Frontend Hooks + Acceptance/Integration Gates

Primary goal: user-accessible document export from Studio UI and passing Phase 4 gates.

Tasks:

1. Update router format handling and dynamic download media types in `routers/studio.py`
2. Update frontend export UI for document artifacts:
   - `StudioWorkspace.tsx`
   - `ExportPanel.tsx`
   - `store/index.ts`
   - `lib/api.ts` (minimal adjustments)
3. Extend router tests and schema tests
4. Add acceptance tests `test_22`-`test_25`
5. Extend integration test file with document scenarios
6. Run acceptance/integration + baseline regression
7. Perform manual smoke check:
   - create document outline
   - approve document draft
   - export DOCX and PDF
   - open/download artifacts via Studio routes/UI

Checkpoint (Phase 4 complete):

- Prompt-to-document works end-to-end with DOCX/PDF export
- Acceptance tests confirm both formats open without corruption

---

## 15. Exit Criteria

Phase 4 is complete when all of the following are true:

- Document generator MVP supports Phase 4 core types:
  - `technical_spec`
  - `report`
  - `proposal`
- Document outline-first workflow is fully functional:
  - outline generated
  - user approves outline
  - document draft generated and revision persisted
- `POST /studio/{artifact_id}/export` supports:
  - document -> `docx`
  - document -> `pdf`
- `GET /studio/{artifact_id}/exports/{export_job_id}/download` returns correct files/media types for DOCX/PDF
- DOCX and PDF exports pass open-validation and are not corrupted
- Citation/provenance slots are stored in document metadata (minimal plumbing)
- Phase 4 unit/acceptance/integration tests pass
- Existing slides PPTX export behavior remains non-regressed

This matches the Phase 4 20-day-plan exit criteria: prompt-to-document works end-to-end with DOCX/PDF export.

---

## 16. Risks and Mitigations

### Risk 1: WeasyPrint runtime dependency issues in CI/local

Mitigation:

- Add explicit dependency/runtime check and controlled export failure message
- Validate PDF output with `fitz` in tests
- Ensure CI image/setup includes required shared libraries before Phase 4 gate runs

### Risk 2: LLM-generated document structure variability breaks exporters

Mitigation:

- Add deterministic outline normalization and draft normalization layers
- Exporters consume normalized trees only
- Add unit tests for malformed/partial structures

### Risk 3: Citation/provenance scope creep

Mitigation:

- Limit Phase 4 to placeholder provenance slots stored in `metadata`
- Defer full citation style formatting and Oracle linking to later phases
- Keep bibliography rendering simple and deterministic

### Risk 4: Frontend export UI regression for slides

Mitigation:

- Preserve slide export mode behavior in `ExportPanel.tsx`
- Add document mode as additive branch
- Keep store/API signatures backward-compatible where possible

### Risk 5: Router/API ambiguity for format and parameter compatibility

Mitigation:

- Centralize compatibility checks in orchestrator
- Use explicit error messages for unsupported artifact/format combos and slides-only params
- Add router tests for mixed-parameter cases

---

## 17. Deferred Items (Explicitly Not in Phase 4)

- Citation style renderers (APA/MLA/Chicago/IEEE formatting rules)
- Footnotes/endnotes in DOCX/PDF
- Google Docs export
- Markdown/LaTeX export
- Document diff visualization
- Comment/suggestion annotations
- Collaborative editing locks/conflict warnings
- Rich document template/themes (branded DOCX/PDF styles)
- Oracle provenance hydration into citation slots

---

## 18. Phase 5+ Extension Hooks

Phase 4 should leave clear extension points for Sheets MVP (Phase 5) and Edit Loop (Phase 6).

### 18.1 Reusable Export Dispatch Pattern for Sheets

The artifact-type/format dispatch added in `orchestrator.py` should make adding `sheet -> xlsx/csv` straightforward:

- Add enum values
- Add `core/studio/sheets/exporter.py`
- Add validators
- Register compatibility matrix

### 18.2 HTML Intermediate for Future Document HTML Export

The WeasyPrint HTML template path can later support:

- `document -> html` export with the same template/view model
- Shared CSS between HTML and PDF rendering

### 18.3 Provenance Slot Upgrade Path

`metadata.provenance_slots` is intentionally shaped to map to a future typed `ResearchProvenance` model:

- `citation_key` <-> bibliography key
- `slot_id` <-> provenance entry id
- `status` enables progressive enrichment (`placeholder` -> `linked`)

### 18.4 Frontend Export UI Generalization

The Phase 4 `ExportPanel` document mode can become the template for Phase 5 sheet export mode (format picker + polling/download history) while retaining slide-specific advanced options.

---

## Appendix A: Key Existing Files Referenced

- `core/schemas/studio_schema.py`
- `core/studio/orchestrator.py`
- `core/studio/prompts.py`
- `core/studio/storage.py`
- `routers/studio.py`
- `platform-frontend/src/features/studio/StudioWorkspace.tsx`
- `platform-frontend/src/features/forge/components/ExportPanel.tsx`
- `platform-frontend/src/store/index.ts`
- `platform-frontend/src/lib/api.ts`
- `tests/test_studio_orchestrator.py`
- `tests/test_studio_export_router.py`
- `tests/test_studio_schema.py`
- `tests/acceptance/p04_forge/test_exports_open_and_render.py`
- `tests/integration/test_forge_research_to_slides.py`

## Appendix B: Example Document Metadata with Provenance Slots (Phase 4)

```json
{
  "doc_title": "API Modernization Technical Spec",
  "doc_type": "technical_spec",
  "abstract": "This document defines the migration plan for the internal API gateway...",
  "sections": [
    {
      "id": "sec1",
      "heading": "Executive Summary",
      "level": 1,
      "content": "We propose a phased migration to a versioned gateway architecture...",
      "subsections": [],
      "citations": ["src_gateway_bench"]
    }
  ],
  "bibliography": [
    {
      "key": "src_gateway_bench",
      "title": "Gateway Benchmark Report 2025",
      "author": "Platform Engineering",
      "url": "https://example.internal/reports/gateway-benchmark-2025",
      "provenance_slot_id": "prov1"
    }
  ],
  "metadata": {
    "audience": "engineering leadership",
    "tone": "technical",
    "doc_type_display": "Technical Spec",
    "citation_style": "inline_bracket",
    "provenance_slots": [
      {
        "slot_id": "prov1",
        "citation_key": "src_gateway_bench",
        "title": "Gateway Benchmark Report 2025",
        "url": "https://example.internal/reports/gateway-benchmark-2025",
        "author": "Platform Engineering",
        "retrieved_at": "2026-02-25T12:00:00Z",
        "source_type": "internal_report",
        "status": "placeholder"
      }
    ],
    "export_hints": {
      "toc": false,
      "page_numbers": true
    }
  }
}
```

## Appendix C: Example Document Export Validator Result (Success)

```json
{
  "valid": true,
  "format": "pdf",
  "errors": [],
  "warnings": [],
  "page_count": 6,
  "heading_count": 8,
  "text_present": true,
  "bibliography_present": true
}
```

## Appendix D: Example Document Export Validator Result (Failure)

```json
{
  "valid": false,
  "format": "docx",
  "errors": [
    "DOCX file could not be opened: Package not found or invalid zip archive"
  ],
  "warnings": [],
  "paragraph_count": 0,
  "heading_count": 0,
  "text_present": false,
  "bibliography_present": false
}
```

