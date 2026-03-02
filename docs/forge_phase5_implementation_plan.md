# Forge Phase 5 — Implementation Plan: Sheets MVP + Data Upload Analysis + XLSX/CSV Export (Days 14-15)

## Context

Phase 1 (Days 1-5) established the Forge studio foundation: canonical Pydantic schemas in `core/schemas/studio_schema.py`, outline-first orchestration in `core/studio/orchestrator.py`, file-based artifact/revision persistence in `core/studio/storage.py`, prompt templates in `core/studio/prompts.py`, and the core Studio API routes in `routers/studio.py`.

Phase 2 (Days 6-8) delivered the Slides MVP: deterministic slide planning, curated theme support, PPTX export, export job lifecycle tracking, and export/download endpoints.

Phase 3 (Days 9-10) completed the Slides quality pass: 100+ themes via variants, native charts, speaker notes repair, and blocking slide layout-quality validation.

Phase 4 (Days 11-13) delivered the Docs MVP: document type registry with outline normalization, DOCX export via `python-docx`, PDF export via `xhtml2pdf` (HTML intermediate + Jinja2 template), HTML export with optional hero image generation, citation/provenance slot plumbing, and document draft normalization with bibliography reconciliation.

With Phase 4 complete, the platform now has:

- A working outline-first flow for all three artifact types (`slides`, `document`, `sheet`)
- Sheet schema support (`SheetContentTree`, `SheetTab`) and basic sheet draft generation via LLM
- Sheet outline/draft prompts already defined in `prompts.py` (lines 121-128 outline guidance, lines 248-269 draft schema)
- A mature export pipeline pattern (job creation, storage, validation, download) for slides (`pptx`) and documents (`docx`, `pdf`, `html`)
- A proven artifact-type/format dispatch matrix in the orchestrator with parameter gating
- Frontend export UI with artifact-type-aware format picker dialog and polling/download flow

Phase 5 focuses on turning the existing sheet outline/draft capability into a usable Sheets MVP with XLSX/CSV export, adding a data upload analysis pipeline, and hardening sheet generation with formula validation and normalization.

This plan is derived from:

- `docs/forge_20_day_plan.md` (Phase 5 scope, gates, exit criteria)
- `docs/forge_specs.md` (FR-S1, FR-S2, FR-S3, FR-S4; FR-SH1, FR-SH2, FR-SH3, FR-SH5)
- Current Phase 4 implementation state in `core/studio/`, `routers/studio.py`, `platform-frontend/src/features/`

### Phase 5 Goals (from plan/specs)

- Sheets generation normalization for formula validity and tab consistency
- Upload analysis pipeline for CSV/Excel/JSON (summary stats, correlations/trends, anomaly flags, pivot/crosstab)
- Sheet export dispatch in orchestrator (`sheet -> xlsx/csv`)
- XLSX exporter via `openpyxl`
- CSV exporter for primary tab output
- Upload-analysis API endpoint in `routers/studio.py`
- Frontend: minimal sheet export picker + upload button in Studio workspace
- Tests across schema, sheets modules, orchestrator, router, acceptance, integration

### Scope Boundaries

**In scope:**

- Sheet generation normalization for formula validity and tab consistency
- Upload ingestion (`.csv`, `.xlsx`, `.json`) and deterministic analysis outputs
- Sheet export dispatch in orchestrator (`sheet -> xlsx/csv`)
- XLSX exporter via `openpyxl`
- CSV exporter for primary tab output
- Upload-analysis API endpoint in `routers/studio.py`
- Frontend: minimal sheet export picker + upload button in Studio workspace
- Tests across schema, sheets modules, orchestrator, router, acceptance, integration

**Out of scope:**

- Google Sheets export/API integration
- Advanced BI features (forecasting, clustering, ML-driven anomaly models)
- Multi-file merge workflows
- Real-time collaborative editing for sheets (Phase 6+)
- Rich spreadsheet chart rendering in UI (only data analysis + export this phase)

### Codebase Patterns Referenced

| Pattern | Source File | What to Replicate |
|---------|-------------|-------------------|
| Backward-safe schema evolution with optional fields | `core/schemas/studio_schema.py` | Add xlsx/csv formats and sheet analysis models without breaking existing artifacts |
| Export job lifecycle (pending -> completed/failed) | `core/studio/orchestrator.py` | Reuse identical job creation, persistence, and summary-update flow for sheets |
| `_VALID_COMBOS` artifact-type/format dispatch matrix | `core/studio/orchestrator.py` (line 246) | Extend with `sheet: {xlsx, csv}` using the same validation pattern |
| Parameter gating by artifact type | `core/studio/orchestrator.py` (lines 259-266) | Reject `theme_id`, `strict_layout`, `generate_images` for sheet exports |
| File-based export persistence layout | `core/studio/storage.py` | Reuse `{artifact_id}/exports/{job_id}.{fmt}` for xlsx/csv outputs |
| Router request validation + error translation | `routers/studio.py` | Keep `HTTPException` mapping and UUID validation behavior for upload endpoint |
| `_EXPORT_MEDIA_TYPES` dynamic download types | `routers/studio.py` (line 301) | Extend with xlsx and csv media types |
| Content tree normalization hook in orchestrator | `core/studio/orchestrator.py` (lines 141-170) | Add sheet normalization after `validate_content_tree()` in `approve_and_generate_draft()` |
| Prompt specialization by artifact type | `core/studio/prompts.py` | Strengthen existing sheet prompts with formula/formatting/integrity rules |
| Format picker dialog by artifact type | `platform-frontend/src/features/forge/components/ExportPanel.tsx` | Add `SheetFormatPickerDialog` following the `DocFormatPickerDialog` pattern |
| Generalized `startExport(format, options)` action | `platform-frontend/src/store/index.ts` | Reuse existing generic export flow; add `analyzeSheetUpload` action |

---

## 1. Directory & File Structure

