# Implementation notes

## Runtime topology

- **API process**: `uvicorn docsearch.main:app` (host network, port 8000).
- **Data plane**: `pgvector/pgvector:pg16` with init script `scripts/init.sql`.
- **Observability**: `arizephoenix/phoenix` on port 6006.
- **Chat UI**: OpenWebUI on port 3000, OpenAI base URL pointed at the API.
- **Inference**: Ollama on 11434. Native install preferred; Compose profile `ollama` as fallback.

## Ingestion details

`docsearch.services.ingestion.parse_pdf` is the only PDF parser. It uses Docling, not PyPDF, to satisfy the mandatory preprocessing tool. Chunk metadata keeps `filename`, `page`, `chunk_index`, and the optional `context_prefix` so citations in the synthesizer can name a source file.

LlamaIndex `PGVectorStore.from_params` creates the embedding table on first use, including HNSW parameters. Hybrid search is on by default (`text_search_config=english`).

## Agent design

Four CrewAI agents map 1:1 to YAML prompts:

1. Query Planner — standalone rewrite (contextual for chat follow-ups)
2. Knowledge Retriever — `search_knowledge_base` tool wrapping LlamaIndex
3. Answer Synthesizer — grounded answer + Sources
4. Groundedness Critic — JSON `{faithful, score, issues, revised_query}`

The orchestrator in `docsearch.services.agents.run_agentic_rag` always performs planner → multi-query retrieve → synthesize → critic in Python, then attempts `Crew.kickoff()` so the assessment's CrewAI requirement is exercised. If CrewAI raises (common with tiny models and tool calling), the sequential result is returned unchanged.

One critic-driven revision round is the default (`AGENTIC_MAX_REVISION_ROUNDS=1`).

## Direct vs agentic

OpenWebUI lists two models so reviewers can A/B:

- `docsearch-agentic` — full pipeline
- `docsearch-direct` — `prompts/direct_rag.yaml` over a single retrieve

## Tracing

`docsearch.observability.setup_tracing` registers Phoenix OTLP export and OpenInference instrumentors. It is deliberately best-effort: an assessment laptop with Phoenix still booting must still serve chat.

## Evaluation

Golden questions in `data/eval/golden_set.json` are derived from the four sample AetherCorp PDFs. Replace that file when the shared Drive corpus is available; the schema is `{question, ground_truth}`.

RAGAs is invoked with Ollama through the OpenAI-compatible endpoint (`/v1`) via `langchain_openai`. Metric class names differ across RAGAs 0.2 and 0.3; the evaluator tries both.

## What to change for the Drive corpus

1. Copy PDFs into `data/pdfs/`
2. `uv run python scripts/ingest.py`
3. Rewrite `data/eval/golden_set.json` with questions a reviewer would actually ask
4. `uv run python scripts/evaluate.py` and paste scores into your presentation

## Known local-model limits

`llama3.2` (3B) is chosen so the stack runs on a laptop CPU. Faithfulness JSON from the critic is less stable than with 8B+ models. For a demo, `llama3.1:8b` in `.env` improves agent tool use at the cost of RAM and time. Embedding model should stay `nomic-embed-text` unless you rebuild the vector table.
