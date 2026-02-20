# Project 11 Setup Guide: Qdrant Local Development

This guide will help you set up Qdrant locally using Docker for Phase 1 of Project 11.

## Prerequisites

- Docker and Docker Compose installed
- Python 3.11+
- Project dependencies installed (`uv sync` or `pip install -e .`)

## Step 1: Start Qdrant with Docker

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

## Step 2: Check Qdrant Health

Open your browser and visit:
- **REST API**: http://localhost:6333/dashboard
- **Health Check**: http://localhost:6333/health

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

1. Open http://localhost:6333/dashboard
2. You should see the `arcturus_memories` collection
3. Check the points count (should match test memories added)

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

## Next Steps

Once Qdrant is running and tests pass:

1. **Review the vector store implementation**: `memory/vector_store.py`
2. **Understand the API**: Compare with `remme/store.py` (FAISS version)
3. **Plan migration**: How to move existing FAISS data to Qdrant
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
store = QdrantVectorStore(
    url=os.getenv("QDRANT_URL", "http://localhost:6333"),
    api_key=os.getenv("QDRANT_API_KEY"),
)
```

---

**Ready to proceed?** Once Qdrant is running and tests pass, you can start building the migration from FAISS to Qdrant! 🚀

