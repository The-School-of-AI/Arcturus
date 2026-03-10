# P05 Delivery README

## 1. Scope Delivered

### Week 1 (Days 1-5): Event Log Schema + Deterministic Checkpoint Flow ✅
- **session/schema.py**: Event log schema with `EventType` enum, `EventLogEntry`, `CheckpointSnapshot`. Canonical JSON serialization for content-addressable hashing.
- **session/capture.py**: Async event capture engine (queue + background writer) for low-overhead streaming to NDJSON event logs.
- **session/checkpoint.py**: Deterministic checkpoint snapshot flow: serialize graph → load events → compute hash → persist. `create_checkpoint`, `list_checkpoints`, `load_checkpoint`.

### Week 2 (Days 6-10): Rewind Engine + State Restoration Invariants ✅
- **session/rewind.py**: Rewind engine. `restore_from_checkpoint` rebuilds `ExecutionContextManager` from `CheckpointSnapshot`, resets running nodes to pending, verifies 5 state restoration invariants. `rewind_to_latest` selects most recent checkpoint. `list_available_checkpoints` lists sessions.
- **core/loop.py**: Chronicle event emission wired in — `STEP_START` on `_execute_step` entry, `STEP_COMPLETE` and `STEP_FAILED` after result processing. Checkpoint automatically created after each `STEP_COMPLETE` and `STEP_FAILED`.

### Pending (Week 3)
- Git-integrated checkpoints (branch arcturus/sessions/v1)
- Rewind/resume CLI
- Session Explorer UI enhancements
- Auto-summarization

## 2. Architecture Changes

- New package: `session/` at repo root
  - `schema.py`: Pydantic models for events and checkpoints
  - `capture.py`: SessionCapture class, get_capture() singleton
  - `checkpoint.py`: create_checkpoint, list_checkpoints, load_checkpoint
  - `rewind.py`: RewindError, RewindResult, restore_from_checkpoint, rewind_to_latest, list_available_checkpoints, verify_restoration_invariants
- `core/loop.py`: Chronicle hooks added to `_execute_step` and result processing (STEP_START, STEP_COMPLETE, STEP_FAILED events + checkpoint creation)
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

### Week 2 Tests (in test_rewind_restores_exact_state.py)
| Test | Description |
|------|-------------|
| test_13_restore_from_checkpoint_returns_correct_node_count | Restored context has correct node count |
| test_14_restore_resets_running_nodes_to_pending | Running nodes reset to pending after restore |
| test_15_verify_restoration_invariants_no_running_nodes | Invariant check catches running nodes |
| test_16_list_available_checkpoints_returns_nonempty_after_create | list_available_checkpoints works after checkpoint created |

### Week 2 Integration Tests (in test_chronicle_git_checkpoint_alignment.py)
| Test | Description |
|------|-------------|
| test_06_rewind_module_importable | session.rewind imports cleanly |
| test_07_checkpoint_and_rewind_roundtrip | Create checkpoint → rewind → node count matches |
| test_08_rewind_to_latest_selects_newest_checkpoint | rewind_to_latest picks newest by created_at |
| test_09_restoration_invariants_pass_for_clean_graph | Clean graph passes all invariants |
| test_10_restoration_invariants_detect_missing_end_time | Invariants flag completed nodes missing end_time |

Run: `pytest tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py tests/integration/test_chronicle_git_checkpoint_alignment.py -v`

## 6. Existing Baseline Regression Status
- Command: scripts/test_all.sh quick
- TODO (run after env setup)

## 7. Security And Safety Impact
- Event logs and checkpoints store session data (prompts, outputs, graph state). Stored under `memory/` in repo. Consider .gitignore for `memory/chronicle_*` if sensitive.

## 8. Known Gaps
- Git branch integration for checkpoints (arcturus/sessions/v1) not yet implemented (Week 3)
- Rewind/resume CLI not implemented (Week 3)
- Session Explorer UI enhancements pending (Week 3)
- Auto-summarization pending (Week 3)

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
