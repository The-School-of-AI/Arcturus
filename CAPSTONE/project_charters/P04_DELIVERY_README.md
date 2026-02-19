# P04 Delivery README — Forge Phase 1: Artifact Schemas + Outline-First Pipeline

## 1. Scope Delivered

**Phase 1 (Days 1-5) of the Forge AI Creation Suite** — the foundational layer that all subsequent phases build upon.

### Completed
- **Canonical Pydantic schemas** for all three artifact types: Slides, Documents, and Sheets
- **Outline-first generation pipeline**: Prompt → outline JSON → user approval → draft content_tree
- **Revision model** with computed change summaries and linked-list history
- **File-based storage layer** with full CRUD under `studio/` runtime directory
- **8 REST API endpoints** (`/api/studio/*`) for the complete creation flow
- **Skill stub** (`forge_outline`) for intent matching and auto-discovery
- **Frontend integration**: Forge sidebar tab, creation modal, outline/content viewers, and full-width dashboard
- **53+ backend tests** (schema, storage, revision, orchestrator, router) — all passing
- **Manual E2E test script** (`scripts/manual_test_forge.py`) for live pipeline validation

### Deferred (Phase 2+)
- High-quality generation logic, themes, charting, image generation (Phase 2-5)
- Export engines: python-pptx, python-docx, openpyxl, WeasyPrint (Phase 2-5)
- Chat-driven edit loop and patch engine (Phase 6)
- WYSIWYG editor components (frontend track)
- Advanced collaboration, locking, conflict resolution (Phase 6)

## 2. Architecture Changes

### New Modules

```
core/schemas/studio_schema.py      — Pydantic models: Artifact, Revision, Outline, ContentTrees
core/studio/__init__.py            — Package init
core/studio/orchestrator.py        — ForgeOrchestrator: outline-first pipeline (LLM → parse → validate)
core/studio/storage.py             — StudioStorage: file-based persistence under studio/
core/studio/revision.py            — RevisionManager + compute_change_summary() diff utility
core/studio/prompts.py             — LLM prompt templates for outline and draft generation
core/skills/library/forge_outline/ — Skill stub for auto-discovery by SkillManager
routers/studio.py                  — FastAPI router with 8 endpoints
```

### Data Flow

```
User Prompt
  → POST /api/studio/{type}
    → ForgeOrchestrator.generate_outline()
      → get_outline_prompt() → ModelManager.generate_text()
      → parse_llm_json() → Outline Pydantic validation
      → StudioStorage.save_artifact() (status: pending)
    ← Returns {artifact_id, outline}

User Approval
  → POST /api/studio/{id}/outline/approve
    → ForgeOrchestrator.approve_and_generate_draft()
      → get_draft_prompt() → ModelManager.generate_text()
      → parse_llm_json() → validate_content_tree() (type-specific Pydantic)
      → RevisionManager.create_revision() (with computed change summary)
      → StudioStorage.save_artifact() (content_tree populated)
    ← Returns full Artifact with content_tree
```

### Backward Compatibility
- No existing modules modified beyond minimal wiring:
  - `api.py`: +2 lines (import + include_router)
  - `shared/state.py`: +11 lines (get_studio_storage singleton)
- All existing tests continue to pass unchanged

## 3. API And UI Changes

