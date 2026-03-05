# P06 Canvas Delivery README

## 1. Scope Delivered
- **A2UI v0.9 Protocol**: Full implementation of the agent-to-UI messaging schema in `canvas/schema.py`.
- **Live WebSocket Handler**: Real-time bidirectional communication in `canvas/ws_handler.py`.
- **Canvas Runtime**: Surface lifecycle and component management in `canvas/runtime.py`.
- **Secure Sandbox**: Isolated iframe rendering with CSP and permission management in `canvas/sandbox.py` and `SandboxFrame.tsx`.
- **Widget Library**: Integrated `LineChartWidget`, `MonacoWidget`, and basic UI components (Button, Text, Container).
- **Persistence**: Server-side state snapshots and restoration in `storage/canvas/`.
- **Agent Simulation**: Test scripts for verifying live updates and sandbox isolation.

## 2. Architecture Changes
- **Backend**: Created `canvas/` module to encapsulate all A2UI logic.
- **Frontend**: Created `features/canvas/` directory for React host and widgets.
- **Data Flow**: `Agent Script -> REST API -> CanvasRuntime -> WebSocket -> CanvasHost -> WidgetRegistry -> Render`.
- **Cross-App Triggering**: `CanvasRuntime` is registered as a global singleton in `shared/state.py` (via `get_canvas_runtime()`). This fulfills the architectural requirement that **Canvas must be triggerable from all other applications (Voice, Run, Presentation)** directly in Python without HTTP loopbacks.
- **Persistence**: Snapshots are saved/loaded on API lifespan events in `api.py`.

## 3. API And UI Changes
- **New Endpoints**:
  - `WS /api/canvas/ws/{surface_id}`: Real-time UI synchronization.
  - `GET /api/canvas/state/{surface_id}`: Current surface state retrieval.
  - `POST /api/canvas/test-update/{surface_id}`: Manual state push (for testing).
- **UI Components**: `CanvasHost`, `SandboxFrame`, `WidgetRegistry`.

## 4. Mandatory Test Gate Definition
- **Acceptance/Integration Tests**: 
  - `scripts/seed_canvas_clean.py`: Verifies initial state seeding.
  - `scripts/simulate_agent_action.py`: Verifies live widget updates.
  - `scripts/test_sandbox_visual.py`: Verifies isolated JS execution.
- **Criteria**:
  - WebSocket connection shows "Green" (ReadyState.OPEN).
  - Components render correctly according to A2UI discriminator.
  - State persists through server restart.

## 5. Test Evidence

### 5.1 Real-time Update (A2UI Sync)
**Command:** `uv run scripts/simulate_agent_action.py`
**Output:**
```text
🤖 Agent Simulation starting (using REST API)...
📈 Updating chart data via REST...
Server response: 200
📝 Adding code editor widget via REST...
Server response: 200
✨ Updates pushed. Check your browser!
```
**Result:** Successfully verified `LineChart` and `MonacoEditor` appeared instantly on the frontend without page reload.

### 5.2 Sandbox Execution (JS Isolation)
**Command:** `uv run scripts/test_sandbox_visual.py`
**Output:**
```text
🛡️ Testing Sandbox with Visual Feedback...
🚀 Pushing Sandbox component...
Server response: 200
✨ Check your browser. The box should turn green when you click!
```
**Result:** Verified blue card rendered; card turned green on click with a success alert, confirming isolated JS execution.

### 5.3 State Persistence (Snapshot Recovery)
**Evidence:**
1. Seed cleaned state: `uv run scripts/seed_canvas_clean.py` -> `✅ Clean state written to storage\canvas\main-canvas.json`.
2. Kill API and restart.
3. Fetch state: `curl http://localhost:8000/api/canvas/state/main-canvas`.
**Result:** JSON response matched the seeded snapshot exactly, confirming stable restoration.

## 6. Existing Baseline Regression Status
- **Regression**: No impact on existing Oracle or Nexus flows. 
- **Side Effects**: Added `canvas` tab to Sidebar, ensuring no interference with existing `ide` or `runs` tabs.

## 7. Security And Safety Impact
- **Sandboxing**: iframes use `sandbox="allow-scripts allow-forms allow-popups allow-modals"`.
- **Isolation**: prevents cross-origin data leakage from the main platform to agent-generated UIs.

## 8. Known Gaps
- **Whiteboard**: The whiteboard widget from the charter is currently a placeholder (deferred to future sprint).
- **Concurrency**: Basic support for multiple surfaces, but locking mechanisms for simultaneous agent edits are not yet implemented.

## 9. Rollback Plan
- **Frontend**: Revert `AppLayout.tsx` and `Sidebar.tsx` changes.

## 11. Extended Scope: Phase 3 Infrastructure
### [Day 2 Update] Infrastructure Hardening & Windows Compatibility
We have successfully sanitized the codebase for Windows compatibility (resolving `UnicodeEncodeError`) and verified core infrastructure stability.

**Test Evidence (scripts/verify_phase3.py --all):**
```text
[TEST] Verifying EpisodicMemory Integration...
SUCCESS: Episodic skeleton saved at D:\A1_School_ai_25\001_My_proj_AI\Arcturus\memory\episodes\skeleton_test_verify_...

[TEST] Verifying FileReaderSkill...
SUCCESS: Agent Execution Success!
Agent Output: summary...
```

**Key Fixes:**
- Unified `UnicodeEncodeError` resolution: Replaced emojis with text markers across all core logging (`utils`, `loop`, `agent`, `memory`, `mcp`).
- RAG Stability: Implemented timeouts and error handling for Ollama/Embedding failures.
- Import Fixes: Resolved `ImportError` in `FileReaderSkill`.
- **Task 46: Episodic Memory**: Automatic skeleton generation for session persistence (`memory/episodes/`). Verified via IDE Agent chat simulation (new skeletons present in storage).
- **Task 47: FileReader Skill**: Extracted robust file access tool. Verified via General Agent (Phase3Tester) successfully reading `README.md`.
- **Task 48: Snake Game E2E**: Verified "Plan-to-Code" pipeline with a functional game at `output/snake.html` (Preview link generated).

## 10. Demo Steps
1. Start API: `uv run uvicorn api:app --reload`
2. Start Frontend: `npm run dev`
3. Open `http://localhost:5173/` and click **Canvas icon**.
4. Run: `uv run scripts/test_sandbox_visual.py`
5. Verify: Blue card appears, turns green on click.
