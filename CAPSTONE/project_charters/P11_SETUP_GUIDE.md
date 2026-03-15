# P11 Setup Guide — Qdrant, Neo4j, Sync & Auth

This guide helps you set up the Mnemo stack (Qdrant, Neo4j, optional Sync Engine and Auth). Use **Quick setup** if you want to get running with Docker quickly; use **Configuration reference** for env vars and detailed options.

---

## Quick Setup (Docker)

For a fast local setup with minimal configuration:

1. **Start services**
   ```bash
   docker-compose up -d
   ```
   This starts Qdrant (port 6333) and Neo4j (port 7687, UI 7474). Data is persisted under `./data/`.

2. **Configure environment**
   - Copy `.env.example` to `.env` if needed.
   - Add or ensure the following (Docker defaults work with these):
   ```bash
   VECTOR_STORE_PROVIDER=qdrant
   RAG_VECTOR_STORE_PROVIDER=qdrant
   QDRANT_URL=http://localhost:6333
   # Optional: NEO4J_ENABLED=true, NEO4J_URI=bolt://localhost:7687, NEO4J_USER=neo4j, NEO4J_PASSWORD=arcturus-neo4j
   ```
   For Neo4j knowledge graph, also set:
   ```bash
   NEO4J_ENABLED=true
   NEO4J_URI=bolt://localhost:7687
   NEO4J_USER=neo4j
   NEO4J_PASSWORD=arcturus-neo4j
   ```
   (Match `NEO4J_AUTH` in docker-compose; default is `neo4j/arcturus-neo4j`.)

3. **Run migrations (optional but recommended)**
   ```bash
   uv run python scripts/migrate_all_memories.py
   # or: uv run python scripts/migrate_all_memories.py docker
   ```
   This migrates FAISS memories → Qdrant, RAG → Qdrant, then backfills Qdrant → Neo4j. The script can offer to append sensible defaults to `.env`.

4. **Verify**
   ```bash
   uv run python scripts/test_qdrant_setup.py
   ```
   For Neo4j: open http://localhost:7474 and log in with the same credentials.

5. **Start the API**
   ```bash
   uv run uvicorn api:app --host 0.0.0.0 --port 8000
   ```

You can keep using FAISS and skip Qdrant/Neo4j by leaving `VECTOR_STORE_PROVIDER` unset (default `faiss`) and `NEO4J_ENABLED=false`.

---

## Configuration Reference

### Prerequisites

- Python 3.11+
- Dependencies: `uv sync` or `pip install -e .`
- For Docker: Docker and Docker Compose
- For Neo4j entity extraction: Ollama running (LLM used for extraction); Neo4j driver is included via `uv sync`

### Environment Variables

#### Qdrant (vector store)

| Variable | Purpose | Default |
|----------|---------|---------|
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | API key (Qdrant Cloud) | — |
| `VECTOR_STORE_PROVIDER` | RemMe memories backend | `faiss` |
| `RAG_VECTOR_STORE_PROVIDER` | RAG chunks backend | `faiss` |

#### Neo4j (knowledge graph)

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEO4J_ENABLED` | Enable Neo4j | `false` |
| `NEO4J_URI` | Bolt URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Username | `neo4j` |
| `NEO4J_PASSWORD` | Password | (required when enabled) |

#### Mnemo unified path

| Variable | Purpose | Default |
|----------|---------|---------|
| `MNEMO_ENABLED` | Unified extractor, Neo4j Fact/Evidence, preferences adapter | `false` |

#### Sync Engine (Phase 4)

| Variable | Purpose | Default |
|----------|---------|---------|
| `SYNC_ENGINE_ENABLED` | Enable push/pull sync | `false` |
| `SYNC_SERVER_URL` | Sync server base URL (e.g. `http://localhost:8000/api`) | — |
| `DEVICE_ID` | This device ID | auto-generated and cached |

#### Auth (Phase 5)

| Variable | Purpose | Default |
|----------|---------|---------|
| `MNEMO_SECRET_KEY` | JWT signing secret (HS256); required for login/register | — |

#### Other

| Variable | Purpose | Default |
|----------|---------|---------|
| `EPISODIC_STORE_PROVIDER` | Episodic store: `qdrant` \| `legacy` | — |
| `ASYNC_KG_INGEST` | Run KG ingestion in background after add | `false` |

### Qdrant: Cloud vs Docker

- **Docker:** `docker-compose up -d`; use `QDRANT_URL=http://localhost:6333`; no API key needed for local.
- **Qdrant Cloud:** Create a cluster, get URL and API key, set `QDRANT_URL`, `QDRANT_API_KEY`, and the provider vars above.

### Neo4j: Docker vs Aura

- **Docker:** `docker-compose up -d neo4j`; use `NEO4J_URI=bolt://localhost:7687` and credentials from `NEO4J_AUTH` in docker-compose.
- **Neo4j Aura:** Use `neo4j+s://...` URI and your Aura credentials in `.env`.

### Migrations

- **All-in-one:** `uv run python scripts/migrate_all_memories.py` (or `migrate_all_memories.py docker` / `cloud`). Runs FAISS→Qdrant (memories), RAG→Qdrant, Qdrant→Neo4j.
- **Individual scripts:**
  - RemMe memories: `uv run python scripts/migrate_faiss_to_qdrant.py`
  - RAG chunks: `uv run python scripts/migrate_rag_faiss_to_qdrant.py`
  - Neo4j backfill: `uv run python scripts/migrate_memories_to_neo4j.py`
- **Hubs → Neo4j (one-time):** `uv run python scripts/migrate_hubs_to_neo4j.py` (or `--dry-run`)

### Sync Engine: One-Server vs Two-Stores

- **One-server (protocol test):** Same app and same Qdrant/Neo4j. Set `SYNC_ENGINE_ENABLED=true`, `SYNC_SERVER_URL=http://localhost:8000/api`. Push/pull run against the same store; no replication, only sync log and LWW merge.
- **Two-stores (replication):** Run one API as “server” (its own Qdrant/Neo4j). Run another as “device” with a **different** Qdrant/Neo4j and `SYNC_SERVER_URL` pointing at the server. Then push/pull replicate data between server and device.

### Auth (Login/Register)

- Generate a secret: `openssl rand -base64 48` or `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- Set `MNEMO_SECRET_KEY=<secret>` in `.env`. Without it, the app starts and guest flow works, but login/register return 503.

### Troubleshooting

- **Qdrant connection refused:** Ensure Docker is running and port 6333 is free; check `docker logs arcturus-qdrant`.
- **Neo4j connection failed:** Use `bolt://` (not http); ensure auth matches docker-compose `NEO4J_AUTH`.
- **Entity extraction fails:** Ollama must be running; check entity-extraction model in config/skills.
- **Sync 503:** Set `SYNC_ENGINE_ENABLED=true` and `SYNC_SERVER_URL` (no trailing slash).

---

## Future Enhancements and Improvements

- **Embedded Qdrant:** Use Qdrant with `path=` for fully local, no-Docker vector storage (see lite architecture design).
- **Load testing:** Sync load tests (multiple devices, burst changes, reconnection) and target apply latency (e.g. ≤100 ms).
- **Production auth:** Move to RS256 and external key management (see `P11_AUTH_DESIGN.md`).

---

**Related:** `P11_DETAILED_ARCHITECTURE.md`, `P11_DELIVERY_README.md`.
