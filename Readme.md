## Run Services

`make setup`, 
`make up`, 
`make models`, 
`make ingest`, 
`make api`
## Questions asked
Added SOP Document in RAG systems and ask questions
<img width="1268" height="611" alt="image" src="https://github.com/user-attachments/assets/9a24b454-b417-4642-afb0-db89621f8176" />

## PDF Data ngetion can be add on
[data/pdfs/Perennial_ SoP Leave Application_Updated (1).pdf](https://github.com/yagnikpokal/agentic-rag-document-intelligence/blob/main/data/pdfs)

## Screenshots data

### 1. Run Ingest
<img width="911" height="205" alt="image" src="https://github.com/user-attachments/assets/3e7547d1-ff67-4171-ad02-89aefbf137c8" />



### 2. Download models
<img width="1888" height="428" alt="image" src="https://github.com/user-attachments/assets/9188b627-ad0c-4b4c-8889-73381f507ca0" />


### 3. Up container
<img width="802" height="366" alt="image" src="https://github.com/user-attachments/assets/0e28b713-9365-468a-9c08-43c5be838464" />


### 4. Up Local services
<img width="1874" height="366" alt="image" src="https://github.com/user-attachments/assets/4cb8b925-f490-41f1-a71d-70fd74682723" />


### 5. Phoenix dashboard
<img width="2560" height="1288" alt="image" src="https://github.com/user-attachments/assets/9c204b44-92b0-4abe-a80f-e5e79d0dea89" />


# Document Search Platform

Agentic RAG backend for **OpenWebUI**. PDFs are preprocessed with **Docling**, indexed into **PostgreSQL + pgvector** through **LlamaIndex**, answered by a **CrewAI** multi-agent pipeline, traced in **Arize Phoenix**, and scored with **RAGAs**. Inference runs on **Ollama**.

This repository is the complete technical assessment deliverable: source, Docker stack, REST API (Swagger/OpenAPI), evaluation harness, and supporting documents under `[doc/](doc/)`.

## Architecture

```
OpenWebUI (chat) ──OpenAI-compatible──► FastAPI
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    │                      │                      │
              CrewAI agents         LlamaIndex RAG          Prompt YAML
           planner/retriever/        hybrid retrieve         prompts/
           synthesizer/critic        + contextual chunks
                    │                      │
                    └──────────► PostgreSQL / pgvector ◄──────────┘
                                           │
                         Ollama (LLM + embeddings)
                         Arize Phoenix (traces)
                         RAGAs (evaluation)
```

Full diagrams, sequence flows, and design choices: [doc/architecture.md](doc/architecture.md)  
API contract: [doc/openapi.yaml](doc/openapi.yaml) · live Swagger at `/docs`  
Presentation: [doc/presentation.html](doc/presentation.html)  
Assessment brief: [requirement.txt](requirement.txt)

## Prerequisites


| Tool                             | Purpose                      |
| -------------------------------- | ---------------------------- |
| Python 3.11–3.13                 | Runtime (`uv` pins 3.13)     |
| [uv](https://docs.astral.sh/uv/) | Package and venv manager     |
| Docker + Compose                 | Postgres, Phoenix, OpenWebUI |
| [Ollama](https://ollama.com)     | Local LLM + embeddings       |


RAM: 16 GB recommended. First model pull is several GB.

On macOS, if Docker or Ollama are missing:

```bash
brew install ollama docker-compose
# Docker engine must be running (Docker Desktop, or: brew install colima && colima start)
brew services start ollama   # or just: ollama serve
```



## Quick start

```bash
cd Assignment

# 1. Python environment
uv python pin 3.13
uv sync --all-extras
cp .env.example .env

# 2. Sample knowledge base (stand-in for the shared Drive PDFs)
uv run python scripts/generate_sample_pdfs.py

# 3. Infrastructure
docker compose up -d postgres phoenix openwebui

# 4. Models (install Ollama from https://ollama.com if `ollama` is missing)
ollama pull llama3.2
ollama pull nomic-embed-text

# 5. Ingest + API
uv run python scripts/ingest.py
uv run uvicorn docsearch.main:app --host 0.0.0.0 --port 8000 --reload
```

If you do not have a native Ollama install:

```bash
docker compose --profile ollama up -d
docker exec -it docsearch-ollama ollama pull llama3.2
docker exec -it docsearch-ollama ollama pull nomic-embed-text
```

Open:


| Surface        | URL                                                                        |
| -------------- | -------------------------------------------------------------------------- |
| OpenWebUI      | [http://localhost:3000](http://localhost:3000)                             |
| Swagger UI     | [http://localhost:8000/docs](http://localhost:8000/docs)                   |
| Phoenix traces | [http://localhost:6006](http://localhost:6006)                             |
| Health         | [http://localhost:8000/api/v1/health](http://localhost:8000/api/v1/health) |


Equivalent Make targets: `make setup`, `make up`, `make models`, `make ingest`, `make api`.

## OpenWebUI integration

Compose already points OpenWebUI at the backend:

```
OPENAI_API_BASE_URL=http://host.docker.internal:8000/v1
OPENAI_API_KEY=docsearch-local
```

In the UI: **Admin → Connections → OpenAI** should list:

- `docsearch-agentic` — CrewAI contextual RAG (planner → retrieve → synthesize → critic)
- `docsearch-direct` — single-shot LlamaIndex RAG

Start a new chat, pick `docsearch-agentic`, and ask:

> How many PTO days do full-time AetherCorp employees receive?

If the models do not appear, add the connection manually with base URL `http://host.docker.internal:8000/v1` (from inside Docker) or `http://localhost:8000/v1` (OpenWebUI running on the host).

## Ingestion workflow

1. **Preprocess** — Docling `DocumentConverter` + `HybridChunker`
2. **Contextualize** (optional) — each chunk gets a one-sentence prefix from `prompts/contextualize.yaml`
3. **Vectorize** — Ollama `nomic-embed-text` (768-d) via LlamaIndex
4. **Index** — pgvector HNSW + optional hybrid (vector + keyword) search

```bash
# Sample corpus
curl -X POST http://localhost:8000/api/v1/ingest

# Upload additional PDFs
curl -X POST http://localhost:8000/api/v1/ingest/upload \
  -F "files=@/path/to/file.pdf"
```

Drop Drive PDFs into `data/pdfs/` and re-run ingest. Existing filenames are upserted.

## Retrieval workflow (agentic RAG)

1. **Query planner** rewrites follow-ups using chat history
2. **Retriever agent** emits 1–3 search strings and LlamaIndex hybrid-retrieves
3. **Synthesizer** answers only from context, with a Sources section
4. **Critic** returns JSON faithfulness; one revision loop if ungrounded

Prompts live in `[prompts/](prompts/)` as YAML. `PROMPT_HOT_RELOAD=true` reloads them on the next request — no code change, no restart required for template edits. List them at `GET /api/v1/prompts`.

## Evaluation

```bash
uv run python scripts/evaluate.py
# or
curl -X POST http://localhost:8000/api/v1/evaluate
```

The harness runs the golden set in `data/eval/golden_set.json` through the agentic pipeline, then RAGAs (`faithfulness`, `answer relevancy`, `context precision`, `context recall`) using Ollama as the judge. Lexical hit-rate and latency percentiles are always reported even if RAGAs cannot bind to a small local model.

## Configuration

Copy `.env.example` to `.env`. Important variables:


| Variable                       | Default                           | Meaning                 |
| ------------------------------ | --------------------------------- | ----------------------- |
| `OLLAMA_BASE_URL`              | `http://localhost:11434`          | LLM provider            |
| `OLLAMA_LLM_MODEL`             | `llama3.2`                        | Chat / agent model      |
| `OLLAMA_EMBED_MODEL`           | `nomic-embed-text`                | Must match `EMBED_DIM`  |
| `EMBED_DIM`                    | `768`                             | pgvector column size    |
| `ENABLE_CONTEXTUAL_ENRICHMENT` | `true`                            | LLM prefixes on ingest  |
| `ENABLE_HYBRID_SEARCH`         | `true`                            | Vector + keyword        |
| `PHOENIX_COLLECTOR_ENDPOINT`   | `http://localhost:6006/v1/traces` | OTLP HTTP               |
| `PROMPTS_DIR`                  | `prompts`                         | External prompt library |


If you change the embedding model, drop the `document_chunks` table (or recreate the Postgres volume) so the vector dimension stays consistent.

## REST API

Interactive docs: [http://localhost:8000/docs](http://localhost:8000/docs)  
Static contract: [doc/openapi.yaml](doc/openapi.yaml)


| Method | Path                    | Use                                              |
| ------ | ----------------------- | ------------------------------------------------ |
| GET    | `/api/v1/health`        | Postgres, Ollama, Phoenix                        |
| POST   | `/api/v1/ingest`        | Index `data/pdfs`                                |
| POST   | `/api/v1/ingest/upload` | Multipart PDF upload                             |
| GET    | `/api/v1/documents`     | Ingestion status                                 |
| POST   | `/api/v1/query`         | Agentic or direct RAG                            |
| POST   | `/api/v1/evaluate`      | RAGAs + latency                                  |
| GET    | `/api/v1/prompts`       | PromptOps catalog                                |
| GET    | `/v1/models`            | OpenWebUI model list                             |
| POST   | `/v1/chat/completions`  | OpenAI-compatible chat (SSE streaming supported) |




## Project layout

```
Assignment/
  docsearch/            FastAPI app, agents, ingestion, evaluation
  prompts/              Externalized YAML prompts (PromptOps)
  data/pdfs/            Knowledge-base PDFs
  data/eval/            Golden questions for RAGAs
  doc/                  Architecture, design, presentation, OpenAPI
  scripts/              Ingest, eval, sample PDF generator
  tests/                Unit tests (no GPU required)
  docker-compose.yml    Postgres, Phoenix, OpenWebUI, optional Ollama
```



## Tests

```bash
uv run pytest -q
```

These cover prompt loading, PDF generation, OpenAPI shape, and critic JSON parsing. End-to-end RAG needs Postgres + Ollama.

## Troubleshooting

`uv sync` **fails on Python 3.14**  
This project requires `<3.14` (Docling / Torch / CrewAI). `uv python pin 3.13` then `uv sync`.

**Health shows Ollama down**  
`ollama serve` in another terminal, or start the compose `ollama` profile. Confirm `curl http://localhost:11434/api/tags`.

**OpenWebUI cannot reach the API**  
The API must listen on the host (`0.0.0.0:8000`). From Docker, the hostname is `host.docker.internal`, not `localhost`.

**pgvector dimension error**  
`EMBED_DIM` must match the embedding model (768 for `nomic-embed-text`). Reset with `docker compose down -v` if you switch models.

**Ingest is slow**  
Set `ENABLE_CONTEXTUAL_ENRICHMENT=false` for a first pass. Docling + embeddings dominate runtime.

**Phoenix shows no traces**  
API starts even when Phoenix is down. Confirm `PHOENIX_ENABLED=true` and open [http://localhost:6006](http://localhost:6006) after a `/api/v1/query` call.

`docker compose` **is unknown / daemon not running**  
This repo uses Compose V2 (`docker compose`) or the `docker-compose` binary. Start the Docker engine first, then `brew install docker-compose` if the plugin is missing. `bash scripts/up.sh` detects which command you have.

`docker: Cannot connect to the Docker daemon`  
Docker Desktop is not running (or not installed). Open Docker Desktop, or install Colima (`brew install colima docker && colima start`).
