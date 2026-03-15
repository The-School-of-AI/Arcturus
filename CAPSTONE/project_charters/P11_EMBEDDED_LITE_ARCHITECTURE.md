# P11 Embedded / "Lite" Local Architecture

**Purpose:** Design notes and industry context for running Mnemo without Docker on local devices (embedded Qdrant, embedded graph), and for hybrid cloud vs local deployment. Use this when implementing or evaluating the "Lite" architecture from §8.9 Future Phase in P11_UNIFIED_REFERENCE.md.

---

## 1. Swapping Qdrant Docker for Embedded Qdrant

**Difficulty: Low**

The `qdrant-client` supports embedded mode:

```python
# Remote (current)
client = QdrantClient(url=url, api_key=api_key, timeout=10.0)

# Embedded
client = QdrantClient(path="/path/to/storage")
```

**Implementation sketch:**

1. In `memory/qdrant_config.py`: add `get_qdrant_path()` and/or `is_qdrant_embedded()`.
2. In `memory/backends/qdrant_store.py` (around line 78): branch on config; use `QdrantClient(path=...)` when embedded.
3. Env vars: e.g. `QDRANT_MODE=embedded`, `QDRANT_PATH=./memory/qdrant_local/`.

**Data access / investigation:**

- Storage: directory contains `storage.sqlite` and `meta.json`.
- Same Python API: `scroll()`, `retrieve()`, `get_collection()` work identically for local and remote.
- To inspect: instantiate the same client with `path=` and call `scroll()` / `retrieve()`; or add a small script that dumps points. There is no Qdrant UI for embedded mode; for visual inspection you’d run a temporary server and import data if needed.

---

## 2. Swapping Neo4j for Kùzu (Embedded Property Graph)

**Difficulty: Medium–High**

Kùzu supports Cypher and an embedded Python API but has notable differences from Neo4j.

| Aspect | Neo4j | Kùzu |
|--------|--------|------|
| Schema | Schema-less (optional) | Schema required before insert |
| MATCH | Trail semantics (no repeated edges) | Walk semantics (allows repeated edges) |
| Variable-length | Optional upper bound | Upper bound required (default 30) |
| Unsupported | — | `FOREACH`, `REMOVE`, `WHERE` inside patterns |
| `datetime()` | Native | Different / not identical |

**Implementation approach:**

1. Introduce a `KnowledgeGraphProtocol` (like `VectorStoreProtocol`) with `_run_query` / `_run_write`.
2. Implement `KùzuKnowledgeGraph`: define schema (nodes/relationships) before insert; adapt Cypher where needed.
3. For each query in `knowledge_graph.py`: map Neo4j `datetime()` and similar to Kùzu equivalents; adjust MATCH semantics if needed; add upper bounds to variable-length patterns.

Estimate: 2–4 days depending on query volume and edge cases.

---

## 3. Cloud Server vs Local Embedded (Hybrid)

**Feasible: Yes.**

| Role | Vector store | Graph store |
|------|--------------|-------------|
| Central server | Qdrant Cloud | Neo4j Cloud |
| Local instances | Embedded Qdrant (`path=`) | Embedded Kùzu |

**Configuration pattern:**

```env
# Server
VECTOR_STORE_PROVIDER=qdrant
QDRANT_MODE=remote
QDRANT_URL=https://xxx.cloud.qdrant.io
GRAPH_STORE_PROVIDER=neo4j
NEO4J_ENABLED=true
NEO4J_URI=neo4j+s://...

# Local
VECTOR_STORE_PROVIDER=qdrant
QDRANT_MODE=embedded
QDRANT_PATH=./memory/qdrant_local
GRAPH_STORE_PROVIDER=kuzu
NEO4J_ENABLED=false
KUZU_PATH=./memory/kuzu_local
```

Sync Engine already moves **memories** and **spaces**; the server stores them in Qdrant Cloud and ingests into Neo4j. Local instances push/pull memory deltas; no change to sync protocol required. Graph on the server is derived from synced memories; local graph can be derived from local memories (entity IDs may differ until sync).

---

## 4. Kùzu vs Neo4j for Production

**If Kùzu were used for both cloud and local:**