```
Arcturus/
├── core/
│   ├── schemas/
│   │   └── studio_schema.py                                   # MODIFY - ExportFormat (xlsx/csv), SheetAnalysisReport models, SheetContentTree extension
│   └── studio/
│       ├── orchestrator.py                                    # MODIFY - sheet export dispatch + normalization hook + upload analysis + _VALID_COMBOS + param gating
│       ├── prompts.py                                         # MODIFY - strengthen sheet draft prompt with formula/formatting/integrity rules
│       └── sheets/
│           ├── __init__.py                                    # NEW - package exports
│           ├── types.py                                       # NEW - TabularDataset dataclass, analysis threshold constants
│           ├── generator.py                                   # NEW - normalize_sheet_content_tree() for tab/formula/row normalization
│           ├── formulas.py                                    # NEW - formula syntax validation, cell ref extraction, tab-level formula validation
│           ├── ingest.py                                      # NEW - CSV/XLSX/JSON upload ingestion with guardrails
│           ├── analysis.py                                    # NEW - deterministic analysis: summary stats, correlations, trends, anomalies, pivot
│           ├── exporter_xlsx.py                               # NEW - XLSX export via openpyxl
│           ├── exporter_csv.py                                # NEW - CSV export for primary tab
│           └── validator.py                                   # NEW - validate_xlsx(), validate_csv()
├── routers/
│   └── studio.py                                              # MODIFY - analyze-upload endpoint, _EXPORT_MEDIA_TYPES extension
├── platform-frontend/
│   └── src/
│       ├── features/studio/StudioWorkspace.tsx               # MODIFY - add ExportButton for sheet artifacts + Upload Data action
│       ├── features/forge/components/ExportPanel.tsx         # MODIFY - SheetFormatPickerDialog, remove sheet exclusion
│       ├── lib/api.ts                                         # MODIFY - analyzeSheetUpload(artifactId, file) using FormData
│       └── store/index.ts                                     # MODIFY - analyzeSheetUpload action that updates activeArtifact
├── tests/
│   ├── test_studio_sheets_ingest.py                           # NEW - format parsing + normalization + guardrails
│   ├── test_studio_sheets_formulas.py                         # NEW - syntax/ref validation
│   ├── test_studio_sheets_analysis.py                         # NEW - summary/correlation/trend/anomaly/pivot fixtures
│   ├── test_studio_sheets_generator.py                        # NEW - normalization rules
│   ├── test_studio_sheets_exporter_xlsx.py                    # NEW - sheet/formula rendering
│   ├── test_studio_sheets_exporter_csv.py                     # NEW - primary-tab export
│   ├── test_studio_sheets_validator.py                        # NEW - open-validation pass/fail cases
│   ├── test_studio_orchestrator.py                            # MODIFY - sheet export lifecycle + param gating + upload-analysis revision
│   ├── test_studio_export_router.py                           # MODIFY - xlsx/csv accepted + upload endpoint + download media types
│   ├── test_studio_schema.py                                  # MODIFY - ExportFormat xlsx/csv + SheetAnalysisReport serialization
│   ├── acceptance/p04_forge/test_exports_open_and_render.py   # MODIFY - add sheet export + upload-analysis acceptance cases (test_26+)
│   └── integration/test_forge_research_to_slides.py           # MODIFY - add sheet pipeline integration scenarios (test_22+)
├── pyproject.toml                                              # MODIFY - openpyxl, python-multipart
└── docs/
    └── forge_phase5_implementation_plan.md                    # THIS DOCUMENT
```

**Total (planned):** 9 new backend files + 4 modified backend/router files + 4 modified frontend files + 7 new test files + 5 modified test files

Notes:

- The integration test filename remains slides-oriented (`test_forge_research_to_slides.py`) for continuity with the SPS gate file path; Phase 5 extends it with sheet scenarios.
- The acceptance test filename remains under `p04_forge/` because all Forge acceptance tests share the same gate file; Phase 5 adds tests starting at `test_26`.

---

## 2. Schema Additions

**File:** `core/schemas/studio_schema.py`

Phase 5 requires schema changes for export formats, analysis models, and a content tree extension. Existing sheet models (`SheetTab`, `SheetContentTree`) are already defined and sufficient for generation; Phase 5 adds analysis output models and export format support.

### 2.1 `ExportFormat` Enum Expansion

Current code supports `pptx`, `docx`, `pdf`, `html`.

Phase 5 update:

```python
class ExportFormat(str, Enum):
    pptx = "pptx"
    docx = "docx"
    pdf = "pdf"
    html = "html"
    xlsx = "xlsx"
    csv = "csv"
```

Rationale:

- Enables router/orchestrator parsing of sheet export formats
- Preserves the existing export job model and storage layout
- Avoids format-specific router branches outside the orchestrator dispatch

### 2.2 Sheet Analysis Models

New Pydantic models for upload analysis results:

```python
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
```

### 2.3 `SheetContentTree` Extension

Add optional field for analysis results:

```python
class SheetContentTree(BaseModel):
    workbook_title: str
    tabs: List[SheetTab]
    assumptions: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    analysis_report: Optional[SheetAnalysisReport] = None  # NEW
```

### 2.4 Backward Compatibility Rules

- Existing slide and document artifacts and exports continue to deserialize unchanged.
- Existing sheet artifacts without `analysis_report` remain valid (field is optional with `None` default).
- Existing router tests that expect `"xlsx"` or `"csv"` to be unsupported must be updated (behavior changes in Phase 5).
- The `ContentTree` union type and `_CONTENT_TREE_MAP` require no changes — `SheetContentTree` is already registered.

---

## 3. Sheet Types and Data Structures

**New file:** `core/studio/sheets/types.py`

Phase 5 introduces a shared data structure for upload ingestion and a constants module for analysis thresholds.

### 3.1 `TabularDataset` Dataclass

Normalized representation of any uploaded file after ingestion:

```python
from dataclasses import dataclass
from typing import Any, List

@dataclass
class TabularDataset:
    columns: List[str]
    rows: List[List[Any]]
    source_format: str   # "csv", "xlsx", "json"
    source_name: str     # original filename
```

### 3.2 Analysis Threshold Constants

Deterministic constants for analysis module:

```python
ANOMALY_Z_THRESHOLD = 3.0
TREND_EPSILON = 1e-6
MIN_OBSERVATIONS_FOR_CORRELATION = 5
MAX_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_UPLOAD_ROWS = 20_000
MAX_UPLOAD_COLUMNS = 200
```

These are fixed values to ensure deterministic, testable analysis outputs.

---

## 4. Sheet Generation Normalization

**New file:** `core/studio/sheets/generator.py`

The current sheet draft path validates schema but does not enforce sheet quality conventions. Phase 5 adds a deterministic post-generation normalization step before persistence, following the same pattern established by `normalize_document_content_tree()` in Phase 4.

### 4.1 Design Approach

Sheet normalization runs immediately after `validate_content_tree()` succeeds for sheet artifacts, before the content tree is persisted and revisioned. It ensures structural integrity without modifying semantic content.

### 4.2 Public API

```python
def normalize_sheet_content_tree(
    content_tree: SheetContentTree,
) -> SheetContentTree:
    ...
```

### 4.3 Normalization Rules

- Ensure unique tab ids (deduplicate by appending `_2`, `_3`, etc.)
- Ensure unique tab names (deduplicate by appending ` (2)`, ` (3)`, etc.)
- Ensure row widths align with headers (pad short rows with `None`, truncate excess)
- Normalize `column_widths` length to match headers (pad with default `100`, truncate excess)
- Enforce at least one non-empty tab (raise `ValueError` if all tabs are empty)
- Sanitize placeholders (`TBD`, `Lorem ipsum`, `To be added`) with deterministic fallback text
- Run formula validation on each tab via `validate_tab_formulas()` (Section 5)
- Record invalid formula warnings in `analysis_report.warnings` (create report if needed)

### 4.4 Orchestrator Integration Point

In `approve_and_generate_draft()`:

```python
elif artifact.type == ArtifactType.sheet:
    from core.studio.sheets.generator import normalize_sheet_content_tree
    content_tree_model = normalize_sheet_content_tree(content_tree_model)
```

Note:

- This follows the same conditional block pattern used for slides (lines 157-163) and documents (lines 166-170) in the current orchestrator.
- The normalization is idempotent — running it twice yields the same result.

---

## 5. Formula Validation

**New file:** `core/studio/sheets/formulas.py`

Phase 5 adds deterministic formula validation to catch invalid syntax and out-of-bounds cell references before export.

### 5.1 Public API

