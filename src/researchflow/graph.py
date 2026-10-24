"""Actual LangGraph workflow: plan -> search -> reflect -> write -> validate."""

from langgraph.graph import END, START, StateGraph

from .providers import LanguageProvider, SearchProvider
from .schemas import ResearchState, invalid_citations, merge_sources, used_citations


def build_graph(language: LanguageProvider, searcher: SearchProvider):
    """Return uncompiled StateGraph so the caller can supply a checkpointer."""

    def plan(state: ResearchState) -> dict:
        queries = [q.strip() for q in language.plan(state["question"]) if isinstance(q, str) and q.strip()]
        queries = list(dict.fromkeys(queries))[:3]
        if not queries:
            queries = [state["question"]]
        return {"next_query": queries[0], "queue": queries[1:]}

    def search(state: ResearchState) -> dict:
        query = state["next_query"]
        if state["attempts"] >= state["budget"]:
            return {"keep_searching": False}
        warnings = list(state["warnings"])
        try:
            results = searcher.search(query)
        except Exception as exc:
            results = []
            # Never include secrets or full raw provider exception text in output.
            warnings.append(f"Search failed for query {len(state['tried_queries']) + 1}: {type(exc).__name__}")
        sources = merge_sources(state["sources"], results, query)
        return {
            "sources": sources,
            "attempts": state["attempts"] + 1,
            "tried_queries": [*state["tried_queries"], query],
            "next_query": "",
            "warnings": warnings,
        }

    def reflect(state: ResearchState) -> dict:
        # Hard upper bound prevents unbounded search and unnecessary API costs.
        if state["attempts"] >= state["budget"]:
            return {"keep_searching": False}
        queued = list(state["queue"])
        if queued:
            return {"keep_searching": True, "next_query": queued[0], "queue": queued[1:]}
        if not state["sources"]:
            # At least one more attempt is useful when the first search failed.
            fallback = f"{state['question']} documentation"
            if fallback not in state["tried_queries"]:
                return {"keep_searching": True, "next_query": fallback}
            return {"keep_searching": False}
        review = language.review(state["question"], state["sources"])
        followup = review.followup_query.strip()
        if review.needs_more_search and followup and followup not in state["tried_queries"]:
            return {"keep_searching": True, "next_query": followup}
        return {"keep_searching": False}

    def route(state: ResearchState) -> str:
        return "search" if state.get("keep_searching") else "write"

    def write(state: ResearchState) -> dict:
        if not state["sources"]:
            return {
                "report": "# Insufficient evidence\n\nNo search sources were available. Try another query.",
                "warnings": [*state["warnings"], "No sources found; no factual report was generated."],
            }
        return {"report": language.write(state["question"], state["sources"])}

    def validate(state: ResearchState) -> dict:
        bad = invalid_citations(state["report"], state["sources"])
        warnings = list(state["warnings"])
        if bad:
            warnings.append("Unknown source IDs cited: " + ", ".join(bad))
        if state["sources"] and not used_citations(state["report"]):
            warnings.append("The report has no machine-detectable source citations.")
        return {"invalid_citations": bad, "warnings": warnings}

    graph = StateGraph(ResearchState)
    graph.add_node("plan", plan)
    graph.add_node("search", search)
    graph.add_node("reflect", reflect)
    graph.add_node("write", write)
    graph.add_node("validate", validate)
    graph.add_edge(START, "plan")
    graph.add_edge("plan", "search")
    graph.add_edge("search", "reflect")
    graph.add_conditional_edges("reflect", route, {"search": "search", "write": "write"})
    graph.add_edge("write", "validate")
    graph.add_edge("validate", END)
    return graph
