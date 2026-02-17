# PROJECT 5: "Chronicle" — AI Session Tracking & Reproducibility


> **Inspired by:** Entire.io (session capture, checkpoints, rewind/resume, git integration)
> **Team:** Developer Tools · **Priority:** P1 · **Duration:** 3 weeks

### Objective
Build a comprehensive **AI session capture system** that records every agent interaction (prompts, responses, tool calls, files modified, reasoning traces) with git-integrated checkpoint/rewind capabilities — enabling full reproducibility and auditability.

### Detailed Features

#### 5.1 Session Capture Engine
- **Auto-capture everything:** Every agent interaction recorded:
  - User prompts (text, files, images)
  - Agent reasoning traces (chain-of-thought, tool selection rationale)
  - Tool invocations (name, args, results, duration)
  - Files created/modified/deleted (full diffs)
  - Model used, token counts, latency metrics
  - Memory reads/writes (episodic memory access log)
- **Session metadata:** Start time, duration, user, agent config, model versions, skill set
- **Low-overhead capture:** Async event streaming to avoid impacting agent latency

#### 5.2 Git-Integrated Checkpoints
- **Automatic checkpointing:** Create checkpoint on each commit or after each agent response (configurable strategy)
- **Checkpoint storage:** Store session data on a separate git branch (`arcturus/sessions/v1`) to keep main branch clean
- **Checkpoint contents:** Full session transcript + file diffs + agent state snapshot
- **Rewind:** `arcturus rewind` — interactive checkpoint selector, restores code and agent state to any checkpoint
- **Resume:** `arcturus resume <branch>` — restore session context and continue where you left off

#### 5.3 Session Explorer UI
- **Timeline view:** Visual timeline of all agent interactions in a session
- **Diff viewer:** Side-by-side file diffs at any checkpoint
- **Replay mode:** Step-through replay of agent reasoning + actions (already exists in `features/replay/`)
- **Search across sessions:** Full-text search across all past sessions
- **Session comparison:** Compare two sessions side-by-side (e.g., before/after a prompt change)

#### 5.4 Auto-Summarization
- **Per-session summaries:** Auto-generate a concise summary of what was accomplished
- **Commit message generation:** Auto-generate meaningful git commit messages from session activity
- **Weekly digest:** Automated weekly report of all AI sessions, changes made, time saved

#### 5.5 CLI Integration
- `arcturus session status` — current session info
- `arcturus session list` — list recent sessions
- `arcturus session rewind [checkpoint-id]` — rewind to checkpoint
- `arcturus session resume <session-id>` — resume a previous session
- `arcturus session export <session-id>` — export session transcript as Markdown

#### 5.6 Deliverables
- `session/capture.py` — async event capture engine
- `session/checkpoint.py` — git-integrated checkpoint manager
- `session/rewind.py` — state restoration engine
- `session/summarizer.py` — auto-summarization agent
- CLI: `scripts/arcturus_session.py` — session management CLI
- Frontend: enhance `features/replay/` with full session explorer, search, comparison

### Strategy
- Leverage existing `features/replay/` UI as foundation
- Build capture engine as middleware in `core/loop.py` — intercept all agent actions
- Use git worktree awareness for concurrent session support

---

## 20-Day Execution Addendum

### Team Split
- Student A: Event capture and storage model.
- Student B: Rewind/replay CLI + timeline UI.

### Day Plan
- Days 1-5: Capture protocol and immutable event log.
- Days 6-10: Checkpoint creation and restore semantics.
- Days 11-15: Replay UX and diff visualizer.
- Days 16-20: Load tests and reproducibility verification.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py`
- Integration: `tests/integration/test_chronicle_git_checkpoint_alignment.py`
- CI required check: `p05-chronicle-replay`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. Capture must record prompts, tool calls, outputs, and file diffs per step; rewind must restore identical state hash for chosen checkpoint.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Chronicle captures Legion multi-agent flows and IDE actions with coherent timeline ordering.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p05-chronicle-replay must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P05_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 500ms capture overhead per step.
