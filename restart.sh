#!/bin/bash
# Restart script for ERAV2 Platform
# NOTE: This script has known issues with MCP process cleanup.
# It's recommended to manually restart by pressing Ctrl+C and running npm run dev:all

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[Restart] ⚠️  WARNING: Auto-restart may cause process cleanup errors"
echo "[Restart] For cleanest restart, manually use: Ctrl+C then 'npm run dev:all'"
echo ""
echo "[Restart] Attempting graceful shutdown..."

# Send SIGTERM (graceful) instead of hard kill
pkill -TERM -f "uvicorn" 2>/dev/null
sleep 3

# Only kill vite after uvicorn has stopped
pkill -TERM -f "vite" 2>/dev/null
sleep 2

echo "[Restart] Starting services..."

# Change to the platform-frontend directory and restart
cd "$SCRIPT_DIR/platform-frontend"
nohup npm run dev:all > "$SCRIPT_DIR/server.log" 2>&1 &

echo "[Restart] Services starting in background. Check server.log for output"
echo "[Restart] PID: $!"
