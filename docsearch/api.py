from __future__ import annotations

import json
import logging
import shutil
import time
import uuid
from pathlib import Path

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from docsearch.config import get_settings
from docsearch.prompt_store import get_prompt_store
from docsearch.schemas import (
    ChatCompletionRequest,
    EvalRequest,
    HealthComponent,
    HealthResponse,
    IngestRequest,
    IngestResponse,
    QueryRequest,
    QueryResponse,
)
from docsearch.services.agents import run_agentic_rag, run_direct_rag
from docsearch.services.evaluation import evaluate_pipeline
from docsearch.services import metadata as meta
from docsearch.services.pipeline import ingest_directory, ingest_paths

logger = logging.getLogger(__name__)

router = APIRouter()
openai_router = APIRouter()


def _components() -> list[HealthComponent]:
    settings = get_settings()
    checks: list[HealthComponent] = []

    try:
        engine = meta.get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks.append(HealthComponent(name="postgres", ok=True, detail=settings.postgres_host))
    except Exception as exc:
        checks.append(HealthComponent(name="postgres", ok=False, detail=str(exc)))

    try:
        response = httpx.get(settings.ollama_base_url.rstrip("/") + "/api/tags", timeout=3.0)
        response.raise_for_status()
        models = [m.get("name", "") for m in response.json().get("models", [])]
        checks.append(HealthComponent(name="ollama", ok=True, detail=", ".join(models[:8]) or "reachable"))
    except Exception as exc:
        checks.append(HealthComponent(name="ollama", ok=False, detail=str(exc)))

    try:
        phoenix = httpx.get("http://localhost:6006/healthz", timeout=3.0)
        ok = phoenix.status_code < 500
        checks.append(HealthComponent(name="phoenix", ok=ok, detail=f"status {phoenix.status_code}"))
    except Exception as exc:
        checks.append(HealthComponent(name="phoenix", ok=False, detail=str(exc)))

    return checks


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    components = _components()
    if all(c.ok for c in components):
        status = "ok"
    elif any(c.name == "postgres" and not c.ok for c in components):
        status = "error"
    else:
        status = "degraded"
    return HealthResponse(status=status, components=components)


@router.get("/ready", response_model=HealthResponse)
def ready() -> HealthResponse:
    return health()


@router.get("/prompts")
def list_prompts() -> dict:
    store = get_prompt_store()
    return {
        "prompts": [
            {"name": name, **{k: v for k, v in store.get(name).items() if k != "template"}}
            for name in store.list_prompts()
        ]
    }


@router.get("/prompts/{name}")
def get_prompt(name: str) -> dict:
    try:
        return get_prompt_store().get(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/ingest", response_model=IngestResponse)
def ingest(payload: IngestRequest | None = None) -> IngestResponse:
    payload = payload or IngestRequest()
    settings = get_settings()
    source = Path(payload.source_dir) if payload.source_dir else settings.pdf_dir
    result = ingest_directory(source, enrich=payload.contextual_enrichment)
    return IngestResponse(**result)


@router.post("/ingest/upload", response_model=IngestResponse)
async def ingest_upload(files: list[UploadFile] = File(...)) -> IngestResponse:
    settings = get_settings()
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for upload in files:
        if not upload.filename:
            continue
        dest = settings.upload_dir / Path(upload.filename).name
        with dest.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        saved.append(dest)
    if not saved:
        raise HTTPException(status_code=400, detail="No files uploaded")
    result = ingest_paths(saved, enrich=None)
    return IngestResponse(**result)


@router.get("/documents")
def documents() -> dict:
    return {"documents": meta.list_documents()}


@router.delete("/documents/{filename}")
def delete_document(filename: str) -> dict:
    deleted = meta.delete_document(filename)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": filename}


@router.post("/query", response_model=QueryResponse)
def query(payload: QueryRequest) -> QueryResponse:
    if payload.mode == "direct":
        result = run_direct_rag(payload.question, top_k=payload.top_k)
    else:
        result = run_agentic_rag(
            payload.question,
            chat_history=payload.chat_history,
            top_k=payload.top_k,
        )
    return QueryResponse(
        answer=result.answer,
        rewritten_query=result.rewritten_query,
        citations=result.citations(),
        critic=result.critic,
        latency_ms=result.latency_ms,
        mode=result.mode,
    )


@router.post("/evaluate")
def evaluate(payload: EvalRequest | None = None) -> dict:
    payload = payload or EvalRequest()
    path = Path(payload.dataset_path) if payload.dataset_path else None
    return evaluate_pipeline(dataset_path=path, sample_size=payload.sample_size)


def _last_user_message(messages) -> tuple[str, list[dict[str, str]]]:
    history: list[dict[str, str]] = []
    question = ""
    for message in messages:
        content = message.content or ""
        if message.role == "user":
            question = content
        if message.role in {"user", "assistant"}:
            history.append({"role": message.role, "content": content})
    history = history[:-1] if history and history[-1]["role"] == "user" else history
    if not question:
        raise HTTPException(status_code=400, detail="No user message provided")
    return question, history


@openai_router.get("/models")
def openai_models() -> dict:
    return {
        "object": "list",
        "data": [
            {"id": "docsearch-agentic", "object": "model", "owned_by": "docsearch"},
            {"id": "docsearch-direct", "object": "model", "owned_by": "docsearch"},
        ],
    }


def _completion_payload(model: str, answer: str, created: int) -> dict:
    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@openai_router.post("/chat/completions")
async def chat_completions(payload: ChatCompletionRequest):
    question, history = _last_user_message(payload.messages)
    mode = "direct" if "direct" in payload.model else "agentic"
    if mode == "direct":
        result = run_direct_rag(question)
    else:
        result = run_agentic_rag(question, chat_history=history)
    created = int(time.time())

    if not payload.stream:
        return _completion_payload(payload.model, result.answer, created)

    async def event_stream():
        chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        header = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": payload.model,
            "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}],
        }
        yield f"data: {json.dumps(header)}\n\n"
        # Stream the finished agentic answer in small pieces for OpenWebUI
        text = result.answer or ""
        step = 24
        for i in range(0, len(text), step):
            piece = {
                "id": chunk_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": payload.model,
                "choices": [
                    {"index": 0, "delta": {"content": text[i : i + step]}, "finish_reason": None}
                ],
            }
            yield f"data: {json.dumps(piece)}\n\n"
        done = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": payload.model,
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }
        yield f"data: {json.dumps(done)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
