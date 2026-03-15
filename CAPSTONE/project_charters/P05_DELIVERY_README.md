# P05 Delivery README

## 1. Scope Delivered

### Week 1 (Days 1-5): Event Log Schema + Deterministic Checkpoint Flow ✅
- **session/schema.py**: Event log schema with `EventType` enum, `EventLogEntry`, `CheckpointSnapshot`. Canonical JSON serialization for content-addressable hashing.
- **session/capture.py**: Async event capture engine (queue + background writer) for low-overhead streaming to NDJSON event logs.
- **session/checkpoint.py**: Deterministic checkpoint snapshot flow: serialize graph → load events → compute hash → persist. `create_checkpoint`, `list_checkpoints`, `load_checkpoint`.

### Week 2 (Days 6-10): Rewind Engine + State Restoration Invariants ✅
- **session/rewind.py**: Rewind engine. `restore_from_checkpoint` rebuilds `ExecutionContextManager` from `CheckpointSnapshot`, resets running nodes to pending, verifies 5 state restoration invariants. `rewind_to_latest` selects most recent checkpoint. `list_available_checkpoints` lists sessions.
- **core/loop.py**: Chronicle event emission wired in — `STEP_START` on `_execute_step` entry, `STEP_COMPLETE` and `STEP_FAILED` after result processing. Checkpoint automatically created after each `STEP_COMPLETE` and `STEP_FAILED`.

### Scope: Git/Checkpoint Alignment + Cross-Module Trace Linking ✅
- **session/alignment.py**: `get_git_head_info(repo_path)` — captures HEAD commit sha and branch; `get_current_trace_ids()` — captures OpenTelemetry trace_id/span_id from active span.
- **CheckpointSnapshot**: Extended with `git_commit_sha`, `git_branch`, `trace_id`, `span_id` for alignment and cross-module linking.
- **create_checkpoint**: Integrates alignment; checkpoints now include git state and trace IDs when available.
- **Cross-module trace linking**: Chronicle checkpoints link to Watchtower (P14) spans via trace_id/span_id for end-to-end observability.

### Phase 7 (Days 16-20): Hardening, Docs, Replay Reliability Demo ✅
- **Concurrent edit hardening**: SessionCapture uses per-session sequence (`_session_sequences`), asyncio lock for sequence, per-session file locks for NDJSON appends. Checkpoint creation uses per-session `threading.Lock` for safe concurrent writes.
- **Docs**: `session/README.md` — overview, API, usage, storage paths, concurrent hardening.
- **Replay reliability demo**: `scripts/demos/p05_chronicle.sh` — end-to-end demo: checkpoint create/load, restore, rewind roundtrip, rewind_to_latest. Runs key acceptance and integration tests.

### Pending (Week 3)
- Git-integrated checkpoints (branch arcturus/sessions/v1)
- Rewind/resume CLI
- Session Explorer UI enhancements
- Auto-summarization

## 2. Architecture Changes

- New package: `session/` at repo root
  - `schema.py`: Pydantic models for events and checkpoints (incl. git_commit_sha, trace_id, span_id)
  - `alignment.py`: get_git_head_info, get_current_trace_ids for git/checkpoint and trace linking
  - `capture.py`: SessionCapture class, get_capture() singleton
  - `checkpoint.py`: create_checkpoint, list_checkpoints, load_checkpoint (integrates alignment, lock-protected)
  - `README.md`: Module docs, API, concurrent hardening
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
| test_11_checkpoint_includes_git_commit_when_in_repo | Git alignment: checkpoint has git_commit_sha when in repo |
| test_12_checkpoint_includes_trace_id_when_under_span | Trace linking: checkpoint has trace_id under run_span |
| test_13_concurrent_checkpoint_creation_same_session | Concurrent hardening: 8 checkpoints via ThreadPool, all loadable |
| test_14_capture_per_session_sequence | Concurrent hardening: per-session sequence under parallel emits |

Run: `pytest tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py tests/integration/test_chronicle_git_checkpoint_alignment.py -v`

Demo: `./scripts/demos/p05_chronicle.sh`

## 6. Existing Baseline Regression Status
- Command: scripts/test_all.sh quick
- TODO (run after env setup)

## 7. Security And Safety Impact
- Event logs and checkpoints store session data (prompts, outputs, graph state). Stored under `memory/` in repo. Consider .gitignore for `memory/chronicle_*` if sensitive.

## 8. Known Gaps
- Git branch storage (arcturus/sessions/v1) for checkpoints not yet implemented (Week 3); git_commit_sha/branch are captured and stored in checkpoint JSON
- Rewind/resume CLI not implemented (Week 3)
- Session Explorer UI enhancements pending (Week 3)
- Auto-summarization pending (Week 3)

## 9. Rollback Plan
- Remove `session/` package
- Remove `memory/chronicle_events/`, `memory/chronicle_checkpoints/`
- No other code depends on session module in Week 1

## 10. Demo Steps
- Script: `scripts/demos/p05_chronicle.sh` (replay reliability: checkpoint → load → restore → rewind)
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