| Aspect | Neo4j | Kùzu |
|--------|--------|------|
| **Model** | Server-based | Embedded (in-process) |
| **Cloud** | AuraDB (managed) | No managed cloud; you host/embed |
| **Multi-user** | Native (concurrent connections, RBAC) | Single-process; no built-in multi-user server |

**Production readiness:**

- **Neo4j:** Server model, AuraDB managed cloud, HA, backups, RBAC, long production history.
- **Kùzu:** Embeddable library; strong for analytics, notebooks, edge, single-user apps. Enterprise Edition (server mode, HA, security) is in development (waitlist); no managed cloud.

**Performance:** Kùzu is optimized for analytical workloads and can handle very large graphs (hundreds of millions of nodes, billions of edges) on one machine. Neo4j is general-purpose for mixed OLTP/OLAP.

**Recommendation:** Use **Kùzu for local/embedded only** and **Neo4j for the central cloud** to keep embedded local mode without giving up managed cloud and multi-user production. Standardizing on Kùzu everywhere is viable only if you are comfortable running it embedded in your API process and self-managing backups/HA.

---

## 5. Alternatives to Kùzu (Embedded Graph)

Neo4j has **no embedded option** for Python; it is always a separate JVM process.

**Embedded graph database options:**

| Option | Type | Query | Cypher? | Notes |
|--------|------|--------|---------|--------|
| **Kùzu** | Embedded lib | Cypher | Yes (OpenCypher) | Schema required; strong analytics |
| **FalkorDBLite** | Subprocess | Cypher | Yes | Redis + FalkorDB as subprocess; no Docker; same Cypher as FalkorDB; easy path to FalkorDB Cloud |
| **CogDB** | Pure Python | Torque (Python API) | No | Graph + vector in one; lighter |
| **Coffy** | Pure Python | Declarative | No | Built on NetworkX; NoSQL/SQL/Graph |
| **NetworkX** | In-memory | Python | No | Prototyping only; no persistence by default |

If Cypher compatibility matters: **Kùzu** or **FalkorDBLite**. FalkorDBLite gives a smooth path to FalkorDB Cloud or self-hosted for production.

---

## 6. Embedded Vector Store Options

| Option | Type | Docker? | Notes |
|--------|------|--------|-------|
| **Qdrant `path=`** | Embedded lib | No | Same client; `path` instead of `url`; SQLite-backed |
| **Chroma** | Embedded | No | Common for RAG; SQLite/duckdb backend |
| **LanceDB** | Embedded | No | File-based; multimodal; DuckDB integration |
| **sqlite-vec** | SQLite extension | No | Minimal; "SQLite for vectors" |
| **FAISS** | In-memory | No | Already used; no persistence without extra code |

---

## 7. Industry Practice

1. **Divergence between dev and prod is normal** — e.g. SQLite locally, Postgres in production.
2. **Embedded vector stores are common** for local/RAG — Chroma, LanceDB, Qdrant local, sqlite-vec.
3. **Embedded graph DBs are less common** — most production graph is server-based (Neo4j, Neptune, Tigergraph); Kùzu and FalkorDBLite are used for edge/embedded/local.
4. **Running full Docker stack on every laptop is often overkill** — many teams use embedded vector + embedded or in-memory graph locally and reserve server DBs for production.

**Recommended pattern:** Abstract vector and graph behind protocols; use embedded backends locally (Qdrant embedded, Kùzu or FalkorDBLite) and cloud/server backends in production (Qdrant Cloud, Neo4j), with env-based configuration to switch.

---

## 8. Summary Table

| Swap | Effort | Data access |
|------|--------|-------------|
| Qdrant Docker → embedded | Low (config + branch) | Same Python API; `scroll`/`retrieve`; SQLite under path |
| Neo4j → Kùzu | Medium–high (abstraction + schema + Cypher adaptation) | Native Kùzu API; disk files under path |
| Cloud vs local hybrid | Low (env-based routing) | Per-instance: either cloud or embedded |

**Order of implementation:** (1) Add embedded Qdrant via `QDRANT_MODE`/`QDRANT_PATH`. (2) Introduce `KnowledgeGraphProtocol` and Kùzu backend with schema and Cypher tweaks. (3) Add `GRAPH_STORE_PROVIDER` (and optionally `QDRANT_MODE`) so the same codebase runs cloud vs local via configuration.
