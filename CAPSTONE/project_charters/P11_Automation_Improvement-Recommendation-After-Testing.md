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
