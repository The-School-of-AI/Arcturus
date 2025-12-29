#!/bin/bash
# Restart script for ERAV2 Platform
# Called by the /settings/restart API endpoint

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "[Restart] Stopping current processes..."

# Find and kill the current npm run dev:all process
# This pattern matches the parent npm process running dev:all
pkill -f "npm run dev:all" 2>/dev/null
pkill -f "vite" 2>/dev/null
pkill -f "uvicorn" 2>/dev/null

# Wait for processes to terminate
sleep 2

echo "[Restart] Starting services..."

# Change to the platform-frontend directory and restart
cd "$SCRIPT_DIR/platform-frontend"
nohup npm run dev:all > /dev/null 2>&1 &

echo "[Restart] Services restarting in background. PID: $!"
echo "[Restart] Complete."
