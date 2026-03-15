# P05 Chronicle — Session Capture & Reproducibility

AI session capture system for agent interaction tracking, checkpoints, and rewind.

## Overview

- **session/schema.py** — Event types, `EventLogEntry`, `CheckpointSnapshot` (incl. git alignment, trace linking)
- **session/capture.py** — Async event capture (queue + background writer), hardened for concurrent edits
- **session/checkpoint.py** — Deterministic checkpoints with git/trace alignment, lock-protected writes
- **session/rewind.py** — Restore from checkpoint, state invariants
- **session/alignment.py** — Git HEAD info, OpenTelemetry trace_id/span_id for cross-module linking

## API

```python
from session.capture import get_capture
from session.schema import EventType
from session.checkpoint import create_checkpoint, load_checkpoint, list_checkpoints
from session.rewind import restore_from_checkpoint, rewind_to_latest, list_available_checkpoints
```

## Usage

1. **Capture events** — `get_capture().emit(EventType.STEP_START, {...}, session_id="run-123")`
2. **Create checkpoint** — `create_checkpoint("run-123", "step_complete", plan_graph)`
3. **Restore** — `context, result = restore_from_checkpoint(loaded_snapshot)`

## Storage

- Event logs: `memory/chronicle_events/events_{session_id}.ndjson`
- Checkpoints: `memory/chronicle_checkpoints/{session_id}/checkpoint_{hash}.json`

## Concurrent Edit Hardening

- Per-session sequence numbers for event ordering
- Lock-protected appends to NDJSON event logs
- Per-session locks for checkpoint creation