### Backend Endpoints (all under `/api/studio`)

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/studio/slides` | Create slides artifact; returns outline for approval |
| `POST` | `/studio/documents` | Create document artifact; returns outline |
| `POST` | `/studio/sheets` | Create sheet artifact; returns outline |
| `POST` | `/studio/{artifact_id}/outline/approve` | Approve outline → generates draft content_tree |
| `GET` | `/studio/{artifact_id}` | Retrieve full artifact |
| `GET` | `/studio` | List all artifacts (sorted by updated_at desc) |
| `GET` | `/studio/{artifact_id}/revisions` | List revisions for artifact |
| `GET` | `/studio/{artifact_id}/revisions/{revision_id}` | Get specific revision |

### Request Models

```
CreateArtifactRequest { prompt: str, title?: str, parameters?: dict, model?: str }
ApproveOutlineRequest { approved: bool, modifications?: dict }
```

### Frontend Components

| Component | Location | Description |
|-----------|----------|-------------|
| Sidebar tab | `Sidebar.tsx` | "Forge" tab with Wand2 icon |
| `StudioSidebar.tsx` | `features/studio/` | Artifact list in sidebar sub-panel |
| `StudioCreationModal.tsx` | `features/studio/` | Type picker + prompt input via createPortal |
| `StudioWorkspace.tsx` | `features/studio/` | Outline review, content tree viewers |
| `ForgeDashboard.tsx` | `features/forge/` | Full-width main canvas with split-pane layout |
| `StudioSlice` | `store/index.ts` | Zustand state for artifact management |
| API methods | `lib/api.ts` | listArtifacts, getArtifact, createArtifact, approveOutline, listRevisions, getRevision |

## 4. Mandatory Test Gate Definition

- **Acceptance file**: `tests/acceptance/p04_forge/test_exports_open_and_render.py` (Phase 2+ — export not in Phase 1 scope)
- **Integration file**: `tests/integration/test_forge_research_to_slides.py` (Phase 2+ — research integration not in Phase 1 scope)
- **CI check**: `p04-forge-studio`

### Phase 1 Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `tests/test_studio_schema.py` | 20+ | Schema validation, content trees, round-trip serialization |
| `tests/test_studio_storage.py` | 10+ | File-based CRUD, directory creation, sort ordering |
| `tests/test_studio_revision.py` | 10+ | Revision chains, change summary computation |
| `tests/test_studio_orchestrator.py` | 8+ | Full pipeline with mocked LLM, error cases |
| `tests/test_studio_router.py` | 5+ | Router wiring and endpoint validation |

**Pass criteria**: All 53+ tests pass with 0 failures.

## 5. Test Evidence

### Backend Tests
```
$ uv run python -m pytest tests/ -q
306 passed, 2 skipped in 38.70s
```
- 2 skips are expected: `RUN_BUILD_TESTS` and `RUN_EXTERNAL_TESTS` gated tests
- All 53+ studio-specific tests included in the 306 passed

### Frontend Tests
```
$ cd platform-frontend && npx vitest run
 ✓ src/__tests__/prompt.test.ts (4 tests)
 ✓ src/__tests__/parsing.test.ts (9 tests)
 ✓ src/__tests__/security.test.ts (44 tests)
 ✓ src/__tests__/tool_reliability.test.ts (11 tests)
 ✓ src/__tests__/agent_tool_tests.test.ts (43 tests)

Test Files  5 passed (5)
     Tests  111 passed (111)
```

## 6. Existing Baseline Regression Status

- **Command**: `scripts/test_all.sh quick` (run via uv + npx individually)
- **Result**: **306 backend passed + 111 frontend passed = 417 total, 0 failures**
- No regressions introduced. All pre-existing tests pass unchanged.

## 7. Security And Safety Impact

- **No new attack surfaces**: All endpoints are local-only (CORS restricted to `localhost:5173` and Electron `app://`)
- **No secrets handling**: Forge uses existing `ModelManager` which reads API keys from `.env` (already untracked)
- **File-based storage**: `studio/` runtime directory is gitignored; no database credentials needed
- **Input validation**: All inputs validated through Pydantic models; LLM outputs validated before persistence
- **No code execution**: Phase 1 does not execute any user-provided or LLM-generated code

## 8. Known Gaps

- **No export engines yet**: PPTX/DOCX/XLSX export deferred to Phase 2+ (python-pptx, python-docx, openpyxl not added)
- **LLM quality**: Draft content quality depends on model capability; prompt engineering will be refined in Phase 2+
- **No edit loop**: Users cannot iteratively refine artifacts via chat yet (Phase 6)
- **No themes**: Visual theming system deferred to Phase 2
- **Frontend viewers are read-only**: Content tree is displayed but not editable in the UI

## 9. Rollback Plan

- **Safe rollback**: Revert this branch's commits. Only 2 existing files modified minimally (`api.py` +2 lines, `shared/state.py` +11 lines)
- **Data rollback**: Delete `studio/` runtime directory (gitignored, no persistent data concerns)
- **No feature flags needed**: Forge endpoints are additive; removing the router registration disables all functionality
- **No database migrations**: File-based storage only

## 10. Demo Steps

### Automated Test (no API key needed)
```bash
uv run python -m pytest tests/test_studio_orchestrator.py -v
```

### Manual E2E Test (requires GEMINI_API_KEY)
```bash
# Start the backend
uv run api.py

# In another terminal — run the manual test script
uv run python scripts/manual_test_forge.py
```

### Manual curl Test
```bash
# Start server
uv run api.py

# 1. Create a slides outline
curl -s -X POST http://localhost:8000/api/studio/slides \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Create a 5-slide pitch deck for an AI startup"}' | python -m json.tool

# 2. Approve the outline (replace ARTIFACT_ID from step 1)
curl -s -X POST http://localhost:8000/api/studio/ARTIFACT_ID/outline/approve \
  -H "Content-Type: application/json" \
  -d '{"approved": true}' | python -m json.tool

# 3. Retrieve the artifact with content_tree
curl -s http://localhost:8000/api/studio/ARTIFACT_ID | python -m json.tool

# 4. List all artifacts
curl -s http://localhost:8000/api/studio | python -m json.tool

# 5. List revisions
curl -s http://localhost:8000/api/studio/ARTIFACT_ID/revisions | python -m json.tool
```

### Frontend Demo
```bash
cd platform-frontend && npm run electron:dev:all
# Click the "Forge" tab (Wand2 icon) in the sidebar
# Use the "+" button to create a new artifact
# Select type, enter prompt, review outline, approve to generate draft
```
