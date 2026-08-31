from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    source_dir: str | None = None
    contextual_enrichment: bool | None = None


class IngestResponse(BaseModel):
    documents: list[dict[str, Any]]
    chunks_indexed: int
    elapsed_seconds: float


class QueryRequest(BaseModel):
    question: str
    chat_history: list[dict[str, str]] = Field(default_factory=list)
    mode: Literal["agentic", "direct"] = "agentic"
    top_k: int | None = None


class Citation(BaseModel):
    filename: str
    page: str | int | None = None
    score: float | None = None
    snippet: str = ""


class QueryResponse(BaseModel):
    answer: str
    rewritten_query: str | None = None
    citations: list[Citation] = Field(default_factory=list)
    critic: dict[str, Any] | None = None
    latency_ms: int
    mode: str


class DocumentRecord(BaseModel):
    id: str
    filename: str
    source_path: str
    chunk_count: int
    status: str
    error: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HealthComponent(BaseModel):
    name: str
    ok: bool
    detail: str = ""


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded", "error"]
    components: list[HealthComponent]


class EvalRequest(BaseModel):
    dataset_path: str | None = None
    sample_size: int | None = None


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "docsearch-agentic"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
