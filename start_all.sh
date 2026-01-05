#!/bin/bash

# Kill any existing api.py process
pkill -f "api.py"

# Function to handle script exit
cleanup() {
  echo "Stopping all services..."
  kill $(jobs -p) 2>/dev/null
}

trap cleanup EXIT

echo "🚀 Starting Arcturus Unified System..."

# Start Backend
echo "📡 Starting Backend (api.py)..."
uv run api.py &
BACKEND_PID=$!

# Wait a moment for backend to initialize
sleep 2

# Start Frontend
echo "💻 Starting Frontend (platform-frontend)..."
cd platform-frontend
npm run dev &
FRONTEND_PID=$!

# Wait for both processes
wait $BACKEND_PID $FRONTEND_PID
