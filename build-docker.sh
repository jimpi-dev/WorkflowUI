#!/usr/bin/env sh
# Build WorkflowUI Docker image using the version from frontend/package.json.
# Usage: run from app root or anywhere; script lives in app root (one level up from docker/).
# Set DOCKER_IMAGE_NAME to match Docker Hub (e.g. myorg/workflowui); default: workflowui

set -e
APP_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_ROOT"

# Read version from frontend (UI) package.json
VERSION="$(node -p "require('./frontend/package.json').version")"
IMAGE_NAME="${DOCKER_IMAGE_NAME:-workflowui}"
TAG="${IMAGE_NAME}:${VERSION}"

echo "Building Docker image: $TAG (from $APP_ROOT)"
docker build -f docker/Dockerfile -t "$TAG" .
echo "Built $TAG"