```python
def validate_formula_syntax(formula: str) -> bool:
    """Check that formula starts with '=' and has balanced parentheses."""
    ...

def extract_cell_refs(formula: str) -> list[str]:
    """Extract all cell references (e.g., 'A1', 'B2:C10') from a formula."""
    ...

def validate_formula_refs(formula: str, max_row: int, max_col: int) -> bool:
    """Check that all cell refs in the formula point to valid in-tab coordinates."""
    ...

def validate_tab_formulas(tab: SheetTab) -> list[str]:
    """Validate all formulas in a tab. Returns list of warning messages for invalid formulas."""
    ...
```

### 5.2 Implementation Rules

- Formula must start with `=`
- Cell references use A1 notation; column letters converted to 1-based index
- Cell ranges (`A1:B10`) validated at both endpoints
- `max_row` = `len(tab.rows) + 1` (header row counts as row 1)
- `max_col` = `len(tab.headers)`
- `validate_tab_formulas()` iterates `tab.formulas` dict:
  - Formula **references** (cell addresses inside the `=...` expression) must point to cells within current data bounds (`max_row` × `max_col`) OR to other formula cell positions
  - Formula **keys** (the target cell address where the result is placed) may extend up to one column beyond `max_col` and one row beyond `max_row`, allowing derived columns and totals rows
  - Invalid formulas are removed from `tab.formulas` in the normalization pass
  - Returns warning strings like `"Removed invalid formula at C15: reference out of bounds"`

---

## 6. Upload Analysis Agent

Phase 5 introduces a two-stage upload analysis pipeline: ingestion normalizes raw file data, and analysis produces deterministic statistical outputs.

### 6.1 Ingestion (`core/studio/sheets/ingest.py`)

**New file:** `core/studio/sheets/ingest.py`

Public API:

```python
def ingest_upload(
    filename: str,
    content_bytes: bytes,
    content_type: str,
) -> TabularDataset:
    ...
```

Supported formats:

- **CSV** via `csv` module (auto-detect delimiter with `csv.Sniffer`)
- **XLSX** via `openpyxl.load_workbook(data_only=True)` (first sheet only)
- **JSON** as list-of-objects or `{"rows": [...], "columns": [...]}` shape

Input guardrails:

- Max file size: 10 MB (`MAX_UPLOAD_SIZE_BYTES`)
- Max rows: 20,000 (`MAX_UPLOAD_ROWS`)
- Max columns: 200 (`MAX_UPLOAD_COLUMNS`)
- Reject empty datasets with controlled `ValueError`
- Reject unsupported file types with controlled `ValueError`

Format detection:

- Primary: `content_type` MIME type
- Fallback: file extension from `filename`
- Supported MIME types: `text/csv`, `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`, `application/json`

### 6.2 Analysis (`core/studio/sheets/analysis.py`)

**New file:** `core/studio/sheets/analysis.py`

Public API:

```python
def analyze_dataset(dataset: TabularDataset) -> SheetAnalysisReport:
    ...
```

Produces a deterministic `SheetAnalysisReport` with five components:

1. **`summary_stats`**: For each numeric column — count, null_count, mean, median, std, min, max. Uses Python `statistics` module (no numpy dependency).

2. **`correlations`**: Pearson correlation pairs for numeric columns with >= `MIN_OBSERVATIONS_FOR_CORRELATION` non-null observations. Uses manual Pearson formula or `statistics.correlation()` (Python 3.10+).

3. **`trends`**: Slope-based trend classification for numeric series:
   - `slope > TREND_EPSILON` → `"up"`
   - `slope < -TREND_EPSILON` → `"down"`
   - otherwise → `"flat"`
   - Uses simple linear regression (least-squares slope).

4. **`anomalies`**: Z-score based flags for values where `|z| >= ANOMALY_Z_THRESHOLD`. Reports column, row_index, value, and z_score.

5. **`pivot_preview`**: Single pivot/crosstab table from first suitable categorical + numeric pair. Returns `{"index_column": str, "value_column": str, "table": dict}` or `None` if no suitable pair found.

### 6.3 Content Tree Integration (`build_analysis_tabs`)

Helper function to update a sheet artifact after upload analysis:

```python
def build_analysis_tabs(
    dataset: TabularDataset,
    report: SheetAnalysisReport,
) -> list[SheetTab]:
    ...
```

Generates/refreshes tabs:

- `Uploaded_Data` — raw data from the uploaded file
- `Summary_Stats` — one row per numeric column with summary statistics
- `Correlations` — correlation pairs (skipped if empty)
- `Anomalies` — flagged anomaly rows (skipped if empty)
- `Pivot` — pivot/crosstab table (skipped if no suitable pair)

The orchestrator integrates this by:

- Appending/replacing analysis tabs in the existing `content_tree.tabs`
- Setting `content_tree.analysis_report` to the new report
- Creating a new revision with summary: `"Added upload analysis from <filename>"`

---

## 7. XLSX Exporter

**New file:** `core/studio/sheets/exporter_xlsx.py`

Phase 5 XLSX export follows the same exporter pattern established by `export_to_pptx()` and `export_to_docx()`.

### 7.1 Public API

```python
def export_to_xlsx(content_tree: SheetContentTree, output_path: Path) -> None:
    ...
```

Design notes:

- Match the existing exporter style (`export_to_pptx(...)`, `export_to_docx(...)`)
- Create parent directory if missing
- Raise `ValueError` for empty tab list before writing

### 7.2 Rendering Rules

Workbook structure:

