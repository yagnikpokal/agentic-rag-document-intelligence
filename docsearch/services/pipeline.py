from __future__ import annotations

import logging
import time
from pathlib import Path

from llama_index.core import VectorStoreIndex
from llama_index.core.schema import TextNode

from docsearch.config import Settings, get_settings
from docsearch.services.ingestion import parse_pdf, to_nodes
from docsearch.services.llm import get_embed_model, get_llm
from docsearch.services import metadata as meta
from docsearch.services.vectorstore import get_index, get_vector_store

logger = logging.getLogger(__name__)


def ingest_paths(
    paths: list[Path],
    *,
    enrich: bool | None = None,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    enrich = settings.enable_contextual_enrichment if enrich is None else enrich
    started = time.perf_counter()
    meta.ensure_schema()

    from llama_index.core import Settings as LlamaSettings

    LlamaSettings.llm = get_llm()
    LlamaSettings.embed_model = get_embed_model()

    index: VectorStoreIndex = get_index()
    documents: list[dict] = []
    all_nodes: list[TextNode] = []

    for path in paths:
        filename = path.name
        try:
            meta.upsert_document(filename, str(path), status="processing")
            _, chunks = parse_pdf(path)
            nodes = to_nodes(filename, str(path), chunks, enrich=enrich)
            if nodes:
                index.insert_nodes(nodes)
                all_nodes.extend(nodes)
            record = meta.upsert_document(
                filename,
                str(path),
                status="indexed",
                chunk_count=len(nodes),
            )
            documents.append(record)
            logger.info("Indexed %s (%s chunks)", filename, len(nodes))
        except Exception as exc:
            logger.exception("Failed to ingest %s", filename)
            record = meta.upsert_document(
                filename,
                str(path),
                status="error",
                error=str(exc),
            )
            documents.append(record)

    # Touch the vector store so LlamaIndex creates HNSW / tables on first run
    _ = get_vector_store()
    return {
        "documents": documents,
        "chunks_indexed": len(all_nodes),
        "elapsed_seconds": round(time.perf_counter() - started, 2),
    }


def ingest_directory(directory: Path | None = None, enrich: bool | None = None) -> dict:
    settings = get_settings()
    directory = Path(directory or settings.pdf_dir)
    directory.mkdir(parents=True, exist_ok=True)
    pdfs = sorted(directory.glob("*.pdf"))
    if not pdfs:
        raise FileNotFoundError(f"No PDF files found in {directory}")
    return ingest_paths(pdfs, enrich=enrich, settings=settings)
