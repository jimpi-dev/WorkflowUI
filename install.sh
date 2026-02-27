#!/usr/bin/env bash
# WorkflowUI — One-time setup: install backend and frontend dependencies
# Run from WorkflowUI root: ./install.sh

set -e
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
cd "$ROOT_DIR"

echo "WorkflowUI: installing dependencies..."
echo ""

echo "Backend (Python): pip install -r backend/requirements.txt"
(cd backend && pip install -r requirements.txt)

echo ""
echo "Frontend (Node): npm install in frontend/"
(cd frontend && npm install)

echo ""
echo "Done. Start the app with: ./start.sh"
echo "Optional: copy .env.example to .env and set COMFYUI_URL if needed."
