# Project 11 Setup Guide: Qdrant & Neo4j (Mnemo)

This guide will help you set up Qdrant (cloud or local via Docker) and Neo4j for Project 11 (Mnemo).

**Two vector stores** use Qdrant:
- **Remme memories** (`arcturus_memories`) — user preferences, facts, identity
- **RAG chunks** (`arcturus_rag_chunks`) — document chunks, conversation history

**Neo4j knowledge graph** (Phase 2/3):
- **Entities & relationships** — extracted from Remme memories; linked via `memory_id`, `entity_ids`
- **Dual-path retrieval** — semantic (Qdrant) + entity recall (Neo4j); rescues when vector search returns 0

**Note**: You don't need to do these steps if you don't want to move to Qdrant/Neo4j. The default config uses FAISS (legacy) for vector stores; knowledge graph is disabled unless `NEO4J_ENABLED=true`.

## Prerequisites

- Python 3.11+
- Project dependencies installed (`uv sync` or `pip install -e .`)
- For Docker: Docker and Docker Compose installed
- **For Neo4j knowledge graph**: Ollama running (entity extraction uses LLM); Neo4j driver (`pip install neo4j` or `uv sync`)

## Step 1: Set Up Qdrant

Choose one of the following options:

### Option 1: Qdrant Cloud

