from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from docsearch.config import get_settings
from docsearch.services.agents import run_agentic_rag

logger = logging.getLogger(__name__)


def load_golden_set(path: Path | None = None) -> list[dict[str, Any]]:
    settings = get_settings()
    dataset_path = Path(path or settings.eval_dataset_path)
    with dataset_path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _ollama_langchain_pair():
    settings = get_settings()
    from langchain_openai import ChatOpenAI, OpenAIEmbeddings

    llm = ChatOpenAI(
        model=settings.ollama_llm_model,
        base_url=settings.ollama_openai_base,
        api_key="ollama",
        temperature=0,
        timeout=settings.ollama_request_timeout,
    )
    embeddings = OpenAIEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_openai_base,
        api_key="ollama",
        check_embedding_ctx_length=False,
    )
    return llm, embeddings


def _run_ragas(samples: list[dict[str, Any]]) -> dict[str, float] | None:
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.llms import LangchainLLMWrapper
        from ragas.embeddings import LangchainEmbeddingsWrapper
    except Exception as exc:
        logger.warning("RAGAs import failed: %s", exc)
        return None

    try:
        from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall

        metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    except Exception:
        try:
            from ragas.metrics import Faithfulness, ResponseRelevancy, LLMContextPrecisionWithoutReference, LLMContextRecall

            metrics = [
                Faithfulness(),
                ResponseRelevancy(),
                LLMContextPrecisionWithoutReference(),
                LLMContextRecall(),
            ]
        except Exception as exc:
            logger.warning("RAGAs metrics unavailable: %s", exc)
            return None

    llm, embeddings = _ollama_langchain_pair()
    wrapped_llm = LangchainLLMWrapper(llm)
    wrapped_emb = LangchainEmbeddingsWrapper(embeddings)
    dataset = Dataset.from_list(samples)
    result = evaluate(
        dataset=dataset,
        metrics=metrics,
        llm=wrapped_llm,
        embeddings=wrapped_emb,
    )
    scores: dict[str, float] = {}
    try:
        mapping = dict(result)
        for key, value in mapping.items():
            try:
                scores[str(key)] = float(value)
            except (TypeError, ValueError):
                continue
    except Exception:
        scores = {"raw": str(result)}
    return scores


def evaluate_pipeline(
    dataset_path: Path | None = None,
    sample_size: int | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    golden = load_golden_set(dataset_path)
    if sample_size:
        golden = golden[:sample_size]

    rows: list[dict[str, Any]] = []
    lexical_hits = 0
    latencies: list[int] = []

    for item in golden:
        question = item["question"]
        expected = item.get("ground_truth") or item.get("answer") or ""
        result = run_agentic_rag(question)
        latencies.append(result.latency_ms)
        contexts = [c.text for c in result.chunks]
        hit = bool(expected) and expected.lower()[:48] in (result.answer.lower() + " " + " ".join(contexts).lower())
        if not hit and expected:
            tokens = [t for t in expected.lower().split() if len(t) > 4]
            hit = sum(t in result.answer.lower() for t in tokens) >= max(1, len(tokens) // 4)
        lexical_hits += int(hit)
        rows.append(
            {
                "question": question,
                "answer": result.answer,
                "ground_truth": expected,
                "contexts": contexts,
                "latency_ms": result.latency_ms,
                "lexical_hit": hit,
            }
        )

    ragas_samples = [
        {
            "question": r["question"],
            "user_input": r["question"],
            "answer": r["answer"],
            "response": r["answer"],
            "contexts": r["contexts"],
            "retrieved_contexts": r["contexts"],
            "ground_truth": r["ground_truth"],
            "reference": r["ground_truth"],
        }
        for r in rows
    ]
    ragas_scores = _run_ragas(ragas_samples)

    n = max(len(rows), 1)
    summary = {
        "cases": len(rows),
        "lexical_hit_rate": round(lexical_hits / n, 3),
        "avg_latency_ms": int(sum(latencies) / n) if latencies else 0,
        "p95_latency_ms": int(sorted(latencies)[max(0, int(0.95 * len(latencies)) - 1)]) if latencies else 0,
        "ragas": ragas_scores,
        "elapsed_seconds": round(time.perf_counter() - started, 2),
        "results": [
            {
                "question": r["question"],
                "lexical_hit": r["lexical_hit"],
                "latency_ms": r["latency_ms"],
                "answer_preview": r["answer"][:240],
            }
            for r in rows
        ],
    }
    return summary
