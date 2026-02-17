# PROJECT 8: "Legion" — Multi-Agent Swarm Orchestration


> **Inspired by:** GenSpark (multi-agent orchestration), OpenClaw (agent-to-agent sessions), existing scaling plan (Project "Legion")
> **Team:** Core AI Engineering · **Priority:** P0 · **Duration:** 4 weeks

### Objective
Enable **multi-agent collaboration** where a Manager Agent can spawn, coordinate, and aggregate results from multiple Worker Agents — each specialized for different tasks — operating on shared or isolated memory contexts.

### Detailed Features

#### 8.1 Agent Topology
- **Manager-Worker pattern:** 1 Manager routes sub-tasks to N Workers with different specializations
- **Peer-to-Peer pattern:** Agents communicate laterally for consensus/debate before responding
- **Pipeline pattern:** Sequential chain where output of Agent A feeds into Agent B
- **Predefined departments:**
  - Research Department (3 agents: web researcher, academic researcher, data analyst)
  - Engineering Department (3 agents: architect, coder, reviewer)
  - Content Department (3 agents: writer, editor, designer)
  - Business Department (3 agents: strategist, analyst, communicator)

#### 8.2 Agent Communication Protocol
- **Message passing:** Structured `AgentMessage` with `{from_agent, to_agent, task_id, content, artifacts[]}`
- **Shared workspace:** Agents can read/write to shared files and memory spaces
- **Isolated contexts:** Per-agent episodic memory with optional shared knowledge base
- **Progress reporting:** Each agent reports task completion % and intermediate results

#### 8.3 Task Decomposition & Orchestration
- **Intelligent decomposer:** Manager agent analyzes user request and creates a DAG of sub-tasks
- **Dependency resolution:** Tasks execute in correct order based on data dependencies
- **Parallel execution:** Independent tasks execute concurrently, results merged at sync points
- **Failure handling:** If an agent fails, Manager can retry, reassign, or degrade gracefully
- **Budget management:** Total token/cost budget split across agents with priority weighting

#### 8.4 Swarm UI
- **Agent graph visualization:** Real-time DAG showing agents, tasks, data flows, and status
- **Agent chat peek:** View any agent's current conversation/reasoning in a side panel
- **Manual intervention:** User can provide feedback to any agent or redirect the swarm
- **Swarm templates:** Save and reuse successful agent configurations

#### 8.5 Deliverables
- `agents/manager.py` — manager agent with task decomposition
- `agents/worker.py` — generic worker agent with specialization hooks
- `agents/protocol.py` — inter-agent message protocol
- `agents/swarm_runner.py` — swarm lifecycle manager (spawn, monitor, collect)
- `agents/departments/` — pre-built department configurations
- Frontend: `features/swarm/` — swarm visualization, agent peek, intervention controls

### Strategy
- Use Ray.io actor model for agent process isolation and communication
- Start with Manager-Worker for v1, add Peer-to-Peer and Pipeline in v2
- Integrate with Project 5 (Chronicle) — all multi-agent sessions fully captured

---

## 20-Day Execution Addendum

### Team Split
- Student A: Decomposer/manager and scheduling.
- Student B: Worker protocol, swarm observability, and intervention UI.

### Day Plan
- Days 1-5: DAG decomposer and agent protocol.
- Days 6-10: Worker lifecycle, retries, and budget allocation.
- Days 11-15: Swarm UI graph and manual intervention actions.
- Days 16-20: Failure-injection testing and tuning.

### Mandatory Test Gate
- Acceptance: `tests/acceptance/p08_legion/test_swarm_completes_with_worker_failure.py`
- Integration: `tests/integration/test_legion_chronicle_capture.py`
- CI required check: `p08-legion-swarm`

### Expanded Mandatory Test Gate Contract (10 Hard Conditions)

#### Acceptance Hard Conditions
1. The acceptance file declared above must exist and contain at least 8 executable test cases.
2. Happy-path user flow must pass end-to-end for this project's core feature.
3. Invalid-input and malformed-payload behavior must return controlled errors (no crashes).
4. Retry/idempotency behavior must be validated where external calls or queued tasks are used.
5. A decomposed DAG with at least 3 worker roles must complete successfully, including retry/reassign when one worker fails.

#### Integration Hard Conditions
6. The integration file declared above must exist and include at least 5 executable integration scenarios.
7. Integration must prove Legion sessions are fully captured by Chronicle and can consume Mnemo shared memory context.
8. Cross-project failure propagation must be tested (upstream failure to graceful downstream behavior with logs/metrics).

#### CI And Delivery Hard Conditions
9. CI check p08-legion-swarm must run and require all of the following:
   - project acceptance tests,
   - project integration tests,
   - baseline regression suite: scripts/test_all.sh quick (the earlier consolidated test baseline),
   - lint/typecheck for touched code paths.
10. Branch delivery evidence is mandatory:
   - add CAPSTONE/project_charters/P08_DELIVERY_README.md,
   - include sections: Scope Delivered, Architecture Changes, API/UI Changes, Test Evidence, Known Gaps, Rollback Plan, Demo Steps,
   - CI fails if this README file is missing,
   - project P95 target: < 2.0s scheduler decision latency.
