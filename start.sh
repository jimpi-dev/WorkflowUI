#!/usr/bin/env bash
# WorkflowUI — (Re)start backend and frontend (Linux/macOS)
# Run from WorkflowUI root: ./start.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
BACKEND_PORT=8000
FRONTEND_PORT=5173

# Kill existing processes on ports
for port in $BACKEND_PORT $FRONTEND_PORT; do
  pid=$(lsof -ti :$port 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "Stopping process on port $port (PID $pid)..."
    kill -9 $pid 2>/dev/null || true
  fi
done
sleep 1

echo "Starting backend (FastAPI) on port $BACKEND_PORT..."
(cd "$ROOT_DIR/backend" && uvicorn main:app --reload --port $BACKEND_PORT) &
BACKEND_PID=$!
sleep 2

echo "Starting frontend (SvelteKit) on port $FRONTEND_PORT..."
echo ""
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop."
trap "kill $BACKEND_PID 2>/dev/null" EXIT
(cd "$ROOT_DIR/frontend" && npm run dev)
