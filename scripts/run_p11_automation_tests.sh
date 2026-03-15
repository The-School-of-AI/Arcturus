#!/usr/bin/env bash
# scripts/run_p11_automation_tests.sh
# Runs the P11 Mnemo automation test suite against isolated database instances.

set -e

echo "============================================================"
echo "Starting P11 Mnemo Automation Test Suite"
echo "============================================================"

# Ensure we are in the project root
cd "$(dirname "$0")/.."

# 1. Start the isolated test databases
echo "[1/4] Starting isolated Qdrant and Neo4j test instances..."
docker compose -f docker-compose.tests.yml up -d

# Give containers a few seconds to initialize
echo "[2/4] Waiting for databases to become healthy..."
sleep 15 # Wait a bit to ensure they are up. Using healthchecks in docker-compose.tests.yml is better if we polled, but sleep 15 usually suffices.

# 2. Setup environment variables for testing
export VECTOR_STORE_PROVIDER=qdrant
export RAG_VECTOR_STORE_PROVIDER=qdrant
export EPISODIC_STORE_PROVIDER=qdrant
export NEO4J_ENABLED=true
export MNEMO_ENABLED=true
export QDRANT_URL=http://localhost:6335
export NEO4J_URI=bolt://localhost:7688
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=test-password

echo "[3/4] Running tests with ASYNC_KG_INGEST=false (Synchronous Mode)..."
export ASYNC_KG_INGEST=false
uv run pytest -m "p11_automation" -v --tb=short

echo "[4/4] Running tests with ASYNC_KG_INGEST=true (Asynchronous Mode)..."
export ASYNC_KG_INGEST=true
uv run pytest -m "p11_automation" -v --tb=short

echo "============================================================"
echo "All test suites completed successfully!"
echo "Tearing down isolated databases..."
echo "============================================================"
docker compose -f docker-compose.tests.yml down -v
