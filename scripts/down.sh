#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if docker compose version >/dev/null 2>&1; then
  docker compose down
elif command -v docker-compose >/dev/null 2>&1; then
  docker-compose down
else
  docker rm -f docsearch-postgres docsearch-phoenix docsearch-openwebui docsearch-ollama 2>/dev/null || true
fi
