from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from docsearch.config import get_settings
from docsearch.prompt_store import get_prompt_store
from docsearch.schemas import Citation
from docsearch.services.llm import complete
from docsearch.services.retrieval import RetrievedChunk, format_context, retrieve

logger = logging.getLogger(__name__)


@dataclass
class AgenticResult:
    answer: str
    rewritten_query: str
    chunks: list[RetrievedChunk]
    critic: dict[str, Any]
    mode: str
    latency_ms: int

    def citations(self) -> list[Citation]:
        seen: set[str] = set()
        out: list[Citation] = []
        for chunk in self.chunks:
            key = f"{chunk.filename}:{chunk.page}"
            if key in seen:
                continue
            seen.add(key)
            out.append(
                Citation(
                    filename=chunk.filename,
                    page=chunk.page,
                    score=chunk.score,
                    snippet=chunk.text[:280],
                )
            )
        return out


def _history_text(history: list[dict[str, str]] | None) -> str:
    if not history:
        return "(none)"
    lines = []
    for item in history[-8:]:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if content:
            lines.append(f"{role}: {content}")
    return "\n".join(lines) if lines else "(none)"


def _parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _parse_query_list(raw: str, fallback: str) -> list[str]:
    parsed = _parse_json(raw)
    if isinstance(parsed, list):
        return [str(x) for x in parsed if str(x).strip()]
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except json.JSONDecodeError:
        pass
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return [str(x) for x in data]
        except json.JSONDecodeError:
            pass
    return [fallback]


