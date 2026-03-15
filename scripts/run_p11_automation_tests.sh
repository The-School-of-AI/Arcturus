#!/usr/bin/env bash
# P11 Mnemo automation test suite runner.
# These tests are NOT run by default. Execute explicitly via this script.
# Mocks all LLM calls; requires Qdrant + Neo4j for full integration.

set -e
cd "$(dirname "$0")/.."

echo "=== P11 Mnemo Automation Tests ==="
echo "ASYNC_KG_INGEST=${ASYNC_KG_INGEST:-false}"
echo ""

uv run pytest -m p11_automation -v --tb=short "$@"
