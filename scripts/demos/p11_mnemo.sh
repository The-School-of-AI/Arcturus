#!/usr/bin/env bash
# P11 Mnemo — Real-Time Memory & Knowledge Graph Demo
#
# Runs acceptance + integration gates, then (optional) E2E flow when
# backend + Qdrant + Neo4j are available.
#
# Prerequisites (for full E2E):
#   - .env with VECTOR_STORE_PROVIDER=qdrant, NEO4J_ENABLED=true, NEO4J_URI/USER/PASSWORD
#   - Qdrant + Neo4j up (e.g. docker-compose up -d qdrant neo4j)
#   - Backend running (uv run uvicorn api:app --host 0.0.0.0 --port 8000)
#
# Usage:
#   ./scripts/demos/p11_mnemo.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║     P11 Mnemo — Memory & Knowledge Graph Demo            ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Acceptance (charter, delivery README, demo script contract) ───
echo "▶ Running P11 acceptance tests (charter, delivery, demo contract)..."
uv run python -m pytest tests/acceptance/p11_mnemo/test_memory_influences_planner_output.py -v --tb=short -q

# ── Step 2: Integration (CI wiring, file contracts) ─────────────────────────
echo ""
echo "▶ Running P11 integration tests (CI gate, baseline script)..."
uv run python -m pytest tests/integration/test_mnemo_oracle_cross_project_retrieval.py -v --tb=short -q

echo ""
echo "✅ [P11 Mnemo] Acceptance + integration gates passed."
echo ""
echo "Optional — full E2E (memory add → entity extraction → retrieval):"
echo "  1. Start services: docker-compose up -d qdrant neo4j"
echo "  2. Backend: uv run uvicorn api:app --host 0.0.0.0 --port 8000"
echo "  3. Run: uv run pytest tests/automation/p11_mnemo/task_group_1_guest_single_space/test_sequential_scenario.py -v"
echo "  See CAPSTONE/project_charters/P11_DELIVERY_README.md §10 Demo Steps for Qdrant/Neo4j setup."
echo ""
