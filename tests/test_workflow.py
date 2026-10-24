import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")

from researchflow.config import Settings
from researchflow.service import load_research, run_research


def test_mock_graph_and_sqlite_persistence(tmp_path):
    settings = Settings(mode="mock", db_path=tmp_path / "checkpoint.db", max_searches=3, model="unused")
    result = run_research("Compare LangGraph and another agent framework", settings=settings)
    data = result.as_dict()
    assert data["mode"] == "mock"
    assert 1 <= data["search_count"] <= 3
    assert data["invalid_citations"] == []
    assert all(s["url"].startswith("https://example.com/") for s in data["sources"])
    assert "DEMO" in data["report"]
    restored = load_research(result.task_id, settings=settings)
    assert restored is not None
    assert restored.state["report"] == data["report"]
    assert load_research("not-uuid", settings=settings) is None
