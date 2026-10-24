"""Verify the new entrypoint persists completed tasks without using the network."""
import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")

from researchflow.config import Settings
from researchflow.tool_cli import run_tool_task
from researchflow.service import load_research


def test_mock_tool_task_saved_and_queryable(tmp_path):
    settings = Settings("mock", tmp_path / "tool-run.db", 1, "unused")
    result = run_tool_task("请查看 GitHub 仓库 langchain-ai/langgraph", mode="mock", settings=settings)
    assert result["status"] == "completed"
    assert result["attempts"] == 1
    saved = load_research(result["task_id"], settings=settings)
    assert saved is not None
    assert saved.status == "completed"
    assert "DEMO" in saved.state["report"]


def test_tool_task_failure_is_saved_without_raw_exception(tmp_path):
    from researchflow.research_tools import build_research_tools

    class BrokenModel:
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            raise RuntimeError("RAW SECRET ERROR TEXT SHOULD NOT BE SAVED")

    settings = Settings("mock", tmp_path / "tool-fail.db", 1, "unused")
    result = run_tool_task(
        "比较 LangGraph 和 CrewAI", mode="mock", settings=settings,
        model=BrokenModel(), tools=build_research_tools("mock"),
    )
    assert result["status"] == "failed"
    saved = load_research(result["task_id"], settings=settings)
    assert saved is not None and saved.status == "failed"
    assert "RAW SECRET" not in (saved.error_message or "")
