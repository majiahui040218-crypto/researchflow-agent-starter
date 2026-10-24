"""Integration tests require the same dependencies as the original tool CLI."""

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langgraph.checkpoint.sqlite")
pytest.importorskip("langchain_core")

from langchain_core.messages import AIMessage, ToolMessage

from researchflow.config import Settings
from researchflow.service import load_research
from researchflow.tool_cli import run_tool_task
from researchflow.research_tools import build_research_tools


def test_mock_trace_persisted_and_queryable(tmp_path):
    settings = Settings("mock", tmp_path / "trace.db", 1, "unused")
    result = run_tool_task("帮我查找 LangGraph GitHub 仓库", mode="mock", settings=settings)
    assert result["status"] == "completed"
    audit = result["tool_trace"]
    assert audit["tool_calls_requested"] == 1
    assert audit["tool_results_observed"] == 1
    assert audit["events"][0]["tool"] == "github_repo_info"
    assert audit["events"][0]["result"] == "executed"
    assert audit["synthetic"] is True
    persisted = load_research(result["task_id"], settings=settings)
    assert persisted.state["tool_trace"] == audit


def test_budget_trace_explicitly_marks_non_execution(tmp_path):
    class TwoCalls:
        def bind_tools(self, tools): return self
        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[
                {"name": "web_search", "args": {"query": "one"}, "id": "one"},
                {"name": "web_search", "args": {"query": "two"}, "id": "two"},
                {"name": "web_search", "args": {"query": "three"}, "id": "three"},
                {"name": "web_search", "args": {"query": "four"}, "id": "four"},
            ])

    settings = Settings("mock", tmp_path / "budget.db", 1, "unused")
    result = run_tool_task("请帮我调研测试工具预算限制", mode="mock", settings=settings,
                           model=TwoCalls(), tools=build_research_tools("mock"))
    assert result["status"] == "completed"
    trace = result["tool_trace"]
    assert trace["tool_calls_requested"] == 4
    assert trace["tool_results_observed"] == 0
    assert trace["limit_reached"] is True
    assert all(event["result"] == "budget_blocked" for event in trace["events"])


def test_failed_call_trace_is_saved_and_private(tmp_path):
    from researchflow.providers import ProviderCallError

    class ErrorModel:
        def bind_tools(self, tools): return self
        def invoke(self, messages):
            raise ProviderCallError("MODEL_BUSY", "busy", retryable=True)

    settings = Settings("mock", tmp_path / "failure.db", 1, "unused")
    result = run_tool_task("演示免费 GLM 繁忙后如何记录轨迹", mode="mock", settings=settings,
                           model=ErrorModel(), tools=build_research_tools("mock"))
    assert result["status"] == "failed"
    assert result["error_code"] == "MODEL_BUSY"
    audit = result["tool_trace"]
    assert audit["complete"] is False
    assert audit["error_code"] == "MODEL_BUSY"
    assert audit["llm_responses_observed"] == 0
    persisted = load_research(result["task_id"], settings=settings)
    assert persisted.state["tool_trace"] == audit
