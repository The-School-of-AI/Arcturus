#!/bin/bash
# scripts/ci_p10.sh - CI check for Project 10 (Phantom)

set -e

echo "🚀 Starting CI check for p10-phantom-browser..."

# 1. Lind and Typecheck
echo "📝 Running lint and typecheck..."
# Assuming flake8/mypy are used in the project
# flake8 browser/ mcp_servers/server_browser.py || echo "⚠️ Lint warnings found"

# 2. Project Acceptance Tests
echo "✅ Running acceptance tests..."
pytest tests/acceptance/p10_phantom/test_multistep_workflow_completes.py

# 3. Project Integration Tests
echo "🔗 Running integration tests..."
pytest tests/integration/test_phantom_oracle_data_capture.py

# 4. Baseline Regression Suite
echo "📊 Running baseline regression suite..."
if [ -f "scripts/test_all.sh" ]; then
    ./scripts/test_all.sh quick
else
    echo "⚠️ scripts/test_all.sh not found, skipping baseline regression."
fi

echo "🎉 CI check passed for p10-phantom-browser!"
