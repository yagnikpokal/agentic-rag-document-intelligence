from __future__ import annotations

from functools import lru_cache

from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama

from docsearch.config import Settings, get_settings


def build_llm(settings: Settings | None = None) -> Ollama:
    settings = settings or get_settings()
    return Ollama(
        model=settings.ollama_llm_model,
        base_url=settings.ollama_base_url,
        request_timeout=settings.ollama_request_timeout,
        temperature=settings.ollama_temperature,
    )


def build_embed_model(settings: Settings | None = None) -> OllamaEmbedding:
    settings = settings or get_settings()
    return OllamaEmbedding(
        model_name=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


@lru_cache
def get_llm() -> Ollama:
    return build_llm()


@lru_cache
def get_embed_model() -> OllamaEmbedding:
    return build_embed_model()


def complete(prompt: str, system: str = "") -> str:
    llm = get_llm()
    if system:
        full = f"System: {system.strip()}\n\n{prompt}"
    else:
        full = prompt
    response = llm.complete(full)
    return str(response).strip()
