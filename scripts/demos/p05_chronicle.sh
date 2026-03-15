#!/usr/bin/env bash
# Project 5: Chronicle — Replay Reliability Demo
# End-to-end: checkpoint creation, load, restore, rewind.

set -euo pipefail

echo "📼 [P05 Chronicle] Replay Reliability Demo..."

# 1. Checkpoint create and load
echo "📦 Creating checkpoint and verifying load..."
pytest tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py::test_12_create_checkpoint_persists_and_loads -q

# 2. Restore from checkpoint
echo "🔄 Restoring from checkpoint (node count, state)..."
pytest tests/acceptance/p05_chronicle/test_rewind_restores_exact_state.py::test_13_restore_from_checkpoint_returns_correct_node_count -q

# 3. Rewind roundtrip
echo "⏪ Rewind roundtrip: create → load → restore..."
pytest tests/integration/test_chronicle_git_checkpoint_alignment.py::test_07_checkpoint_and_rewind_roundtrip -q

# 4. Rewind to latest
echo "📌 Rewind to latest checkpoint selection..."
pytest tests/integration/test_chronicle_git_checkpoint_alignment.py::test_08_rewind_to_latest_selects_newest_checkpoint -q

echo "✅ [P05 Chronicle] Replay reliability demo completed successfully."
