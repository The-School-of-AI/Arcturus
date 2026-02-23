# P05 Delivery README

## 1. Scope Delivered

### Week 1 (Days 1-5): Event Log Schema + Deterministic Checkpoint Flow ✅
- **session/schema.py**: Event log schema with `EventType` enum, `EventLogEntry`, `CheckpointSnapshot`. Canonical JSON serialization for content-addressable hashing.
- **session/capture.py**: Async event capture engine (queue + background writer) for low-overhead streaming to NDJSON event logs.
- **session/checkpoint.py**: Deterministic checkpoint snapshot flow: serialize graph → load events → compute hash → persist. `create_checkpoint`, `list_checkpoints`, `load_checkpoint`.

### Pending (Weeks 2-3)
- Event wiring into core loop and agent (emit from loop.py, base_agent)
- Git-integrated checkpoints (branch arcturus/sessions/v1)
- Rewind/resume CLI
- Session Explorer UI enhancements
- Auto-summarization

## 2. Architecture Changes

- New package: `session/` at repo root
  - `schema.py`: Pydantic models for events and checkpoints
  - `capture.py`: SessionCapture class, get_capture() singleton
  - `checkpoint.py`: create_checkpoint, list_checkpoints, load_checkpoint
- Storage paths:
  - Event logs: `memory/chronicle_events/events_{session_id}.ndjson`
  - Checkpoints: `memory/chronicle_checkpoints/{session_id}/checkpoint_{hash}.json`

## 3. API And UI Changes

- No API or UI changes in Week 1. Session module is backend-only.
- `get_capture()` returns global SessionCapture; `emit()`, `emit_sync()` for events.

## 4. Mandatory Test Gate Definition
- Acceptance file: tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py
- Additional for Week 1: tests/acceptance/p05_chronicle/test_event_schema_and_checkpoint_flow.py
- Integration file: tests/integration/test_chronicle_git_checkpoint_alignment.py
- CI check: p05-chronicle-replay

## 5. Test Evidence

### Week 1 Tests (in test_rewind_restores_exact_state.py)
| Test | Description |
|------|-------------|
| test_09_event_log_entry_canonical_json_determinism | Same entry → identical canonical JSON |
| test_10_event_log_entry_content_hash_determinism | Same entry → identical 16-char content hash |
| test_11_create_checkpoint_deterministic_hash | Same inputs → same checkpoint content hash |
| test_12_create_checkpoint_persists_and_loads | Checkpoint written to disk; load_checkpoint retrieves it |

Run: `pytest tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py -v`

## 6. Existing Baseline Regression Status
- Command: scripts/test_all.sh quick
- TODO (run after env setup)

## 7. Security And Safety Impact
- Event logs and checkpoints store session data (prompts, outputs, graph state). Stored under `memory/` in repo. Consider .gitignore for `memory/chronicle_*` if sensitive.

## 8. Known Gaps
- Event bus subscription not yet wired (capture emits manually; loop/agent integration in Week 2)
- No git branch integration for checkpoints
- Rewind/resume CLI not implemented

## 9. Rollback Plan
- Remove `session/` package
- Remove `memory/chronicle_events/`, `memory/chronicle_checkpoints/`
- No other code depends on session module in Week 1

## 10. Demo Steps
- Script: scripts/demos/p05_chronicle.sh
- Week 1 demo (manual):
  ```python
  from session.schema import EventLogEntry, EventType
  from session.checkpoint import create_checkpoint, load_checkpoint
  import networkx as nx
  g = nx.DiGraph()
  g.add_node("A", agent="CoderAgent", status="completed")
  snap = create_checkpoint("demo", "manual", g)
  print(snap.checkpoint_id, snap.content_hash)
  loaded = load_checkpoint("demo", snap.checkpoint_id)
  assert loaded is not None
  ```