1. **Create a Qdrant Cloud cluster**
   - Go to [Qdrant Cloud](https://cloud.qdrant.io/)
   - Sign up or log in
   - Create a new cluster and choose your region

2. **Get your cluster URL and API key**
   - In the Qdrant Cloud Console, find your cluster URL (e.g. `https://xyz-example.region.cloud-provider.cloud.qdrant.io`)
   - Go to **API Keys**, create a new key, and copy it

3. **Configure `.env`**
   - Copy `.env.example` to `.env` if you haven't already
   - Add the following (or update existing values):

   ```
   QDRANT_URL=https://your-cluster-id.region.cloud-provider.cloud.qdrant.io
   QDRANT_API_KEY=your-api-key-here
   VECTOR_STORE_PROVIDER=qdrant
   RAG_VECTOR_STORE_PROVIDER=qdrant
   ```

   See `.env.example` for Neo4j variables if using the knowledge graph.

   The application reads these from the environment (see `memory/qdrant_config.py`). No code changes are required.

### Option 2: Docker (local)

From the project root directory, run:

```bash
docker-compose up -d
```

This will:
- Pull the latest Qdrant image
- Start Qdrant on port 6333 (REST API) and 6334 (gRPC)
- Persist data to `./data/qdrant_storage/`

**Verify it's running:**
```bash
docker ps | grep qdrant
```

You should see `arcturus-qdrant` container running.

**Optional**: Add to `.env` to use Qdrant:
```
VECTOR_STORE_PROVIDER=qdrant
RAG_VECTOR_STORE_PROVIDER=qdrant
```

## Step 2: Check Qdrant Health

Open your browser and visit:
- **REST API (Docker)**: http://localhost:6333/dashboard
- **Health Check (Docker)**: http://localhost:6333/health
- **Cloud**: Use `https://<your-cluster-url>/health` (replace with your `QDRANT_URL`)

You should see a JSON response with `"status": "ok"`.

## Step 3: Install Dependencies

Make sure you have the Qdrant client installed:

```bash
# If using uv
uv sync

# Or if using pip
pip install qdrant-client>=1.7.0
```

## Step 4: Run Test Script

Test the connection and basic operations:

```bash
# For Qdrant Cloud: ensure .env has QDRANT_URL and QDRANT_API_KEY (script loads .env)
uv run python scripts/test_qdrant_setup.py
```

Expected output:
```
🧪 Qdrant Vector Store Test Suite
============================================================
🔍 Testing Qdrant Connection...
✅ Successfully connected to Qdrant!
📝 Testing Add and Search Operations...
  ✅ Added memory 1: abc12345...
  ✅ Added memory 2: def67890...
  ...
✅ All tests completed!
```

## Step 5: Verify in Qdrant Dashboard

1. **Docker**: Open http://localhost:6333/dashboard  
   **Cloud**: Open your cluster dashboard in Qdrant Cloud Console
2. Collections (created on first use):
   - `arcturus_memories` — Remme memories (user preferences, facts)
   - `arcturus_rag_chunks` — RAG document chunks
   - `test_memories` — created by test script
3. Check the points count for each collection

## Troubleshooting

### Qdrant won't start
```bash
# Check if port 6333 is already in use
lsof -i :6333

# Stop existing Qdrant if needed
docker-compose down

# Start fresh
docker-compose up -d
```

### Connection refused
- Make sure Docker is running
- Check container logs: `docker logs arcturus-qdrant`
- Verify ports are not blocked by firewall

### Import errors
```bash
# Make sure you're in the project root
cd /path/to/Arcturus

# Reinstall dependencies
uv sync
# or
pip install -e .
```

### Neo4j connection failed
- Ensure Neo4j is running: `docker ps | grep neo4j`
- Check auth matches: `NEO4J_AUTH=neo4j/arcturus-neo4j` in docker-compose → `NEO4J_PASSWORD=arcturus-neo4j`
- Test Bolt: `bolt://localhost:7687` (not http)
- If `neo4j` Python package missing: `uv sync` or `pip install neo4j`

### Entity extraction fails (Ollama)
- Ollama must be running for entity extraction
- Check `entity_extraction` model in `config/settings.json` or skill config
- Run `ollama list` to see available models

## Migration Orchestration: FAISS → Qdrant → Neo4j

**Recommended path:** Use the unified migration orchestrator `scripts/migrate_all_memories.py`. It will:

- Migrate FAISS **Remme memories** → Qdrant (`arcturus_memories`) via `migrate_faiss_to_qdrant.py`
- Migrate **RAG FAISS index** → Qdrant (`arcturus_rag_chunks`) via `migrate_rag_faiss_to_qdrant.py`
- Backfill Qdrant **memories → Neo4j** via `migrate_memories_to_neo4j.py`

### Docker mode (default)

For local Docker (Qdrant + Neo4j via `docker-compose`):

```bash
# From project root
uv run python scripts/migrate_all_memories.py
# or explicitly
uv run python scripts/migrate_all_memories.py docker
```

This will:

- Run `docker-compose up -d` to ensure Qdrant and Neo4j are up
- Offer to append sensible Qdrant/Neo4j defaults to `.env` (it will **ask before writing** and never overwrite existing values)
- Run the three migrations in order

### Cloud mode

If you're using **Qdrant Cloud** and **Neo4j Aura (or other managed Neo4j)**:

1. Configure your `.env`:

   ```bash
   # Qdrant Cloud
   QDRANT_URL=https://your-cluster-id.region.cloud-provider.cloud.qdrant.io
   QDRANT_API_KEY=your-api-key-here
   VECTOR_STORE_PROVIDER=qdrant
   RAG_VECTOR_STORE_PROVIDER=qdrant

   # Neo4j (Aura or self-hosted)
   NEO4J_ENABLED=true
   NEO4J_URI=neo4j+s://your-neo4j-instance.databases.neo4j.io  # or bolt://... for self-hosted
   NEO4J_USER=your-neo4j-username
   NEO4J_PASSWORD=your-neo4j-password
   ```

2. Run:

   ```bash
   uv run python scripts/migrate_all_memories.py cloud
   ```

The script will remind you about these env vars, wait for you to confirm that `.env` is configured, and then run the same migration sequence as in Docker mode.

### Using individual migration scripts (advanced)

You can still run the underlying scripts directly for fine‑grained control:

#### Remme memories (FAISS → Qdrant)

```bash
# Using .env (recommended for Cloud)
# Ensure .env has: QDRANT_URL, QDRANT_API_KEY, VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_faiss_to_qdrant.py

# Or export explicitly
export QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
export QDRANT_API_KEY=your-api-key
export VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_faiss_to_qdrant.py
```

Reads from `memory/remme_index/`, writes to `arcturus_memories` collection.

#### RAG document chunks (FAISS → Qdrant)

```bash
# Using .env (recommended for Cloud)
# Ensure .env has: QDRANT_URL, QDRANT_API_KEY, RAG_VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_rag_faiss_to_qdrant.py

# Or export explicitly
export QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
export QDRANT_API_KEY=your-api-key
export RAG_VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_rag_faiss_to_qdrant.py
```

Reads from `mcp_servers/faiss_index/` (metadata.json + index.bin), writes to `arcturus_rag_chunks`. Keeps `metadata.json` for BM25 hybrid search.

---

## Neo4j Knowledge Graph (Phase 2/3)

To enable entity extraction, graph storage, and dual-path retrieval:

### Neo4j via Docker

Neo4j is defined in `docker-compose.yml`. Start it:

```bash
docker-compose up -d neo4j
```

Default auth: `neo4j/arcturus-neo4j` (see `NEO4J_AUTH` in docker-compose).

**Verify:**
- Browser UI: http://localhost:7474
- Bolt: `bolt://localhost:7687`

### Configure .env for Neo4j

Add to `.env`:

```
NEO4J_ENABLED=true
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=arcturus-neo4j
```

These must match your Neo4j instance (Docker uses `NEO4J_AUTH=neo4j/arcturus-neo4j`).

### Backfill Memories to Neo4j

If you already have memories in Qdrant, backfill them into Neo4j:

```bash
# Prerequisites: Qdrant running, NEO4J_* in .env, Ollama running
export VECTOR_STORE_PROVIDER=qdrant  # or set in .env
uv run python scripts/migrate_memories_to_neo4j.py
```

Options:
- `--dry-run` — Extract entities only; skip Neo4j and Qdrant updates
- `--limit N` — Process at most N memories (0 = all)
- `-v` — Verbose (raw LLM response for first memory)

### New Memories

When `NEO4J_ENABLED=true` and you add memories via Qdrant (`VECTOR_STORE_PROVIDER=qdrant`), `qdrant_store.add()` automatically:
1. Extracts entities via LLM (Ollama)
2. Writes User, Memory, Session, Entity nodes and relationships to Neo4j
3. Updates Qdrant payload with `entity_ids` and `entity_labels`

**Ollama** must be running for entity extraction (uses `entity_extraction` model from config).

### Neo4j Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `NEO4J_ENABLED` | Enable knowledge graph | `false` |
| `NEO4J_URI` | Neo4j Bolt URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | (required when enabled) |

---

## Next Steps

Once Qdrant (and optionally Neo4j) is running and tests pass:

1. **Remme**: `memory/vector_store.py`, `memory/backends/qdrant_store.py`
2. **RAG**: `memory/rag_store.py`, `memory/rag_backends/qdrant_rag_store.py`
3. **Knowledge graph**: `memory/knowledge_graph.py`, `memory/entity_extractor.py`, `memory/memory_retriever.py`
4. **Config**: `config/qdrant_config.yaml` — collection specs (including `session_id`, `entity_labels`)
5. **Write integration tests**: Test with real embeddings and entity extraction

## Useful Commands

```bash
# View Qdrant logs
docker logs -f arcturus-qdrant

# Stop Qdrant
docker-compose down

# Stop and remove data (careful!)
docker-compose down -v

# Restart Qdrant
docker-compose restart qdrant
```

## Data Persistence

Qdrant data is stored in `./data/qdrant_storage/`. This directory is:
- ✅ Persisted across container restarts
- ✅ Not committed to git (should be in .gitignore)
- ✅ Can be backed up or deleted as needed

## Production Considerations

For production deployment:
- Use Qdrant Cloud or self-hosted Qdrant cluster
- Set up authentication (API keys)
- Configure proper backup and monitoring
- Use environment variables for connection strings

Example:
```python
# Remme memories
from memory.vector_store import get_vector_store
store = get_vector_store(provider="qdrant")  # arcturus_memories

# RAG document chunks
from memory.rag_store import get_rag_vector_store
rag_store = get_rag_vector_store(provider="qdrant")  # arcturus_rag_chunks
```

## Environment Variables Summary

| Variable | Purpose | Default |
|----------|---------|---------|
| `QDRANT_URL` | Qdrant server URL | `http://localhost:6333` |
| `QDRANT_API_KEY` | API key (Cloud) | `null` |
| `VECTOR_STORE_PROVIDER` | Remme memories backend | `faiss` |
| `RAG_VECTOR_STORE_PROVIDER` | RAG chunks backend | `faiss` |
| `NEO4J_ENABLED` | Enable Neo4j knowledge graph | `false` |
| `NEO4J_URI` | Neo4j Bolt URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | (required when `NEO4J_ENABLED=true`) |

---

**Ready to proceed?** Once Qdrant is running and tests pass, run the migration scripts to move existing FAISS data to Qdrant. Optionally enable Neo4j and backfill memories for dual-path retrieval. 🚀

