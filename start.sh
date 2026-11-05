#!/usr/bin/env bash
# WorkflowUI — (Re)start backend and frontend (Linux/macOS)
# Run from WorkflowUI root: ./start.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
# shellcheck source=scripts/dev-common.sh
. "$ROOT_DIR/scripts/dev-common.sh"

BACKEND_PORT=8000
FRONTEND_PORT=5173
WORKFLOWUI_CORS_ORIGINS="http://localhost:${FRONTEND_PORT},http://127.0.0.1:${FRONTEND_PORT}"

VENV_PY="$(workflowui_require_venv)"
workflowui_require_node

for port in $BACKEND_PORT $FRONTEND_PORT; do
  workflowui_stop_port "$port"
done
sleep 1

echo "Starting backend (FastAPI) on port $BACKEND_PORT (APP_ENV=production)..."
(
  cd "$ROOT_DIR/backend"
  workflowui_run \
    APP_ENV=production \
    WORKFLOWUI_CORS_ORIGINS="$WORKFLOWUI_CORS_ORIGINS" \
    PYTHONUNBUFFERED=1 \
    "$VENV_PY" -m uvicorn main:app --reload --port "$BACKEND_PORT"
) &
BACKEND_PID=$!
sleep 2

echo "Starting frontend (SvelteKit) on port $FRONTEND_PORT..."
echo ""
echo "Backend:  http://localhost:$BACKEND_PORT"
echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Press Ctrl+C to stop."
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT
(
  cd "$ROOT_DIR/frontend"
  BACKEND_URL="http://localhost:${BACKEND_PORT}" \
  FRONTEND_PORT="$FRONTEND_PORT" \
  PORT="$FRONTEND_PORT" \
  workflowui_frontend_dev "$FRONTEND_PORT"
)
