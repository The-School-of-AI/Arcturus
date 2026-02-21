# P08 Legion — Delivery README

## Scope Delivered

**Days 1-5: DAG decomposer and agent protocol** (Student A track)

| Deliverable | File | Status |
|---|---|---|
| Manager agent with LLM task decomposition | `agents/manager.py` | ✅ |
| Generic worker agent with role specialisation | `agents/worker.py` | ✅ |
| Inter-agent message protocol | `agents/protocol.py` | ✅ |
| Swarm lifecycle manager (spawn, monitor, collect) | `agents/swarm_runner.py` | ✅ |
| ManagerAgent skill + system prompt | `core/skills/library/manager/skill.py` | ✅ |
| Acceptance tests (8/8 passing) | `tests/acceptance/p08_legion/test_swarm_completes_with_worker_failure.py` | ✅ |

**Not in Days 1-5 scope** (per charter Day Plan):
- `agents/departments/` — Days 6-10
- Swarm UI (`features/swarm/`) — Days 11-15
- Integration tests with Chronicle/Mnemo — Days 6-10
- CI check `p08-legion-swarm` — Days 6-10

---

## Architecture Changes

### New files
```
agents/
  manager.py          — Ray Actor; calls LLM via ModelManager + skill-loaded prompt
  worker.py           — Ray Actor; executes tasks assigned by SwarmRunner
  protocol.py         — Pydantic models: Task, AgentMessage, Artifact, TaskStatus
  swarm_runner.py     — Orchestrates Ray actors; topological DAG execution with retry

core/skills/library/manager/
  skill.py            — DECOMPOSER_SYSTEM_PROMPT; registered in skills registry

tests/acceptance/p08_legion/
  test_swarm_completes_with_worker_failure.py   — 8 acceptance tests
```

### Modified files
```
config/agent_config.yaml   — added ManagerAgent entry with skills: [manager]
config/profiles.yaml       — added strategy.max_task_retries: 2
core/skills/registry.json  — registered "manager" skill
pyproject.toml             — added ray[default]==2.40.0, pytest, pytest-asyncio
```

### Key design decisions
- **Ray Actor model** for process isolation (per charter Strategy section)
- **`asyncio`-based orchestration** in `SwarmRunner` (Ray's Windows async limitations)
- **Skill-loaded prompt**: `ManagerAgent` loads its prompt via `AgentRegistry` + `SkillManager`, identical to all other agents — no hardcoded strings
- **`max_task_retries` in `profiles.yaml`**: follows the same pattern as `max_steps` and `max_lifelines_per_step` — operator-configurable without code changes

---

## API / UI Changes

**No UI changes** (Swarm UI is Days 11-15).

**New internal API** (`SwarmRunner`):
```python
# Decompose via LLM then execute
await runner.run_request("Write a blog post about AI")

# Inject task list directly (used in tests, bypasses LLM)
await runner.run_tasks([task_dict, ...])
```

---

## Test Evidence

```
uv run pytest tests/acceptance/p08_legion/test_swarm_completes_with_worker_failure.py -v

8/8 PASSED in 20.87s

test_protocol_task_fields_and_defaults         PASSED
test_protocol_task_status_enum                 PASSED
test_protocol_agent_message_creation           PASSED
test_happy_path_two_task_dag_completes         PASSED
test_dag_with_3_worker_roles_completes         PASSED
test_worker_failure_triggers_retry_and_completes  PASSED
test_invalid_task_payload_returns_controlled_error PASSED
test_dependency_order_respected                PASSED
```

Charter hard conditions covered:

| Condition | Test |
|---|---|
| ≥8 executable tests | All 8 |
| Happy-path end-to-end | Tests 4, 5 |
| Invalid input → controlled error | Test 7 |
| Retry/idempotency validated | Test 6 |
| ≥3 worker roles + retry | Tests 5, 6 |

---

## Known Gaps

| Gap | Charter Ref | Planned |
|---|---|---|
| `agents/departments/` not created | Section 8.1, Section 8.5 | Days 6-10 |
| Progress reporting (completion %) | Section 8.2 | Days 6-10 |
| Integration tests (Chronicle/Mnemo) | Hard conditions 6-8 | Days 6-10 |
| CI check `p08-legion-swarm` | Hard condition 9 | Days 6-10 |
| Swarm UI | Section 8.4 | Days 11-15 |
| P2P + Pipeline agent topologies | Section 8.1 | v2 |

---

## Rollback Plan

All P08 files are **additive** — no existing system files were removed or their logic changed in a breaking way.

To roll back:
```bash
git revert HEAD  # reverts the Days 1-5 commit
# or
git checkout master -- agents/ tests/acceptance/p08_legion/
```

The only shared-file changes are in `pyproject.toml` (new deps), `profiles.yaml` (new key), `registry.json` (new skill entry), and `agent_config.yaml` (new agent entry) — all backward-compatible additions.

---

## Demo Steps

```bash
# 1. Install deps
uv sync

# 2. Run acceptance tests (no LLM key needed — tests use FakeWorker + run_tasks())
uv run pytest tests/acceptance/p08_legion/ -v

# 3. Run live decompose (requires GEMINI_API_KEY or Ollama running)
uv run python -c "
import asyncio
from agents.swarm_runner import SwarmRunner

async def demo():
    runner = SwarmRunner()
    await runner.initialize()
    results = await runner.run_request('Write a short blog post about multi-agent AI systems')
    for r in results:
        print(r['title'], '->', r['status'], '|', r.get('result', '')[:80])

asyncio.run(demo())
"
```
