from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from docsearch.config import Settings, get_settings

_ENGINE: Engine | None = None


def get_engine(settings: Settings | None = None) -> Engine:
    global _ENGINE
    if _ENGINE is None:
        settings = settings or get_settings()
        _ENGINE = create_engine(settings.postgres_uri, pool_pre_ping=True, future=True)
    return _ENGINE


def ensure_schema() -> None:
    engine = get_engine()
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        conn.execute(text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"'))
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS ingested_documents (
                    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                    filename TEXT NOT NULL UNIQUE,
                    source_path TEXT NOT NULL,
                    mime_type TEXT DEFAULT 'application/pdf',
                    chunk_count INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending',
                    error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        )


def upsert_document(
    filename: str,
    source_path: str,
    status: str,
    chunk_count: int = 0,
    error: str | None = None,
) -> dict[str, Any]:
    ensure_schema()
    engine = get_engine()
    now = datetime.utcnow()
    with engine.begin() as conn:
        row = conn.execute(
            text(
                """
                INSERT INTO ingested_documents
                    (id, filename, source_path, chunk_count, status, error, created_at, updated_at)
                VALUES
                    (:id, :filename, :source_path, :chunk_count, :status, :error, :now, :now)
                ON CONFLICT (filename) DO UPDATE SET
                    source_path = EXCLUDED.source_path,
                    chunk_count = EXCLUDED.chunk_count,
                    status = EXCLUDED.status,
                    error = EXCLUDED.error,
                    updated_at = EXCLUDED.updated_at
                RETURNING id, filename, source_path, chunk_count, status, error, created_at, updated_at
                """
            ),
            {
                "id": str(uuid4()),
                "filename": filename,
                "source_path": source_path,
                "chunk_count": chunk_count,
                "status": status,
                "error": error,
                "now": now,
            },
        ).mappings().one()
    return dict(row)


def list_documents() -> list[dict[str, Any]]:
    ensure_schema()
    engine = get_engine()
    with engine.begin() as conn:
        rows = conn.execute(
            text(
                """
                SELECT id, filename, source_path, chunk_count, status, error, created_at, updated_at
                FROM ingested_documents
                ORDER BY updated_at DESC
                """
            )
        ).mappings()
        return [dict(r) for r in rows]


def delete_document(filename: str) -> bool:
    engine = get_engine()
    with engine.begin() as conn:
        result = conn.execute(
            text("DELETE FROM ingested_documents WHERE filename = :filename"),
            {"filename": filename},
        )
        return result.rowcount > 0
