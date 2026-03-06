#!/usr/bin/env bash
# P01 Nexus — Live Demo Startup Script
#
# Records a live video of the Arcturus Nexus gateway handling messages across
# WebChat (Electron UI), Telegram, and Slack in real time.
#
# Prerequisites:
#   - .env populated with TELEGRAM_TOKEN, SLACK_BOT_TOKEN, SLACK_SIGNING_SECRET
#   - uv installed (backend)
#   - npm/node installed (frontend)
#   - ngrok installed (for Slack Events webhook, optional for Telegram)
#
# Usage:
#   ./scripts/demos/p01_nexus.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║        P01 Nexus — Live Multi-Channel Demo               ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""

# ── Step 1: Confirm .env tokens ─────────────────────────────────────────────
echo "▶ Checking .env tokens..."
source "$ROOT/.env" 2>/dev/null || true

if [[ -z "${TELEGRAM_TOKEN:-}" ]]; then
  echo "  ⚠️  TELEGRAM_TOKEN not set — Telegram channel will not respond."
else
  echo "  ✅ TELEGRAM_TOKEN found"
fi

if [[ -z "${SLACK_BOT_TOKEN:-}" ]]; then
  echo "  ⚠️  SLACK_BOT_TOKEN not set — Slack channel will not respond."
else
  echo "  ✅ SLACK_BOT_TOKEN found"
fi

echo ""

# ── Step 2: Start backend ────────────────────────────────────────────────────
echo "▶ Starting FastAPI backend on :8000 ..."
echo "  Run in a separate terminal:"
echo ""
echo "    uv run uvicorn api:app --host 0.0.0.0 --port 8000 --reload"
echo ""

# ── Step 3: Start Electron UI ────────────────────────────────────────────────
echo "▶ Starting Electron + Vite frontend..."
echo "  Run in a separate terminal:"
echo ""
echo "    cd platform-frontend && npm run electron:dev:all"
echo ""
echo "  Then open the 'AI Chat' card in the Electron window to use WebChat."
echo ""

# ── Step 4: Slack ngrok tunnel ───────────────────────────────────────────────
echo "▶ Slack — ngrok tunnel (for incoming events):"
echo "  Run in a separate terminal:"
echo ""
echo "    ngrok http 8000"
echo ""
echo "  Then paste the HTTPS URL into:"
echo "    Slack App → Event Subscriptions → Request URL:"
echo "    https://<your-ngrok-id>.ngrok-free.app/api/nexus/slack/events"
echo ""

# ── Step 5: Telegram ─────────────────────────────────────────────────────────
echo "▶ Telegram — no setup needed!"
echo "  The bot polls automatically once the backend starts."
echo "  Open the Telegram app and message your bot directly."
echo ""

# ── Step 6: Quick smoke-test (requires running backend) ───────────────────────
echo "▶ Smoke test — WebChat roundtrip (requires backend to be running):"
echo ""
echo "  POST inbound:"
echo "    curl -s -X POST http://localhost:8000/api/nexus/webchat/inbound \\"
echo "      -H 'Content-Type: application/json' \\"
echo "      -d '{\"session_id\":\"demo\",\"sender_id\":\"u1\",\"sender_name\":\"Demo\",\"text\":\"What is 2+2?\"}'"
echo ""
echo "  Then poll for reply (wait ~5-30s for AgentLoop4):"
echo "    curl -s http://localhost:8000/api/nexus/webchat/messages/demo | python3 -m json.tool"
echo ""

# ── Step 7: Run P01 test suite ────────────────────────────────────────────────
echo "▶ Running P01 acceptance + integration tests..."
uv run python -m pytest \
  tests/acceptance/p01_nexus/ \
  tests/integration/test_nexus_session_affinity.py \
  -v --tb=short -q 2>&1 | tail -20

echo ""
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Demo ready!  Start backend + Electron, then send msgs   ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo ""
