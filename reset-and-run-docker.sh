#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f .env ]; then
  set -a
  source .env
  set +a
fi

printf '\n==> Stopping existing containers\n'
docker compose down --remove-orphans || true

docker rm -f nutriproof 2>/dev/null || true

docker image rm -f nutriproof:latest 2>/dev/null || true

printf '\n==> Rebuilding Docker image\n'
docker compose build --no-cache

printf '\n==> Starting container\n'
docker compose up -d

printf '\n==> Checking Tesseract language data\n'
docker exec -it nutriproof ls /usr/share/tesseract-ocr/5/tessdata | grep fra || true

echo "\nContainer started. Open: http://localhost:${PORT:-8080}"
