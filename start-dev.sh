#!/usr/bin/env bash
# WorkflowUI — (Re)start backend and frontend (developer mode)
# Run from WorkflowUI root: ./start-dev.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/dev-common.sh
. "$ROOT_DIR/scripts/dev-common.sh"

BACKEND_PORT=8000
FRONTEND_PORT=5173
WORKFLOWUI_CORS_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"

VENV_PY="$(workflowui_require_venv)"
workflowui_require_node

echo "WorkflowUI (dev): stopping any existing backend (port $BACKEND_PORT) and frontend (port $FRONTEND_PORT) ..."
for port in $BACKEND_PORT $FRONTEND_PORT; do
  workflowui_stop_port "$port"
done
sleep 1

echo "Starting backend (FastAPI) on port $BACKEND_PORT with APP_ENV=development ..."
(
  cd "$ROOT_DIR/backend"
  workflowui_run \
    APP_ENV=development \
    WORKFLOWUI_CORS_ORIGINS="$WORKFLOWUI_CORS_ORIGINS" \
    PYTHONUNBUFFERED=1 \
    "$VENV_PY" -m uvicorn main:app --reload --port "$BACKEND_PORT"
) &
BACKEND_PID=$!
sleep 2

VITE_CACHE_DIR="$ROOT_DIR/frontend/node_modules/.vite"
if [ -d "$VITE_CACHE_DIR" ]; then
  echo "Clearing frontend Vite cache (node_modules/.vite) ..."
  rm -rf "$VITE_CACHE_DIR" || echo "Warning: could not fully clear Vite cache at $VITE_CACHE_DIR"
fi

echo "Starting frontend (SvelteKit) on port $FRONTEND_PORT..."
echo ""
echo "Backend (dev):  http://localhost:$BACKEND_PORT"
echo "Frontend:       http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop."
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT
(
  cd "$ROOT_DIR/frontend"
  BACKEND_URL="http://localhost:${BACKEND_PORT}" \
  FRONTEND_PORT="$FRONTEND_PORT" \
  PORT="$FRONTEND_PORT" \
  workflowui_frontend_dev "$FRONTEND_PORT"
)
