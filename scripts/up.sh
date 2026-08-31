#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! docker info >/dev/null 2>&1; then
  echo "Docker daemon is not running. Start Docker Desktop, then re-run this script."
  exit 1
fi

run() {
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose "$@"
  elif docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    echo "Docker Compose is not installed."
    echo "Install with: brew install docker-compose"
    exit 1
  fi
}

run up -d postgres phoenix openwebui
echo
echo "Postgres  http://localhost:5432"
echo "Phoenix   http://localhost:6006"
echo "OpenWebUI http://localhost:3000"
echo
echo "Next:"
echo "  ollama pull llama3.2:1b && ollama pull nomic-embed-text"
echo "  uv run python scripts/ingest.py"
echo "  uv run python -m uvicorn docsearch.main:app --host 0.0.0.0 --port 8000 --reload"
