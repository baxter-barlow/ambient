#!/bin/bash
# Ambient SDK Run Script
# Starts the full stack: API server + Dashboard

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
API_HOST="${AMBIENT_API_HOST:-0.0.0.0}"
API_PORT="${AMBIENT_API_PORT:-8000}"
DASHBOARD_PORT="${AMBIENT_DASHBOARD_PORT:-5173}"
MODE="${1:-dev}"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $API_PID 2>/dev/null || true
    kill $DASHBOARD_PID 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "=== Ambient Dashboard ==="
echo "Mode: $MODE"
echo ""

cd "$PROJECT_ROOT"

if [ "$MODE" = "prod" ]; then
    # Production mode: serve built dashboard from API
    echo "Starting API server (production mode)..."
    echo "Dashboard: http://localhost:$API_PORT"
    echo ""
    python -m ambient.api --host "$API_HOST" --port "$API_PORT"
else
    # Development mode: separate API and Vite dev server
    echo "Starting API server on port $API_PORT..."
    python -m ambient.api --host "$API_HOST" --port "$API_PORT" &
    API_PID=$!
    sleep 2

    if ! kill -0 $API_PID 2>/dev/null; then
        echo "Error: API server failed to start"
        exit 1
    fi

    echo "Starting dashboard dev server on port $DASHBOARD_PORT..."
    cd "$PROJECT_ROOT/dashboard"
    npm run dev &
    DASHBOARD_PID=$!
    sleep 3

    echo ""
    echo "=== Ready ==="
    echo "Dashboard: http://localhost:$DASHBOARD_PORT"
    echo "API:       http://localhost:$API_PORT"
    echo ""
    echo "Press Ctrl+C to stop"
    echo ""

    # Wait for either process to exit
    wait $API_PID $DASHBOARD_PID
fi
