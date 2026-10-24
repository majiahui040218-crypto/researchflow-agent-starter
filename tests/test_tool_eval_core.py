"""Pure-Python evaluation tests. No LangGraph or external APIs needed."""

import json
from pathlib import Path

import pytest

from researchflow.tool_eval import load_cases, summarize


def test_load_cases_and_validate_contract():
    path = Path(__file__).resolve().parents[1] / "eval" / "tool_cases.jsonl"
    cases = load_cases(path)
    assert len(cases) == 6
    assert len({case["id"] for case in cases}) == len(cases)
    assert cases[0]["expected_requested"] == ["github_repo_info"]


def test_load_cases_rejects_unknown_scenario(tmp_path):
    data = {"id": "invalid", "scenario": "unsupported", "question": "hello",
            "expected_requested": [], "expected_executed": [], "expected_errors": [],
            "expect_limit_reached": False, "max_tool_calls": 2}
    path = tmp_path / "cases.jsonl"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Unknown scenario"):
        load_cases(path)


def test_load_cases_rejects_duplicate_id(tmp_path):
    path = Path(__file__).resolve().parents[1] / "eval" / "tool_cases.jsonl"
    line = path.read_text(encoding="utf-8").splitlines()[0]
    dup = tmp_path / "duplicate.jsonl"
    dup.write_text(line + "\n" + line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        load_cases(dup)


def test_summary_has_explicit_denominators_and_skips_api_errors():
    rows = [
        {"status": "ok", "scenario": "normal", "passed": True, "selection_match": True},
        {"status": "ok", "scenario": "normal", "passed": False, "selection_match": False},
        {"status": "ok", "scenario": "budget_overflow", "passed": True},
        {"status": "error", "scenario": "normal", "passed": False, "error_code": "MODEL_BUSY"},
    ]
    data = summarize(rows, mode="mock")
    assert data["total_cases"] == 4
    assert data["provider_or_runtime_errors"] == 1
    assert data["evaluated_cases"] == 3
    assert data["passed_cases"] == 2
    assert data["tool_selection_correct"] == 1
    assert data["tool_selection_total"] == 2
    assert data["tool_selection_accuracy_pct"] == 50.0
    assert data["budget_guard_passed"] == 1
    assert data["synthetic"] is True


def test_zero_denominator_is_null_not_fake_perfect_score():
    data = summarize([{"status": "error", "scenario": "normal", "passed": False}], mode="live")
    assert data["tool_selection_accuracy_pct"] is None
    assert data["case_pass_rate_pct"] is None
    assert data["synthetic"] is False
