from __future__ import annotations

import logging

from docsearch.config import Settings

logger = logging.getLogger(__name__)

_INSTRUMENTED = False


def setup_tracing(settings: Settings) -> None:
    """Register Arize Phoenix + OpenInference instrumentation. Never crash the API."""
    global _INSTRUMENTED
    if _INSTRUMENTED or not settings.phoenix_enabled:
        return
    try:
        from phoenix.otel import register
        from openinference.instrumentation.llama_index import LlamaIndexInstrumentor
        from openinference.instrumentation.openai import OpenAIInstrumentor

        register(
            project_name=settings.phoenix_project_name,
            endpoint=settings.phoenix_collector_endpoint,
            auto_instrument=True,
            batch=True,
        )
        LlamaIndexInstrumentor().instrument()
        OpenAIInstrumentor().instrument()
        try:
            from openinference.instrumentation.crewai import CrewAIInstrumentor

            CrewAIInstrumentor().instrument()
        except Exception as exc:  # pragma: no cover - optional instrumentor
            logger.warning("CrewAI Phoenix instrumentor skipped: %s", exc)
        _INSTRUMENTED = True
        logger.info(
            "Phoenix tracing enabled project=%s endpoint=%s",
            settings.phoenix_project_name,
            settings.phoenix_collector_endpoint,
        )
    except Exception as exc:
        logger.warning("Phoenix tracing disabled: %s", exc)
