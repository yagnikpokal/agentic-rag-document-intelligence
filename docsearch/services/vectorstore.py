from __future__ import annotations

from functools import lru_cache

from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.vector_stores.types import VectorStoreQueryMode
from llama_index.vector_stores.postgres import PGVectorStore

from docsearch.config import Settings, get_settings
from docsearch.services.llm import get_embed_model


def build_vector_store(settings: Settings | None = None) -> PGVectorStore:
    settings = settings or get_settings()
    return PGVectorStore.from_params(
        database=settings.postgres_db,
        host=settings.postgres_host,
        password=settings.postgres_password,
        port=str(settings.postgres_port),
        user=settings.postgres_user,
        table_name=settings.vector_table,
        embed_dim=settings.embed_dim,
        hybrid_search=settings.enable_hybrid_search,
        text_search_config="english",
        hnsw_kwargs={
            "hnsw_m": 16,
            "hnsw_ef_construction": 64,
            "hnsw_ef_search": 40,
            "hnsw_dist_method": "vector_cosine_ops",
        },
    )


@lru_cache
def get_vector_store() -> PGVectorStore:
    return build_vector_store()


def get_index() -> VectorStoreIndex:
    vector_store = get_vector_store()
    storage = StorageContext.from_defaults(vector_store=vector_store)
    return VectorStoreIndex.from_vector_store(
        vector_store,
        storage_context=storage,
        embed_model=get_embed_model(),
    )


def query_mode(settings: Settings | None = None) -> VectorStoreQueryMode:
    settings = settings or get_settings()
    if settings.enable_hybrid_search:
        return VectorStoreQueryMode.HYBRID
    return VectorStoreQueryMode.DEFAULT