def _dedupe_chunks(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[str] = set()
    unique: list[RetrievedChunk] = []
    for chunk in chunks:
        key = f"{chunk.filename}:{chunk.chunk_index}:{chunk.text[:80]}"
        if key in seen:
            continue
        seen.add(key)
        unique.append(chunk)
    return unique


def _run_crewai(
    query: str,
    rewritten: str,
    context: str,
    store,
) -> str | None:
    """Primary multi-agent path. Returns synthesizer output or None on failure."""
    try:
        from crewai import Agent, Crew, LLM, Process, Task
        from crewai.tools import BaseTool
    except Exception as exc:
        logger.warning("CrewAI import failed: %s", exc)
        return None

    settings = get_settings()
    os.environ.setdefault("OPENAI_API_KEY", settings.openai_api_key)
    os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")

    llm = LLM(
        model=f"ollama/{settings.ollama_llm_model}",
        base_url=settings.ollama_base_url,
        temperature=settings.ollama_temperature,
    )

    class KnowledgeSearchTool(BaseTool):
        name: str = "search_knowledge_base"
        description: str = (
            "Search the ingested PDF knowledge base. Input is a natural language query."
        )

        def _run(self, search_query: str) -> str:
            chunks = retrieve(search_query)
            return format_context(chunks)

    planner = Agent(
        role="Query Planner",
        goal="Turn follow-up chat into a standalone retrieval query",
        backstory=store.system_role("query_planner"),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    retriever_agent = Agent(
        role="Knowledge Retriever",
        goal="Find the most relevant passages in the document knowledge base",
        backstory=store.system_role("retriever"),
        llm=llm,
        tools=[KnowledgeSearchTool()],
        verbose=False,
        allow_delegation=False,
    )
    synthesizer = Agent(
        role="Answer Synthesizer",
        goal="Write a grounded answer with citations from retrieved context",
        backstory=store.system_role("synthesizer"),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )
    critic = Agent(
        role="Groundedness Critic",
        goal="Reject answers that are not supported by retrieved context",
        backstory=store.system_role("critic"),
        llm=llm,
        verbose=False,
        allow_delegation=False,
    )

    t_plan = Task(
        description=store.render("query_planner", query=query, history="(already rewritten)"),
        expected_output="A single standalone search query",
        agent=planner,
    )
    t_retrieve = Task(
        description=(
            f"Search the knowledge base for: {rewritten}. "
            "Use the search_knowledge_base tool at least once."
        ),
        expected_output="Relevant passages copied from the knowledge base",
        agent=retriever_agent,
        context=[t_plan],
    )
    t_answer = Task(
        description=store.render("synthesizer", query=query, context=context),
        expected_output="Final user-facing answer with a Sources section",
        agent=synthesizer,
        context=[t_retrieve],
    )
    t_critic = Task(
        description=store.render("critic", query=query, context=context, answer="{answer}"),
        expected_output="JSON groundedness verdict",
        agent=critic,
        context=[t_answer],
    )

    crew = Crew(
        agents=[planner, retriever_agent, synthesizer, critic],
        tasks=[t_plan, t_retrieve, t_answer, t_critic],
        process=Process.sequential,
        verbose=False,
    )
    result = crew.kickoff(inputs={"query": query, "rewritten_query": rewritten, "answer": ""})
    return str(result)


def run_agentic_rag(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    top_k: int | None = None,
) -> AgenticResult:
    started = time.perf_counter()
    settings = get_settings()
    store = get_prompt_store()
    history = _history_text(chat_history)

    rewritten = complete(
        store.render("query_planner", query=query, history=history),
        system=store.system_role("query_planner"),
    ) or query
    rewritten = rewritten.splitlines()[0].strip().strip('"')

    search_raw = complete(
        store.render("retriever", query=query, rewritten_query=rewritten),
        system=store.system_role("retriever"),
    )
    search_queries = _parse_query_list(search_raw, rewritten)[:3]
    if rewritten not in search_queries:
        search_queries.insert(0, rewritten)

    chunks: list[RetrievedChunk] = []
    for q in search_queries:
        chunks.extend(retrieve(q, top_k=top_k))
    chunks = _dedupe_chunks(chunks)[: (top_k or settings.similarity_top_k) * 2]
    context = format_context(chunks)

    answer = complete(
        store.render("synthesizer", query=query, context=context),
        system=store.system_role("synthesizer"),
    )

    # CrewAI pass uses the same roles/prompts; synthesizer output is preferred when it succeeds.
    crew_out = None
    try:
        crew_out = _run_crewai(query, rewritten, context, store)
    except Exception as exc:
        logger.warning("CrewAI crew failed, using sequential synthesizer: %s", exc)

    if crew_out and len(crew_out.strip()) > 40:
        # Crew returns critic JSON last in sequential mode; keep synthesizer answer if JSON-only.
        parsed = _parse_json(crew_out)
        if not parsed.get("faithful") and "Sources:" not in crew_out and len(answer) > len(crew_out):
            pass
        elif "faithful" not in parsed:
            answer = crew_out.strip()

    critic: dict[str, Any] = {
        "faithful": True,
        "score": 1.0,
        "issues": [],
        "revised_query": "",
    }
    critic_raw = complete(
        store.render("critic", query=query, context=context, answer=answer),
        system=store.system_role("critic"),
    )
    critic = {**critic, **_parse_json(critic_raw)}

    rounds = 0
    while (
        not critic.get("faithful", True)
        and rounds < settings.agentic_max_revision_rounds
    ):
        rounds += 1
        extra = critic.get("revised_query") or rewritten
        chunks = _dedupe_chunks(chunks + retrieve(str(extra), top_k=top_k))
        context = format_context(chunks)
        answer = complete(
            store.render("synthesizer", query=query, context=context),
            system=store.system_role("synthesizer"),
        )
        critic_raw = complete(
            store.render("critic", query=query, context=context, answer=answer),
            system=store.system_role("critic"),
        )
        critic = {**critic, **_parse_json(critic_raw)}

    latency_ms = int((time.perf_counter() - started) * 1000)
    return AgenticResult(
        answer=answer,
        rewritten_query=rewritten,
        chunks=chunks,
        critic=critic,
        mode="agentic",
        latency_ms=latency_ms,
    )


def run_direct_rag(query: str, top_k: int | None = None) -> AgenticResult:
    started = time.perf_counter()
    store = get_prompt_store()
    chunks = retrieve(query, top_k=top_k)
    context = format_context(chunks)
    answer = complete(
        store.render("direct_rag", query=query, context=context),
        system=store.system_role("direct_rag"),
    )
    return AgenticResult(
        answer=answer,
        rewritten_query=query,
        chunks=chunks,
        critic={"faithful": None, "score": None, "issues": [], "revised_query": ""},
        mode="direct",
        latency_ms=int((time.perf_counter() - started) * 1000),
    )
