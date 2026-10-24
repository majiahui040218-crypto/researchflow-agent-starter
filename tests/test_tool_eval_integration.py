"""Actual LangGraph graph tests using synthetic tools and deterministic models."""

from pathlib import Path

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langchain_core")

from langchain_core.messages import AIMessage
from researchflow.tool_eval import load_cases, run_case, summarize


CASES = load_cases(Path(__file__).resolve().parents[1] / "eval" / "tool_cases.jsonl")


@pytest.mark.parametrize("case", CASES, ids=[case["id"] for case in CASES])
def test_all_mock_evaluation_cases_are_deterministic(case):
    outcome = run_case(case, mode="mock")
    assert outcome["status"] == "ok", outcome
    assert outcome["passed"], outcome
    assert outcome["tool_calls_used"] <= case["max_tool_calls"]


def test_wrong_tool_selection_is_detected_not_counted_as_success():
    class WrongModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            from langchain_core.messages import ToolMessage
            if isinstance(messages[-1], ToolMessage):
                return AIMessage(content="DEMO completed")
            return AIMessage(content="", tool_calls=[
                {"name": "web_search", "args": {"query": "not the GitHub API"}, "id": "wrong_1"}
            ])

    outcome = run_case(CASES[0], mode="mock", model_override=WrongModel())
    assert outcome["status"] == "ok"
    assert not outcome["passed"]
    assert outcome["selection_match"] is False
    assert outcome["executed"] == ["web_search"]


def test_mock_metric_is_explicitly_synthetic():
    rows = [run_case(case, mode="mock") for case in CASES]
    stats = summarize(rows, mode="mock")
    assert stats["synthetic"] is True
    assert stats["passed_cases"] == len(CASES)
    assert stats["tool_selection_total"] == 3
    assert stats["fault_handling_total"] == 2
    assert stats["budget_guard_total"] == 1


def test_provider_errors_are_redacted_in_eval_output():
    for case in CASES:
        if case["scenario"] in ("github_failure", "web_failure"):
            result = run_case(case, mode="mock")
            assert result["status"] == "ok"
            assert "INJECTED SECRET" not in str(result)
