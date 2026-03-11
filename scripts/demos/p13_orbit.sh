#!/usr/bin/env bash
# Project 13: Orbit - Week 1 Demo Flow
# This script simulates a mobile node registration and message exchange.

set -euo pipefail

echo "🚀 [P13 Orbit] Starting Week 1 Demo Flow..."

# 1. Simulate Node Registration
echo "📡 registering node: mobile-node-001 (iOS)..."
# In a real environment, this would be a curl call to a registry endpoint
# For the demo, we validate the protocol logic via the acceptance suite.
uv run pytest tests/acceptance/p13_orbit/test_mobile_sync_and_action.py::test_03_node_registration_protocol -q

# 2. Simulate Inbound Message from Mobile
echo "📥 Simulating inbound message: 'Hello from iPhone'..."
# This verifies the Nexus router can handle the mobile channel
uv run pytest tests/acceptance/p13_orbit/test_mobile_sync_and_action.py::test_10_happy_path_e2e_serialization -q

# 3. Verify Session Sync / Polling
echo "🔄 Verifying session polling for response..."
uv run pytest tests/acceptance/p13_orbit/test_mobile_sync_and_action.py::test_11_mobile_adapter_outbox -q

echo "✅ [P13 Orbit] Demo completed successfully. Mobile shell and sync contracts are stable."
