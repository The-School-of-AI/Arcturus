# Project 11 Setup Guide: Qdrant (Cloud or Local)

This guide will help you set up Qdrant (cloud or local via Docker) for Phase 1 of Project 11 (Mnemo).

**Two vector stores** use Qdrant:
- **Remme memories** (`arcturus_memories`) — user preferences, facts, identity
- **RAG chunks** (`arcturus_rag_chunks`) — document chunks, conversation history

**Note**: You don't need to do these steps if you don't want to move to Qdrant. The default config uses FAISS (legacy) for both.

## Prerequisites

- Python 3.11+
- Project dependencies installed (`uv sync` or `pip install -e .`)
- For Option 2 (Docker): Docker and Docker Compose installed

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

## Migration: FAISS → Qdrant

**Important for Qdrant Cloud:** The migration scripts load `.env` automatically. Ensure your `.env` has:

```
QDRANT_URL=https://your-cluster-id.region.cloud-provider.cloud.qdrant.io
QDRANT_API_KEY=your-api-key-here
```

Without these, migrations will use the default `http://localhost:6333` (local Docker).

### Remme memories

```bash
# Option 1: Use .env (recommended for Cloud)
# Add to .env: QDRANT_URL, QDRANT_API_KEY, VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_faiss_to_qdrant.py

# Option 2: Export explicitly
export QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
export QDRANT_API_KEY=your-api-key
export VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_faiss_to_qdrant.py
```

Reads from `memory/remme_index/`, writes to `arcturus_memories` collection.

### RAG document chunks

```bash
# Option 1: Use .env (recommended for Cloud)
# Add to .env: QDRANT_URL, QDRANT_API_KEY, RAG_VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_rag_faiss_to_qdrant.py

# Option 2: Export explicitly
export QDRANT_URL=https://your-cluster.region.cloud.qdrant.io
export QDRANT_API_KEY=your-api-key
export RAG_VECTOR_STORE_PROVIDER=qdrant
uv run python scripts/migrate_rag_faiss_to_qdrant.py
```

Reads from `mcp_servers/faiss_index/` (metadata.json + index.bin), writes to `arcturus_rag_chunks`. Keeps `metadata.json` for BM25 hybrid search.

## Next Steps

Once Qdrant is running and tests pass:

1. **Remme**: `memory/vector_store.py`, `memory/backends/qdrant_store.py`
2. **RAG**: `memory/rag_store.py`, `memory/rag_backends/qdrant_rag_store.py`
3. **Config**: `config/qdrant_config.yaml` — collection specs
4. **Write integration tests**: Test with real embeddings from your models

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

---

**Ready to proceed?** Once Qdrant is running and tests pass, run the migration scripts to move existing FAISS data to Qdrant! 🚀

