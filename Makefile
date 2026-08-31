.PHONY: help setup up down models sync ingest api eval test openapi

help:
	@echo "Document Search Platform"
	@echo "  make setup    Install Python 3.13 + project deps (uv)"
	@echo "  make up       Start Postgres, Phoenix, OpenWebUI"
	@echo "  make models   Pull Ollama LLM and embedding models"
	@echo "  make ingest   Parse sample PDFs and index into pgvector"
	@echo "  make api      Run the FastAPI backend"
	@echo "  make eval     Run RAGAs evaluation"
	@echo "  make test     Run unit tests"
	@echo "  make down     Stop docker compose services"

setup:
	uv python pin 3.13
	uv sync --all-extras
	cp -n .env.example .env || true
	uv run python scripts/generate_sample_pdfs.py

up:
	bash scripts/up.sh

down:
	bash scripts/down.sh

models:
	ollama pull llama3.2
	ollama pull nomic-embed-text

sync:
	uv sync --all-extras

ingest:
	uv run python scripts/ingest.py

api:
	uv run python -m uvicorn docsearch.main:app --host 0.0.0.0 --port 8000 --reload

eval:
	uv run python scripts/evaluate.py

test:
	uv run pytest -q

openapi:
	uv run python -c "from docsearch.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > doc/openapi.json
