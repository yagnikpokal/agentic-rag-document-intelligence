#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Python env"
uv python pin 3.13
uv sync --all-extras
if [ ! -f .env ]; then
  cp .env.example .env
  echo "wrote .env from .env.example"
fi

echo "==> Sample PDFs"
uv run python scripts/generate_sample_pdfs.py

echo "==> Docker services (Postgres, Phoenix, OpenWebUI)"
if docker info >/dev/null 2>&1; then
  bash scripts/up.sh || true
else
  echo "Docker is not running. Start it, then: bash scripts/up.sh"
fi

if command -v ollama >/dev/null 2>&1; then
  echo "==> Ollama models"
  ollama pull llama3.2
  ollama pull nomic-embed-text
else
  echo "Ollama is not on PATH. Install from https://ollama.com then:"
  echo "  ollama pull llama3.2 && ollama pull nomic-embed-text"
fi

echo
echo "When Postgres + Ollama are up:"
echo "  uv run python scripts/ingest.py"
echo "  uv run uvicorn docsearch.main:app --host 0.0.0.0 --port 8000 --reload"
echo "OpenWebUI: http://localhost:3000   Swagger: http://localhost:8000/docs"
