"""Integration tests; no internet or real API keys required."""

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")

from researchflow.config import Settings
from researchflow.providers import ProviderCallError
from researchflow.service import load_research, run_research


def test_mock_is_saved_as_completed(tmp_path):
    settings = Settings("mock", tmp_path / "run.db", 1, "unused")
    result = run_research("Compare LangGraph and CrewAI", settings)
    assert result.status == "completed"
    assert load_research(result.task_id, settings).status == "completed"


def test_failed_provider_saved_and_queryable(tmp_path, monkeypatch):
    from researchflow import service

    class BrokenLLM:
        def plan(self, question):
            raise ProviderCallError("MODEL_BUSY", "模型繁忙（1305）", retryable=True)
        def close(self):
            pass

    class EmptySearch:
        def search(self, query):
            return []

    monkeypatch.setattr(service, "_providers", lambda settings: (BrokenLLM(), EmptySearch()))
    settings = Settings("live", tmp_path / "fail.db", 1, "unused")
    result = run_research("Compare LangGraph and CrewAI", settings)
    assert result.status == "failed"
    assert result.error_code == "MODEL_BUSY"
    assert not result.state.get("report")
    restored = load_research(result.task_id, settings)
    assert restored is not None
    assert restored.status == "failed"
    assert restored.error_code == "MODEL_BUSY"
