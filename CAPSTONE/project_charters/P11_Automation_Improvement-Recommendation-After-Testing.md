# Mnemo: Recommended Improvements & Identified Fixes

During the process of stabilizing the integration test suite, several architectural "gotchas" were identified. Addressing these will improve the long-term reliability of the Mnemo project.

## 1. Core Codebase Improvements (High Priority)

### 🚨 Timezone Standardization (Sync Engine)
- **Issue**: [merge_memory_change](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/sync/merge.py#46-63) was prone to `TypeError` when comparing naive datetimes (from Qdrant) with aware datetimes (from the Sync payload).
- **Recommendation**: Ensure the `ISO_FORMAT` used throughout the app includes the `Z` suffix or offset, and ensure the [_parse_iso](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/sync/merge.py#11-25) utility always returns a timezone-aware object.
- **Status**: Fixed in [merge.py](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/sync/merge.py) for Conflict Resolution, but should be audited in [backends/qdrant_store.py](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/backends/qdrant_store.py) and `backends/mongo_store.py`.

### 🛡️ Dependency Injection vs. Module-Level Singletons
- **Issue**: Many routers and stores initialize their dependencies (like [KnowledgeGraph](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/knowledge_graph.py#100-2097)) at the module level. This makes unit testing and environment overrides (like `MNEMO_ENABLED`) extremely difficult because the state is captured once at boot.
- **Recommendation**: Move toward a Dependency Injection (DI) pattern or ensure that [get_remme_store()](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/shared/state.py#209-217) and [get_knowledge_graph()](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/knowledge_graph.py#2103-2109) check the environment every time or can be "flushed".
- **Status**: Mitigated in tests via [conftest.py](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/tests/conftest.py) singleton resets, but remains a debt in the production architecture.

### 🧩 Sync Payload Unification
- **Issue**: [MemoryDelta](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/sync/schema.py#16-26) and [SyncChange](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/sync/schema.py#62-120) had slight mismatches in how they expected their [payload](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/lifecycle.py#105-129) to be nested, leading to Pydantic validation errors during cross-device sync.
- **Recommendation**: Unify the [SyncChange](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/sync/schema.py#62-120) constructor to use the same logic as the [VectorStore](file:///Users/gitesh.grover/Study/AI-EVA2/capstone/Antigravity/Arcturus/memory/backends/qdrant_store.py#57-655) point structure.
- **Status**: Fixed for currently failing cases.

## 2. Testing Improvements

### 🕒 Asynchronous State Verification
- **Issue**: Increasing `ASYNC_KG_INGEST=true` is great for performance but dangerous for data-integrity checks if not handled.
- **Recommendation**: Implement a `wait_for_condition` utility in the test suite that polls Neo4j/Qdrant with a timeout, rather than hardcoding `time.sleep()`. This will make the tests faster on high-speed runners.

### 👤 Simulated User Transitions
- **Issue**: Moving a guest's data to a registered user's account is a complex operation that currently requires bypassing the `MemoryRetriever` filters.
- **Recommendation**: Formalize the "Registration Migration" service as a dedicated utility in `shared.auth` or `remme.service` rather than doing ad-hoc Qdrant updates.

---

## Implementation Assessment (Arcturus Codebase)

Review of the above recommendations against this repo. Paths in this project are under `Arcturus/` (no Antigravity).

| Recommendation | Makes sense? | Current state | Suggested action |
|----------------|--------------|---------------|------------------|
| **1. Timezone standardization** | **Yes** | `memory/sync/merge.py` already has `_parse_iso()` that normalizes to UTC and handles naive datetimes (lines 11–24), so merge logic is safe. `memory/backends/qdrant_store.py` uses `datetime.now().isoformat()` (no `Z`), so stored values are naive. | **Implement:** Audit and standardize: in `qdrant_store.py` (and any mongo_store) use UTC and emit ISO strings with `Z` (e.g. `datetime.now(timezone.utc).isoformat()` or append `Z`). Prevents future bugs when other code assumes aware datetimes. Low effort. |
| **2. DI / singletons** | **Yes (partial)** | `get_remme_store()` and `get_knowledge_graph()` in `shared/state.py` and `memory/knowledge_graph.py` are create-once singletons. Tests work around via mocks in `tests/automation/p11_mnemo/conftest.py`. | **Implement (light):** Add a test-only “flush” (e.g. set global to `None` in a dedicated test helper or conftest) so automation can reset state when needed. Full DI is optional long-term. Avoid “check env every time” in hot paths unless low-cost. |
| **3. Sync payload unification** | **Validate first** | `SyncChange.from_memory()` nests `m.payload` as `payload["payload"]`; `_apply_memory_change()` in `memory/sync/engine.py` and `_apply_change_to_store()` in `routers/sync.py` both expect `payload.get("payload", {})` for metadata. Structure is consistent. | **Validate:** Run sync integration tests (e.g. `test_sync_two_devices_converge`, P11 TG4). If they pass, consider this satisfied. If Pydantic or apply errors appear, align `MemoryDelta` / change_tracker with the exact payload shape produced by `qdrant_store` when building points. |
| **4. wait_for_condition (async state)** | **Yes** | P11 automation uses `time.sleep(0.3–1.0)` in multiple tests (sequential scenario, Neo4j verification, recommend-space, registration migration). | **Implement:** Add a `wait_for_condition(callback, timeout_sec, interval_sec)` helper in `tests/automation/p11_mnemo/helpers.py` that polls until the callback returns truthy or timeout. Replace fixed `time.sleep()` in tests that assert on Neo4j/Qdrant state. Makes tests faster and more reliable under load. |
| **5. Formalize registration migration** | **Yes** | `memory/auth/migration.py` already provides `migrate_guest_to_registered()` (Qdrant + Neo4j). | **Implement:** Ensure all “guest → registered” flows (including tests) call this function only; remove any ad-hoc Qdrant/Neo4j updates elsewhere. Document it as the single migration entry point in README or P11 docs. |

**Summary:** Implement 1 (timezone in store), 2 (test flush for singletons), 4 (`wait_for_condition`), and 5 (use single migration path). Validate 3 (sync payload) via existing sync tests; only change if failures appear.
