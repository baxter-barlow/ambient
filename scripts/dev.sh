#!/bin/bash
# Development server script - runs backend and frontend together

set -e

cd "$(dirname "$0")/.."

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting backend on :8000..."
uvicorn ambient.api.main:app --port 8000 --reload &
BACKEND_PID=$!

sleep 2

if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo "Backend failed to start"
    exit 1
fi

echo "Starting frontend on :5173..."
cd dashboard && npm run dev &

wait
