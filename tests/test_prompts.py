from docsearch.prompt_store import PromptStore
from docsearch.config import ROOT_DIR


def test_all_required_prompts_exist_and_render():
    store = PromptStore(ROOT_DIR / "prompts", hot_reload=True)
    names = store.list_prompts()
    for required in (
        "query_planner",
        "retriever",
        "synthesizer",
        "critic",
        "contextualize",
        "direct_rag",
    ):
        assert required in names
        spec = store.get(required)
        assert spec.get("template")
        assert spec.get("system")


def test_query_planner_substitutes_variables():
    store = PromptStore(ROOT_DIR / "prompts")
    rendered = store.render("query_planner", query="What is PTO?", history="(none)")
    assert "What is PTO?" in rendered
    assert "(none)" in rendered
