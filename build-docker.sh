#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

IMAGE_NAME="${IMAGE_NAME:-nutriproof:latest}"
BUILD_CONTEXT="${BUILD_CONTEXT:-.}"
DOCKERFILE="${DOCKERFILE:-Dockerfile}"

echo "Building Docker image: $IMAGE_NAME"

docker image rm -f "$IMAGE_NAME" >/dev/null 2>&1 || true

docker build -t "$IMAGE_NAME" -f "$DOCKERFILE" "$BUILD_CONTEXT"

echo "Image built successfully: $IMAGE_NAME"
