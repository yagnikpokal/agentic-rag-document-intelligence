from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from docsearch.api import openai_router, router
from docsearch.config import get_settings
from docsearch.observability import setup_tracing
from docsearch.services import metadata as meta

logger = logging.getLogger(__name__)


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(settings.log_level)
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
    setup_tracing(settings)
    try:
        meta.ensure_schema()
    except Exception as exc:
        logger.warning("Database schema not ready yet: %s", exc)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description=(
            "Agentic RAG document search backend for OpenWebUI. "
            "Ingests PDFs with Docling, indexes them in PostgreSQL/pgvector via LlamaIndex, "
            "answers with a CrewAI multi-agent pipeline, traces calls in Arize Phoenix, "
            "and evaluates with RAGAs."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api/v1", tags=["platform"])
    app.include_router(openai_router, prefix="/v1", tags=["openai-compatible"])
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "docsearch.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.app_env == "local",
    )
