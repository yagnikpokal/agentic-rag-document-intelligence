from __future__ import annotations

import logging
from pathlib import Path

from llama_index.core.schema import TextNode

from docsearch.config import get_settings
from docsearch.prompt_store import get_prompt_store
from docsearch.services.llm import complete

logger = logging.getLogger(__name__)


def parse_pdf(path: Path) -> tuple[str, list[dict]]:
    """Preprocess a PDF with Docling and return markdown plus structured chunks."""
    from docling.chunking import HybridChunker
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(str(path))
    document = result.document
    markdown = document.export_to_markdown()

    chunker = HybridChunker()
    structured: list[dict] = []
    for index, chunk in enumerate(chunker.chunk(dl_doc=document)):
        text = chunker.serialize(chunk=chunk) if hasattr(chunker, "serialize") else chunk.text
        page = None
        try:
            page = chunk.meta.doc_items[0].prov[0].page_no  # type: ignore[attr-defined]
        except Exception:
            page = None
        structured.append(
            {
                "text": text,
                "page": page,
                "chunk_index": index,
            }
        )
    if not structured and markdown.strip():
        structured.append({"text": markdown, "page": None, "chunk_index": 0})
    return markdown, structured


def to_nodes(
    filename: str,
    source_path: str,
    chunks: list[dict],
    enrich: bool = False,
) -> list[TextNode]:
    settings = get_settings()
    store = get_prompt_store()
    nodes: list[TextNode] = []
    for chunk in chunks:
        text = chunk["text"].strip()
        if not text:
            continue
        prefix = ""
        if enrich and settings.enable_contextual_enrichment:
            try:
                prefix = complete(
                    store.render(
                        "contextualize",
                        title=filename.replace(".pdf", "").replace("_", " ").title(),
                        filename=filename,
                        chunk=text[:4000],
                    ),
                    system=store.system_role("contextualize"),
                )
            except Exception as exc:
                logger.warning("Contextual enrichment skipped for %s: %s", filename, exc)
        payload = f"{prefix}\n\n{text}".strip() if prefix else text
        nodes.append(
            TextNode(
                text=payload,
                metadata={
                    "filename": filename,
                    "source_path": source_path,
                    "page": chunk.get("page"),
                    "chunk_index": chunk.get("chunk_index"),
                    "context_prefix": prefix,
                },
            )
        )
    return nodes
