from __future__ import annotations

from dataclasses import dataclass

from llama_index.core.schema import NodeWithScore

from docsearch.config import get_settings
from docsearch.services.vectorstore import get_index, query_mode


@dataclass
class RetrievedChunk:
    text: str
    filename: str
    page: str | int | None
    score: float | None
    chunk_index: int | None


def _to_chunk(node: NodeWithScore) -> RetrievedChunk:
    meta = node.metadata or {}
    return RetrievedChunk(
        text=node.get_text(),
        filename=str(meta.get("filename") or meta.get("file_name") or "unknown"),
        page=meta.get("page"),
        score=float(node.score) if node.score is not None else None,
        chunk_index=meta.get("chunk_index"),
    )


def retrieve(query: str, top_k: int | None = None) -> list[RetrievedChunk]:
    settings = get_settings()
    k = top_k or settings.similarity_top_k
    index = get_index()
    retriever = index.as_retriever(
        similarity_top_k=k,
        vector_store_query_mode=query_mode(settings),
    )
    nodes = retriever.retrieve(query)
    return [_to_chunk(n) for n in nodes]


def format_context(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for i, chunk in enumerate(chunks, start=1):
        header = f"[{i}] {chunk.filename}"
        if chunk.page is not None:
            header += f" (page {chunk.page})"
        blocks.append(f"{header}\n{chunk.text}")
    return "\n\n---\n\n".join(blocks) if blocks else "(no context retrieved)"