- One worksheet per tab, preserving tab ordering from `content_tree.tabs`
- Worksheet name from `tab.name` (truncated to Excel's 31-character limit)

Header row:

- Write `tab.headers` in row 1 with bold font + light fill
- Freeze top row at cell `A2`

Data rows:

- Write `tab.rows` starting at row 2
- Preserve data types: strings, numbers, `None` as empty cells

Column widths:

- Apply from `tab.column_widths` if present
- Auto-fit fallback: `max(len(header) + 4, 12)` characters

Formulas:

- Write formulas from `tab.formulas` dict (key = cell address, value = formula string)
- Formulas are written as-is; `openpyxl` handles Excel formula serialization

### 7.3 Safety

- Sanitize worksheet names (remove invalid characters: `[]:*?/\`)
- Clamp worksheet name length to 31 characters
- Handle empty tabs gracefully (write headers only)

---

## 8. CSV Exporter

**New file:** `core/studio/sheets/exporter_csv.py`

CSV export provides a lightweight single-tab output for sheet artifacts.

### 8.1 Public API

```python
def export_to_csv(content_tree: SheetContentTree, output_path: Path) -> str:
    """Export primary tab to CSV. Returns the exported tab name."""
    ...
```

### 8.2 Rendering Rules

Tab selection:

- Export the first tab that has both headers and at least one row
- If no qualifying tab found, export the first tab (headers only)
- Return the selected tab name for validator metadata

Output format:

- UTF-8 encoding
- Standard CSV dialect (comma-separated, quoted strings with commas/newlines)
- Newline normalization to `\n`
- Header row first, then data rows

Formulas:

- Formulas are not written to CSV (CSV is data-only)
- Formula cell values are replaced with empty string

---

## 9. Validators

**New file:** `core/studio/sheets/validator.py`

Phase 5 mirrors the Phase 4 "export then validate" pattern. Validators are format-specific and intentionally conservative.

### 9.1 Validator API

```python
def validate_xlsx(
    path: Path,
    expected_sheet_names: list[str] | None = None,
    expected_formula_cells: int | None = None,
) -> dict:
    ...

def validate_csv(
    path: Path,
    min_rows: int = 1,
) -> dict:
    ...
```

### 9.2 Result Contracts

XLSX validator result:

```python
{
    "valid": True,
    "format": "xlsx",
    "errors": [],
    "warnings": [],
    "sheet_count": 3,
    "sheet_names": ["Revenue", "Summary_Stats", "Pivot"],
    "formula_cell_count": 12,
}
```

CSV validator result:

```python
{
    "valid": True,
    "format": "csv",
    "errors": [],
    "warnings": [],
    "row_count": 150,
    "column_count": 8,
    "selected_tab": "Revenue",
}
```

### 9.3 Blocking Policy

- Invalid open/read → export failed
- Missing expected sheets in XLSX → failed
- Missing expected formula cells in XLSX (when specified) → failed
- Empty CSV (zero data rows) → failed
- Validator functions never throw on malformed input (return structured failure)

---

## 10. Orchestrator Changes

**File:** `core/studio/orchestrator.py`

The orchestrator already supports sheet draft generation. Phase 5 extends it with sheet normalization, export dispatch, and upload analysis.

### 10.1 Draft Path: Sheet Normalization

Update `approve_and_generate_draft()`:

- After `validate_content_tree()` for sheet artifacts:
  - Run `normalize_sheet_content_tree(content_tree_model)`
- Ensure normalized content is what gets persisted and revisioned

No changes to the revision model or storage schema are required.

### 10.2 Export Dispatch Matrix (`_VALID_COMBOS`)

Current behavior: slides (`pptx`) and documents (`docx`, `pdf`, `html`).

Phase 5 update:

```python
_VALID_COMBOS = {
    ArtifactType.slides: {ExportFormat.pptx},
    ArtifactType.document: {ExportFormat.docx, ExportFormat.pdf, ExportFormat.html},
    ArtifactType.sheet: {ExportFormat.xlsx, ExportFormat.csv},
}
```

### 10.3 Parameter Gating by Artifact Type

Sheet exports should reject slides/document-only options.

Policy:

- `theme_id`: rejected with `ValueError("theme_id is not supported for sheet exports")`
- `strict_layout`: rejected with `ValueError("strict_layout is not supported for sheet exports")`
- `generate_images`: rejected with `ValueError("generate_images is not supported for sheet exports")`

### 10.4 `_run_sheet_export()` Pseudocode

New async method following the existing `_run_export()` / `_run_document_export()` pattern:

```python
async def _run_sheet_export(
    self,
    artifact_id: str,
    export_job: Any,
    content_tree_dict: dict,
) -> None:
    from core.schemas.studio_schema import ExportFormat, ExportStatus, SheetContentTree
    from core.studio.sheets.exporter_xlsx import export_to_xlsx
    from core.studio.sheets.exporter_csv import export_to_csv
    from core.studio.sheets.validator import validate_xlsx, validate_csv

    try:
        content_tree_model = SheetContentTree(**content_tree_dict)
        output_path = self.storage.get_export_file_path(
            artifact_id, export_job.id, export_job.format.value
        )

        if export_job.format == ExportFormat.xlsx:
            export_to_xlsx(content_tree_model, output_path)
            validation = validate_xlsx(
                output_path,
                expected_sheet_names=[t.name for t in content_tree_model.tabs],
                expected_formula_cells=sum(len(t.formulas) for t in content_tree_model.tabs),
            )
        elif export_job.format == ExportFormat.csv:
            selected_tab = export_to_csv(content_tree_model, output_path)
            validation = validate_csv(output_path)
            validation["selected_tab"] = selected_tab
        else:
            raise ValueError(f"Unsupported sheet format: {export_job.format.value}")

        if validation["valid"]:
            export_job.status = ExportStatus.completed
            export_job.output_uri = str(output_path)
            export_job.file_size_bytes = output_path.stat().st_size
            export_job.validator_results = validation
            export_job.completed_at = datetime.now(timezone.utc)
        else:
            export_job.status = ExportStatus.failed
            export_job.error = "; ".join(validation.get("errors", [])) or "Validation failed"
            export_job.validator_results = validation
            export_job.completed_at = datetime.now(timezone.utc)

    except Exception as e:
        export_job.status = ExportStatus.failed
        export_job.error = str(e)
        export_job.completed_at = datetime.now(timezone.utc)

    self.storage.save_export_job(export_job)

    # Update the artifact's exports summary with the final status
    artifact = self.storage.load_artifact(artifact_id)
    if artifact is not None:
        for summary in artifact.exports:
            if summary.id == export_job.id:
                summary.status = export_job.status.value
                break
        artifact.updated_at = datetime.now(timezone.utc)
        self.storage.save_artifact(artifact)
```

### 10.5 `analyze_sheet_upload()` Method

New async method on `ForgeOrchestrator`:

```python
async def analyze_sheet_upload(
    self,
    artifact_id: str,
    filename: str,
    content_bytes: bytes,
    content_type: str,
) -> dict:
    """Ingest an uploaded file, analyze it, and update the sheet artifact."""
    ...
```

Responsibilities:

- Load artifact, verify it exists and is type `sheet` with a content tree
- Call `ingest_upload(filename, content_bytes, content_type)` → `TabularDataset`
- Call `analyze_dataset(dataset)` → `SheetAnalysisReport`
- Call `build_analysis_tabs(dataset, report)` → analysis tabs
- Update `content_tree.tabs` (append/replace analysis tabs)
- Set `content_tree.analysis_report = report`
- Create a new revision with summary: `"Added upload analysis from {filename}"`
- Return updated artifact dict

### 10.6 Export Job Lifecycle (Unchanged Pattern)

Retain the Phase 2-4 export job lifecycle exactly:

1. Validate artifact exists and has `content_tree`
2. Create pending `ExportJob`
3. Persist job + append summary to artifact
4. Run exporter (sheet exports are synchronous — no background task needed)
5. Run format validator
6. Mark completed or failed with `validator_results` / `error`
7. Persist job and refresh artifact export summary status

---

## 11. Router Changes

**File:** `routers/studio.py`

Phase 5 adds a new upload endpoint and extends the download media types.

### 11.1 New Endpoint: `analyze-upload`

```python
@router.post("/{artifact_id}/sheets/analyze-upload")
async def analyze_sheet_upload(artifact_id: str, file: UploadFile = File(...)):
    """Upload a file for analysis against an existing sheet artifact."""
    ...
```

Implementation:

- Validate `artifact_id` with `_validate_artifact_id()`
- Read file bytes: `content_bytes = await file.read()`
- Call `orchestrator.analyze_sheet_upload(artifact_id, file.filename, content_bytes, file.content_type)`

Error mapping:

- `ValueError` with "not found" → `HTTPException(404)`
- `ValueError` (validation/domain errors) → `HTTPException(400)`
- `Exception` → `HTTPException(500)`

Route ordering note:

- This endpoint uses a sub-path (`/{artifact_id}/sheets/analyze-upload`) which is more specific than `/{artifact_id}`, so it must be placed before the generic `/{artifact_id}` GET route. However, since it uses `POST` and a different path segment, FastAPI's method+path matching handles this correctly without reordering. Place it alongside the existing `POST /{artifact_id}/export` endpoint.

### 11.2 `_EXPORT_MEDIA_TYPES` Extension

Update the media type lookup in `download_export()`:

```python
_EXPORT_MEDIA_TYPES = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pdf": "application/pdf",
    "html": "text/html",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "csv": "text/csv",
}
```

---

## 12. Prompt Improvements

**File:** `core/studio/prompts.py`

Sheet outline and draft prompts already exist in the current codebase:

- **Outline guidance** (lines 121-128): tab/worksheet planning, column descriptions, formula planning
- **Draft schema** (lines 248-269): full `SheetContentTree` JSON schema with tab structure, formulas, column_widths

Phase 5 does not create new prompt blocks from scratch. Instead, it strengthens the existing sheet prompts with additional rules.

### 12.1 Draft Prompt Additions

Append to the existing sheet draft schema guidance:

```text
FORMULA REQUIREMENTS:
- Include formulas for totals, growth percentages, and derived metrics where appropriate
- Formulas must start with '=' and use valid A1-notation cell references
- Cell references must point to cells within the same tab's data range
- Do not reference cells beyond the last data row or column

FORMATTING CONVENTIONS:
- Use meaningful, descriptive headers (not generic "Column1", "Column2")
- Provide appropriate column_widths for each column (wider for text, narrower for numbers)
- Include an assumptions section when the data involves projections or estimates

DATA INTEGRITY:
- All rows must have the same number of columns as headers
- Each tab must have a unique id and name
- Do not use placeholder content (TBD, Lorem ipsum, N/A for all values)
- Include at least one raw-data tab and one computed summary tab when applicable
```

### 12.2 Outline Prompt Additions

Append to the existing sheet outline guidance:

```text
- When formulas are appropriate, describe them in the tab description
- Plan tabs with consistent column naming across related tabs
- Consider including a summary/totals tab for multi-tab workbooks
```

---

## 13. Frontend Hooks

Phase 5 requires minimal frontend changes to enable sheet export and upload analysis from the existing Studio UI.

### 13.1 `ExportPanel.tsx` - Sheet Format Picker

**File:** `platform-frontend/src/features/forge/components/ExportPanel.tsx`

Add a `SheetFormatPickerDialog` following the existing `DocFormatPickerDialog` pattern:

- Format choices: `XLSX`, `CSV`
- Hide all slides/document-only controls (theme picker, strict layout, generate images)
- Reuse existing export job polling, status display, and download link rendering

Update the `ExportButton` component to handle `artifactType === "sheet"`:

- Show `SheetFormatPickerDialog` when triggered
- Remove any sheet exclusion logic

### 13.2 `StudioWorkspace.tsx` - Export Button + Upload Data

**File:** `platform-frontend/src/features/studio/StudioWorkspace.tsx`

Current behavior (line 309): export button only shown for `['slides', 'document']`.

Phase 5 change:

- Include `'sheet'` in the condition: `['slides', 'document', 'sheet'].includes(artifact.type)`
- Add `Upload Data` action button in sheet viewer header:
  - File picker accepts `.csv,.xlsx,.json`
  - Calls `analyzeSheetUpload` store action
  - On success: refreshes active artifact
  - On failure: shows inline error message

### 13.3 `api.ts` - Upload Analysis Call

**File:** `platform-frontend/src/lib/api.ts`

Add:

```typescript
analyzeSheetUpload: async (artifactId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const { data } = await axios.post(
        `${API_BASE}/studio/${artifactId}/sheets/analyze-upload`,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
    );
    return data;
}
```

### 13.4 `store/index.ts` - Upload Analysis Action

**File:** `platform-frontend/src/store/index.ts`

Add `analyzeSheetUpload` action:

```typescript
analyzeSheetUpload: async (artifactId: string, file: File) => {
    const result = await api.analyzeSheetUpload(artifactId, file);
    set({ activeArtifact: result });
    // Refresh artifact list to show updated timestamp
    get().fetchArtifacts?.();
}
```

---

## 14. Dependencies

### 14.1 Python Dependencies

**File:** `pyproject.toml`

Add:

```toml
"openpyxl>=3.1.5",
"python-multipart>=0.0.9",
```

- `openpyxl` — XLSX read (ingestion) and write (export)
- `python-multipart` — Required by FastAPI for `UploadFile` / `File(...)` parameter parsing

Validation uses `openpyxl` for XLSX open-validation and Python stdlib `csv` for CSV open-validation.

### 14.2 No Frontend Dependency Changes Required

Phase 5 sheet export/upload UI reuses existing modal/dialog infrastructure and HTTP client code. No new frontend npm packages are expected.

---

## 15. Test Plan

Phase 5 test coverage follows the same pattern used in Phases 2-4: focused unit/component tests plus acceptance/integration extensions using the existing project gate files.

### `tests/test_studio_sheets_ingest.py` - 12 tests (NEW)

Covers upload ingestion and normalization:

- `test_ingest_csv_basic` — parse simple CSV with headers and rows
- `test_ingest_csv_delimiter_detection` — semicolon and tab-separated CSV handling
- `test_ingest_xlsx_basic` — parse XLSX first sheet with headers and rows
- `test_ingest_json_list_of_objects` — parse `[{"col": "val"}, ...]` format
- `test_ingest_json_rows_columns` — parse `{"columns": [...], "rows": [...]}` format
- `test_ingest_rejects_empty_dataset` — ValueError for file with no data rows
- `test_ingest_rejects_oversized_file` — ValueError for file exceeding 10 MB limit
- `test_ingest_rejects_too_many_rows` — ValueError for > 20,000 rows
- `test_ingest_rejects_too_many_columns` — ValueError for > 200 columns
- `test_ingest_rejects_unsupported_format` — ValueError for `.pdf`, `.txt` etc.
- `test_ingest_normalizes_column_types` — mixed types coerced consistently
- `test_ingest_handles_null_values` — None/empty cells preserved in TabularDataset

### `tests/test_studio_sheets_formulas.py` - 10 tests (NEW)

Covers formula syntax and reference validation:

- `test_formula_syntax_valid` — `=SUM(A1:A10)` passes
- `test_formula_syntax_missing_equals` — `SUM(A1:A10)` fails
- `test_formula_syntax_balanced_parens` — unbalanced parentheses fail
- `test_extract_cell_refs_single` — extracts `['A1']` from `=A1*2`
- `test_extract_cell_refs_range` — extracts `['A1', 'B10']` from `=SUM(A1:B10)`
- `test_validate_refs_in_bounds` — valid refs for 10-row, 5-column tab pass
- `test_validate_refs_out_of_bounds` — column Z or row 9999 fail
- `test_validate_tab_formulas_removes_invalid` — invalid formulas removed, warnings returned
- `test_validate_tab_formulas_preserves_valid` — valid formulas kept unchanged
- `test_validate_formula_key_out_of_bounds` — formula at cell address outside tab range flagged

### `tests/test_studio_sheets_analysis.py` - 14 tests (NEW)

Covers analysis components with fixture data:

- `test_summary_stats_numeric_columns` — mean/median/std/min/max computed correctly
- `test_summary_stats_null_handling` — null_count accurate for columns with None values
- `test_summary_stats_non_numeric_skipped` — string columns produce no summary
- `test_correlations_positive` — known positive correlation detected
- `test_correlations_negative` — known negative correlation detected
- `test_correlations_insufficient_data` — fewer than 5 observations skipped
- `test_trend_up` — increasing series classified as `"up"`
- `test_trend_down` — decreasing series classified as `"down"`
- `test_trend_flat` — constant series classified as `"flat"`
- `test_anomalies_detected` — z-score >= 3.0 flagged
- `test_anomalies_none_for_normal_data` — no anomalies in well-distributed data
- `test_pivot_preview_generated` — categorical + numeric pair produces pivot table
- `test_pivot_preview_none_when_no_categorical` — all-numeric dataset returns None
- `test_build_analysis_tabs_structure` — correct tab names and structure generated

### `tests/test_studio_sheets_generator.py` - 10 tests (NEW)

Covers sheet normalization rules:

- `test_normalize_unique_tab_ids` — duplicate ids get suffixed
- `test_normalize_unique_tab_names` — duplicate names get numbered suffix
- `test_normalize_row_width_padding` — short rows padded with None
- `test_normalize_row_width_truncation` — excess row values truncated
- `test_normalize_column_widths_padding` — missing widths padded with default
- `test_normalize_rejects_all_empty_tabs` — ValueError for empty workbook
- `test_normalize_sanitizes_placeholders` — `"TBD"` replaced with fallback
- `test_normalize_runs_formula_validation` — invalid formulas removed with warnings
- `test_normalize_idempotent` — running twice yields same result
- `test_normalize_preserves_valid_content` — valid tabs pass through unchanged

### `tests/test_studio_sheets_exporter_xlsx.py` - 10 tests (NEW)

Covers XLSX export:

- `test_xlsx_creates_file` — output file exists after export
- `test_xlsx_creates_parent_dirs` — parent directory created if missing
- `test_xlsx_opens_with_openpyxl` — file opens without exception
- `test_xlsx_sheet_count_matches_tabs` — worksheet count matches tab count
- `test_xlsx_sheet_names_match` — worksheet names match tab names
- `test_xlsx_header_row_present` — first row contains headers
- `test_xlsx_data_rows_present` — data rows written correctly
- `test_xlsx_formulas_written` — formula cells contain formula strings
- `test_xlsx_column_widths_applied` — column dimensions set from column_widths
- `test_xlsx_frozen_pane` — top row frozen at A2

### `tests/test_studio_sheets_exporter_csv.py` - 8 tests (NEW)

Covers CSV export:

- `test_csv_creates_file` — output file exists after export
- `test_csv_returns_tab_name` — selected tab name returned
- `test_csv_selects_first_nonempty_tab` — first tab with rows selected
- `test_csv_headers_first_row` — header row written first
- `test_csv_data_rows_present` — data rows match tab rows
- `test_csv_utf8_encoding` — non-ASCII characters preserved
- `test_csv_handles_empty_first_tab` — falls back to first tab with any content
- `test_csv_formulas_not_written` — formula cells exported as empty

### `tests/test_studio_sheets_validator.py` - 10 tests (NEW)

Covers validators:

- `test_validate_xlsx_success` — valid XLSX passes
- `test_validate_xlsx_corrupt_file` — invalid file returns `valid: False`
- `test_validate_xlsx_missing_sheets` — expected sheets missing returns failure
- `test_validate_xlsx_formula_count` — formula cell count matches expectation
- `test_validate_xlsx_result_contract` — result contains valid/errors/warnings/sheet_count/sheet_names
- `test_validate_csv_success` — valid CSV passes
- `test_validate_csv_empty_file` — empty file returns `valid: False`
- `test_validate_csv_min_rows` — fewer than min_rows returns failure
- `test_validate_csv_result_contract` — result contains valid/errors/warnings/row_count/column_count
- `test_validators_never_throw` — malformed input returns structured failure, no exception

### `tests/test_studio_orchestrator.py` - +10 tests (MODIFY)

Add/modify sheet pipeline tests:

- `test_sheet_export_xlsx_lifecycle` — sheet → xlsx export completes successfully
- `test_sheet_export_csv_lifecycle` — sheet → csv export completes successfully
- `test_sheet_export_invalid_format` — sheet → pptx fails cleanly
- `test_sheet_export_rejects_theme_id` — ValueError for theme_id on sheet export
- `test_sheet_export_rejects_strict_layout` — ValueError for strict_layout on sheet export
- `test_sheet_export_rejects_generate_images` — ValueError for generate_images on sheet export
- `test_sheet_export_stores_validator_results` — validator results persisted on job
- `test_sheet_normalization_runs_before_revision` — normalized content persisted
- `test_analyze_sheet_upload_creates_revision` — upload analysis creates new revision
- `test_analyze_sheet_upload_updates_content_tree` — analysis tabs and report added

### `tests/test_studio_export_router.py` - +8 tests (MODIFY)

Add/modify router tests:

- `test_xlsx_format_accepted` — `format="xlsx"` dispatches without error
- `test_csv_format_accepted` — `format="csv"` dispatches without error
- `test_upload_endpoint_success` — POST analyze-upload returns updated artifact
- `test_upload_endpoint_bad_file_type` — unsupported file returns 400
- `test_upload_endpoint_missing_artifact` — nonexistent artifact returns 404
- `test_upload_endpoint_empty_file` — empty file returns 400
- `test_download_xlsx_media_type` — correct XLSX media type in response
- `test_download_csv_media_type` — correct CSV media type in response

### `tests/test_studio_schema.py` - +4 tests (MODIFY)

- `test_export_format_xlsx` — `ExportFormat("xlsx")` accepted
- `test_export_format_csv` — `ExportFormat("csv")` accepted
- `test_sheet_analysis_report_serialization` — `SheetAnalysisReport` round-trip
- `test_sheet_content_tree_with_analysis_report` — `SheetContentTree` with optional `analysis_report` round-trip

### Acceptance Tests - `tests/acceptance/p04_forge/test_exports_open_and_render.py` - +5 tests (MODIFY)

Add tests (next numbering after Phase 4 ends at `test_25`):

- `test_26_xlsx_export_creates_valid_file` — sheet → XLSX export opens without corruption
- `test_27_csv_export_creates_valid_file` — sheet → CSV export opens without corruption
- `test_28_upload_analysis_generates_summary_tabs` — upload CSV/XLSX generates analysis tabs and report
- `test_29_sheet_formula_refs_are_valid` — formulas in generated sheet reference valid cells
- `test_30_sheet_export_job_lifecycle_completed` — sheet export job transitions to completed with validator results

### Integration Tests - `tests/integration/test_forge_research_to_slides.py` - +4 tests (MODIFY)

Despite the filename, extend with sheet scenarios (next numbering after Phase 4 ends at `test_21`):

- `test_22_sheet_outline_to_draft_to_xlsx_export` — full pipeline: outline → draft → XLSX export
- `test_23_sheet_upload_analysis_to_export_pipeline` — upload → analysis → xlsx export
- `test_24_sheet_invalid_upload_graceful_failure` — invalid upload returns controlled error, artifact unchanged
- `test_25_sheet_export_param_gating_enforced` — slides-only params rejected for sheet exports

### Test Count Summary (Planned)

- New test files: 7
- Modified test files: 5
- New tests added: ~105

### Gate Commands

```bash
# Phase 5 new sheet unit/component tests
PYTHONPATH=. uv run python -m pytest \
  tests/test_studio_sheets_ingest.py \
  tests/test_studio_sheets_formulas.py \
  tests/test_studio_sheets_analysis.py \
  tests/test_studio_sheets_generator.py \
  tests/test_studio_sheets_exporter_xlsx.py \
  tests/test_studio_sheets_exporter_csv.py \
  tests/test_studio_sheets_validator.py

# Modified core/router/schema tests
PYTHONPATH=. uv run python -m pytest \
  tests/test_studio_orchestrator.py \
  tests/test_studio_export_router.py \
  tests/test_studio_schema.py

# Acceptance + integration project gates
PYTHONPATH=. uv run python -m pytest \
  tests/acceptance/p04_forge/test_exports_open_and_render.py \
  tests/integration/test_forge_research_to_slides.py

# Baseline non-regression
scripts/test_all.sh quick
```

---

## 16. Day-by-Day Execution (Days 14-15)

### Day 14: Schema + Ingest + Analysis + Normalization + Unit Tests

Primary goal: sheet data pipeline working with deterministic analysis outputs and formula validation.

Tasks:

1. Add `ExportFormat.xlsx/csv` and `SheetAnalysisReport` models in `core/schemas/studio_schema.py`
2. Add `analysis_report` field to `SheetContentTree`
3. Add `openpyxl>=3.1.5` and `python-multipart>=0.0.9` to `pyproject.toml`
4. Implement `core/studio/sheets/types.py` (TabularDataset, constants)
5. Implement `core/studio/sheets/ingest.py` (CSV/XLSX/JSON ingestion + guardrails)
6. Implement `core/studio/sheets/formulas.py` (syntax/ref validation)
7. Implement `core/studio/sheets/analysis.py` (summary stats, correlations, trends, anomalies, pivot)
8. Implement `core/studio/sheets/generator.py` (normalize_sheet_content_tree)
9. Wire sheet normalization into `approve_and_generate_draft()` (orchestrator)
10. Strengthen sheet prompts in `core/studio/prompts.py`
11. Add/green:
    - `tests/test_studio_sheets_ingest.py`
    - `tests/test_studio_sheets_formulas.py`
    - `tests/test_studio_sheets_analysis.py`
    - `tests/test_studio_sheets_generator.py`

Checkpoint:

- Sheet content trees are normalized deterministically with formula validation
- Upload ingestion handles CSV/XLSX/JSON with guardrails
- Analysis produces deterministic reports from fixture data
- All Day 14 unit tests pass

### Day 15: Exporters + Validators + Router + Frontend + Acceptance/Integration

Primary goal: complete sheet export pipeline, upload-analysis endpoint, frontend hooks, and passing Phase 5 gates.

Tasks:

1. Implement `core/studio/sheets/exporter_xlsx.py` (XLSX export via openpyxl)
2. Implement `core/studio/sheets/exporter_csv.py` (CSV primary-tab export)
3. Implement `core/studio/sheets/validator.py` (validate_xlsx, validate_csv)
4. Wire sheet export dispatch in orchestrator (`_run_sheet_export()`, `_VALID_COMBOS`, param gating)
5. Implement `analyze_sheet_upload()` method in orchestrator
6. Add upload-analysis endpoint in `routers/studio.py`
7. Extend `_EXPORT_MEDIA_TYPES` with xlsx/csv
8. Update frontend:
   - `ExportPanel.tsx` — SheetFormatPickerDialog
   - `StudioWorkspace.tsx` — enable sheet export + upload action
   - `api.ts` — analyzeSheetUpload
   - `store/index.ts` — analyzeSheetUpload action
9. Add/green:
   - `tests/test_studio_sheets_exporter_xlsx.py`
   - `tests/test_studio_sheets_exporter_csv.py`
   - `tests/test_studio_sheets_validator.py`
   - Sheet cases in `tests/test_studio_orchestrator.py`
   - Sheet cases in `tests/test_studio_export_router.py`
   - Sheet cases in `tests/test_studio_schema.py`
10. Add acceptance tests `test_26`-`test_30`
11. Extend integration test file with sheet scenarios `test_22`-`test_25`
12. Run acceptance/integration + baseline regression
13. Perform manual smoke check:
    - create sheet outline
    - approve sheet draft
    - export XLSX and CSV
    - upload CSV file and verify analysis tabs
    - download artifacts via Studio routes/UI

Checkpoint (Phase 5 complete):

- Prompt-to-sheet works end-to-end with XLSX/CSV export
- Upload analysis produces deterministic tabs and reports
- Acceptance tests confirm both export formats open without corruption
- `scripts/test_all.sh quick` remains green

---

## 17. Exit Criteria

Phase 5 is complete when all of the following are true:

1. Sheet artifacts export successfully to XLSX and CSV.
2. XLSX opens with `openpyxl` and includes expected tabs, headers, and formulas.
3. CSV opens and contains primary tab data with correct headers and rows.
4. Uploading CSV/XLSX/JSON generates analysis outputs (summary stats, correlations, trends, anomalies, pivot) and a new revision.
5. Formula validation catches invalid syntax and out-of-bounds references deterministically.
6. Sheet normalization ensures consistent tab structure (unique ids/names, aligned rows/widths).
7. `POST /studio/{artifact_id}/sheets/analyze-upload` returns updated artifact with analysis report.
8. Sheet export rejects slides-only parameters (`theme_id`, `strict_layout`, `generate_images`).
9. Acceptance and integration test suites pass with new sheet scenarios.
10. `scripts/test_all.sh quick` remains green with no regression to slides or document exports.

---

## 18. Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Large/dirty uploads causing unstable performance | Medium | Strict size/row/column limits + deterministic truncation warnings |
| Formula reference validation false positives | Low | Explicit A1 parser tests and bounded range checks; conservative removal with warnings |
| Excel parsing variability across user files | Medium | Normalize types, skip unsupported cell types with warnings; test with diverse fixtures |
| Frontend complexity creep | Low | Keep UI hooks minimal; reuse existing export flow; sheet picker follows doc picker pattern |
| `openpyxl` version compatibility issues | Low | Pin minimum version; test XLSX round-trip in CI |
| CSV delimiter detection unreliable | Low | Use `csv.Sniffer` with fallback to comma; test with semicolon and tab fixtures |
| `python-multipart` already present via FastAPI transitive dep | Low | Verify presence in lockfile; add explicit dep to ensure availability |

---

## 19. Deferred Items (Explicitly Not in Phase 5)

- Google Sheets export/API integration
- Multi-tab CSV bundling (zip package)
- Advanced anomaly modeling beyond z-score baseline
- Sheet-specific visual chart builder UI
- Collaborative sheet editing (Phase 6+)
- Rich spreadsheet formula bar / cell editor UI
- XLSX style templates / branded workbooks
- Multi-file merge workflows
- Forecasting or ML-driven analysis

---

## 20. Phase 6+ Extension Hooks

Phase 5 should leave clear extension points for Edit Loop (Phase 6) and future enhancements.

### 20.1 Edit Loop for Sheets

The `SheetContentTree` revision model supports iterative refinement. Phase 6 can add:

- LLM-assisted cell editing / formula generation
- User-requested tab additions/modifications via chat
- Re-analysis after manual edits

### 20.2 XLSX Read-Back for Edit Loop

The `openpyxl` dependency enables reading back exported XLSX files for:

- Round-trip editing: export → user edits in Excel → re-import → diff
- Formula evaluation comparison between openpyxl data_only and formula mode

### 20.3 Multi-Tab CSV Export

Phase 5 CSV exports only the primary tab. Future phases can:

- Bundle multiple tabs as separate CSV files in a zip archive
- Allow tab selection in the export dialog

### 20.4 Sheet Export UI Enhancements

Phase 5 provides a minimal format picker. Future phases can add:

- Tab selection for CSV export
- XLSX style template selection
- Preview of analysis report before export

### 20.5 Analysis Report Persistence

Phase 5 stores analysis reports in the content tree. Future phases can:

- Store reports as separate artifacts for historical comparison
- Track analysis report diffs across revisions

### 20.6 Prompt-Driven Analysis

Phase 5 analysis is deterministic and statistical. Future phases can:

- Use LLM to generate natural-language insights from analysis reports
- Allow user to ask questions about uploaded data via chat

---

## Appendix A: Key Existing Files Referenced

| File | Role |
|------|------|
| `core/schemas/studio_schema.py` | Canonical Pydantic schemas (ExportFormat, SheetContentTree, SheetTab) |
| `core/studio/orchestrator.py` | Outline-first pipeline, export dispatch, _VALID_COMBOS |
| `core/studio/prompts.py` | LLM prompt templates (sheet prompts at lines 121-128, 248-269) |
| `core/studio/storage.py` | File-based artifact/revision/export persistence |
| `core/studio/documents/generator.py` | Reference for content tree normalization pattern |
| `core/studio/documents/validator.py` | Reference for export validator pattern |
| `routers/studio.py` | Studio API routes, _EXPORT_MEDIA_TYPES, error mapping |
| `platform-frontend/src/features/studio/StudioWorkspace.tsx` | Studio workspace with artifact viewers + export button |
| `platform-frontend/src/features/forge/components/ExportPanel.tsx` | Export panel with format picker dialogs |
| `platform-frontend/src/store/index.ts` | Zustand store with startExport action |
| `platform-frontend/src/lib/api.ts` | API client (axios) |
| `tests/test_studio_orchestrator.py` | Orchestrator test suite |
| `tests/test_studio_export_router.py` | Router test suite |
| `tests/test_studio_schema.py` | Schema test suite |
| `tests/acceptance/p04_forge/test_exports_open_and_render.py` | Forge acceptance tests (ends at test_25) |
| `tests/integration/test_forge_research_to_slides.py` | Forge integration tests (ends at test_21) |

## Appendix B: Example SheetContentTree with `analysis_report`

```json
{
  "workbook_title": "Q4 Revenue Analysis",
  "tabs": [
    {
      "id": "tab1",
      "name": "Revenue",
      "headers": ["Month", "Product", "Revenue", "Units"],
      "rows": [
        ["Oct", "Widget A", 45000, 150],
        ["Oct", "Widget B", 32000, 80],
        ["Nov", "Widget A", 48000, 160],
        ["Nov", "Widget B", 35000, 90],
        ["Dec", "Widget A", 52000, 175],
        ["Dec", "Widget B", 38000, 95]
      ],
      "formulas": {
        "E2": "=C2/D2",
        "E3": "=C3/D3"
      },
      "column_widths": [80, 120, 100, 80]
    },
    {
      "id": "uploaded_data",
      "name": "Uploaded_Data",
      "headers": ["Month", "Product", "Revenue", "Units"],
      "rows": [
        ["Oct", "Widget A", 45000, 150],
        ["Nov", "Widget A", 48000, 160],
        ["Dec", "Widget A", 52000, 175]
      ],
      "formulas": {},
      "column_widths": [80, 120, 100, 80]
    },
    {
      "id": "summary_stats",
      "name": "Summary_Stats",
      "headers": ["Column", "Count", "Null Count", "Mean", "Median", "Std", "Min", "Max"],
      "rows": [
        ["Revenue", 3, 0, 48333.33, 48000, 3511.88, 45000, 52000],
        ["Units", 3, 0, 161.67, 160, 12.58, 150, 175]
      ],
      "formulas": {},
      "column_widths": [100, 60, 80, 80, 80, 80, 80, 80]
    }
  ],
  "assumptions": "Revenue figures are gross revenue before returns.",
  "metadata": {
    "currency": "USD",
    "period": "Q4 2025"
  },
  "analysis_report": {
    "summary_stats": [
      {
        "column": "Revenue",
        "count": 3,
        "null_count": 0,
        "mean": 48333.33,
        "median": 48000.0,
        "std": 3511.88,
        "min_val": 45000.0,
        "max_val": 52000.0
      },
      {
        "column": "Units",
        "count": 3,
        "null_count": 0,
        "mean": 161.67,
        "median": 160.0,
        "std": 12.58,
        "min_val": 150.0,
        "max_val": 175.0
      }
    ],
    "correlations": [
      {
        "column_a": "Revenue",
        "column_b": "Units",
        "pearson_r": 0.9998
      }
    ],
    "trends": [
      {"column": "Revenue", "direction": "up", "slope": 3500.0},
      {"column": "Units", "direction": "up", "slope": 12.5}
    ],
    "anomalies": [],
    "pivot_preview": {
      "index_column": "Month",
      "value_column": "Revenue",
      "table": {
        "Oct": 45000,
        "Nov": 48000,
        "Dec": 52000
      }
    },
    "warnings": []
  }
}
```

## Appendix C: Example XLSX Validator Result

```json
{
  "valid": true,
  "format": "xlsx",
  "errors": [],
  "warnings": [],
  "sheet_count": 3,
  "sheet_names": ["Revenue", "Summary_Stats", "Pivot"],
  "formula_cell_count": 12
}
```

## Appendix D: Example CSV Validator Result

```json
{
  "valid": true,
  "format": "csv",
  "errors": [],
  "warnings": [],
  "row_count": 150,
  "column_count": 8,
  "selected_tab": "Revenue"
}
```

## Appendix E: Example `SheetAnalysisReport` JSON

```json
{
  "summary_stats": [
    {
      "column": "Revenue",
      "count": 100,
      "null_count": 2,
      "mean": 52340.5,
      "median": 51000.0,
      "std": 8920.3,
      "min_val": 12000.0,
      "max_val": 98000.0
    }
  ],
  "correlations": [
    {
      "column_a": "Revenue",
      "column_b": "Units_Sold",
      "pearson_r": 0.87
    }
  ],
  "trends": [
    {
      "column": "Revenue",
      "direction": "up",
      "slope": 1250.5
    },
    {
      "column": "Units_Sold",
      "direction": "flat",
      "slope": 0.3
    }
  ],
  "anomalies": [
    {
      "column": "Revenue",
      "row_index": 47,
      "value": 98000.0,
      "z_score": 5.12
    },
    {
      "column": "Revenue",
      "row_index": 3,
      "value": 12000.0,
      "z_score": -4.52
    }
  ],
  "pivot_preview": {
    "index_column": "Region",
    "value_column": "Revenue",
    "table": {
      "North": 245000,
      "South": 198000,
      "East": 312000,
      "West": 278000
    }
  },
  "warnings": [
    "Removed invalid formula at C15: reference out of bounds",
    "Column 'Notes' skipped: non-numeric type"
  ]
}
```
