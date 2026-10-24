"""Offline-first Tool Calling evaluation for ResearchFlow.

Mock mode uses deterministic test doubles. Its accuracy is NOT a measure of
GLM's real-world tool-choice accuracy. Live mode is opt-in, rate-limited by
an explicit maximum case count, and only runs non-fault-injection scenarios.

Run from repository root:
    python -m researchflow.tool_eval --mode mock
    python -m researchflow.tool_eval --mode live --max-cases 1
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
from typing import Any

ALLOWED_SCENARIOS = {"normal", "no_tool", "github_failure", "web_failure", "budget_overflow"}
LIVE_SCENARIOS = {"normal", "no_tool"}


def load_cases(path: Path) -> list[dict[str, Any]]:
    """Load and validate a fixed, human-authored evaluation dataset."""
    cases: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        try:
            case = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {number}") from exc
        if not isinstance(case, dict):
            raise ValueError(f"Case on line {number} must be an object")
        case_id = case.get("id")
        scenario = case.get("scenario")
        if not isinstance(case_id, str) or not case_id.strip() or case_id in seen:
            raise ValueError(f"Missing or duplicate case id on line {number}")
        if scenario not in ALLOWED_SCENARIOS:
            raise ValueError(f"Unknown scenario for {case_id}: {scenario}")
        if not isinstance(case.get("question"), str) or not case["question"].strip():
            raise ValueError(f"Invalid question for {case_id}")
        for key in ("expected_requested", "expected_executed", "expected_errors"):
            value = case.get(key)
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise ValueError(f"Invalid {key} for {case_id}")
        budget = case.get("max_tool_calls")
        if type(budget) is not int or not 1 <= budget <= 6:
            raise ValueError(f"Invalid max_tool_calls for {case_id}")
        if type(case.get("expect_limit_reached")) is not bool:
            raise ValueError(f"Invalid expect_limit_reached for {case_id}")
        seen.add(case_id)
        cases.append(case)
    if not cases:
        raise ValueError("The evaluation file contains no cases")
    return cases


def _percent(numerator: int, denominator: int) -> float | None:
    return round(100.0 * numerator / denominator, 2) if denominator else None


def summarize(rows: list[dict[str, Any]], *, mode: str) -> dict[str, Any]:
    """Compute explicit denominators; API failures do not count as wrong choices."""
    evaluated = [row for row in rows if row["status"] == "ok"]
    failures = [row for row in rows if row["status"] == "error"]
    selection = [r for r in evaluated if r["scenario"] in {"normal", "no_tool"}]
    fault_cases = [r for r in evaluated if r["scenario"] in {"github_failure", "web_failure"}]
    budget_cases = [r for r in evaluated if r["scenario"] == "budget_overflow"]
    return {
        "mode": mode,
        "synthetic": mode == "mock",
        "total_cases": len(rows),
        "evaluated_cases": len(evaluated),
        "provider_or_runtime_errors": len(failures),
        "passed_cases": sum(bool(r.get("passed")) for r in evaluated),
        "case_pass_rate_pct": _percent(sum(bool(r.get("passed")) for r in evaluated), len(evaluated)),
        "tool_selection_correct": sum(bool(r.get("selection_match")) for r in selection),
        "tool_selection_total": len(selection),
        "tool_selection_accuracy_pct": _percent(sum(bool(r.get("selection_match")) for r in selection), len(selection)),
        "fault_handling_passed": sum(bool(r.get("passed")) for r in fault_cases),
        "fault_handling_total": len(fault_cases),
        "budget_guard_passed": sum(bool(r.get("passed")) for r in budget_cases),
        "budget_guard_total": len(budget_cases),
    }


def _mock_dependencies(scenario: str):
    """Never contact GitHub/Tavily/GLM in the mock evaluation."""
    from langchain_core.messages import AIMessage
    from .research_tools import build_research_tools
    from .tool_cli import ScriptedDemoModel

    class FakeSearch:
        def search(self, query: str):
            if scenario == "web_failure":
                raise TimeoutError("INJECTED SECRET must not escape")
            return [{"title": "SYNTHETIC demo", "url": "https://example.com/mock", "snippet": "synthetic"}]

    def fake_github(repo: str):
        if scenario == "github_failure":
            raise RuntimeError("INJECTED SECRET must not escape")
        return {"repository": repo, "stars": None, "forks": None, "demo": True}

    class NoToolModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="DEMO ONLY: no tool needed")

    class BudgetOverflowModel:
        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[
                {"name": "web_search", "args": {"query": "research demo one"}, "id": "budget_1"},
                {"name": "web_search", "args": {"query": "research demo two"}, "id": "budget_2"},
            ])

    if scenario == "no_tool":
        model = NoToolModel()
    elif scenario == "budget_overflow":
        model = BudgetOverflowModel()
    else:
        model = ScriptedDemoModel()
    tools = build_research_tools("mock", search_provider=FakeSearch(), github_fetch=fake_github)
    return model, tools


def _trace(messages: list[Any]) -> tuple[list[str], list[str], list[str]]:
    """Separate requested tool calls from actually executed ToolMessages."""
    from langchain_core.messages import AIMessage, ToolMessage
    requested: list[str] = []
    executed: list[str] = []
    errors: list[str] = []
    id_to_name: dict[str, str] = {}
    for message in messages:
        if isinstance(message, AIMessage):
            for call in message.tool_calls or []:
                name = str(call.get("name", ""))
                requested.append(name)
                id_to_name[str(call.get("id", ""))] = name
        elif isinstance(message, ToolMessage):
            executed.append(str(message.name or id_to_name.get(str(message.tool_call_id), "")))
            try:
                value = json.loads(message.content) if isinstance(message.content, str) else None
            except (ValueError, TypeError):
                value = None
            if isinstance(value, dict) and isinstance(value.get("error"), str):
                errors.append(value["error"])
            elif getattr(message, "status", None) == "error":
                errors.append("TOOL_EXECUTION_ERROR")
    return requested, executed, errors


def run_case(case: dict[str, Any], *, mode: str = "mock", model_override=None, tools_override=None) -> dict[str, Any]:
    """Run one isolated graph; never log raw exception messages or API keys."""
    if mode not in {"mock", "live"}:
        raise ValueError("mode must be mock or live")
    if mode == "live" and case["scenario"] not in LIVE_SCENARIOS:
        raise ValueError("Live evaluation only supports normal/no_tool cases")

    started = time.monotonic()
    language = None
    try:
        from langchain_core.messages import HumanMessage
        from .tool_agent import build_tool_agent

        if model_override is not None and tools_override is not None:
            model, tools = model_override, tools_override
        elif mode == "mock":
            model, tools = _mock_dependencies(case["scenario"])
            if model_override is not None:
                model = model_override
            if tools_override is not None:
                tools = tools_override
        else:
            from dotenv import load_dotenv
            from .config import Settings
            from .providers import OpenAILanguage
            from .research_tools import build_research_tools
            load_dotenv()
            settings = Settings.from_env(require_live_keys=False)
            if not os.getenv("OPENAI_API_KEY") or not os.getenv("TAVILY_API_KEY"):
                raise ValueError("Missing live provider configuration")
            language = OpenAILanguage(settings.model)
            model, tools = language._model, build_research_tools("live")

        graph = build_tool_agent(model, tools, max_tool_calls=case["max_tool_calls"]).compile()
        result = graph.invoke(
            {"messages": [HumanMessage(content=case["question"])],
             "tool_calls_used": 0, "limit_reached": False},
            config={"recursion_limit": 20},
        )
        requested, executed, errors = _trace(result["messages"])
        selection_match = requested == case["expected_requested"]
        execution_match = executed == case["expected_executed"]
        errors_match = sorted(errors) == sorted(case["expected_errors"])
        budget_reached = bool(result.get("limit_reached", False))
        budget_match = budget_reached == case["expect_limit_reached"]
        calls_used = result.get("tool_calls_used", 0)
        bounded = calls_used <= case["max_tool_calls"] and calls_used == len(executed)
        passed = all((selection_match, execution_match, errors_match, budget_match, bounded))
        return {
            "id": case["id"], "scenario": case["scenario"], "status": "ok",
            "passed": passed, "selection_match": selection_match,
            "execution_match": execution_match, "errors_match": errors_match,
            "budget_match": budget_match, "calls_within_budget": bounded,
            "requested": requested, "executed": executed, "tool_errors": errors,
            "tool_calls_used": calls_used, "budget_reached": budget_reached,
            "duration_ms": round((time.monotonic() - started) * 1000, 1),
        }
    except Exception as exc:
        from .providers import _provider_error, ProviderCallError
        failure = exc if isinstance(exc, ProviderCallError) else _provider_error(exc)
        return {"id": case["id"], "scenario": case["scenario"], "status": "error",
                "passed": False, "error_code": failure.code,
                "duration_ms": round((time.monotonic() - started) * 1000, 1)}
    finally:
        if language is not None:
            language.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ResearchFlow Tool Calling evaluation")
    parser.add_argument("--mode", choices=["mock", "live"], default="mock")
    parser.add_argument("--cases", type=Path, default=Path("eval/tool_cases.jsonl"))
    parser.add_argument("--output", type=Path, default=Path("eval/results/tool_eval.json"))
    parser.add_argument("--max-cases", type=int, default=None,
                        help="For live mode defaults to 1 to limit model requests")
    args = parser.parse_args(argv)

    try:
        cases = load_cases(args.cases)
        if args.max_cases is not None and args.max_cases < 1:
            parser.error("--max-cases must be positive")
        if args.mode == "live":
            cases = [case for case in cases if case["scenario"] in LIVE_SCENARIOS]
            cases = cases[: args.max_cases if args.max_cases is not None else 1]
        elif args.max_cases is not None:
            cases = cases[:args.max_cases]
        if not cases:
            parser.error("No eligible evaluation cases")
        rows = [run_case(case, mode=args.mode) for case in cases]
        summary = summarize(rows, mode=args.mode)
        report = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                  "model_label": "scripted_mock" if args.mode == "mock" else "configured_live_model",
                  "summary": summary, "cases": rows,
                  "warning": (
                      "SCRIPTED MOCK: results measure workflow routing, not real LLM intelligence."
                      if args.mode == "mock" else
                      "LIVE: model and tool API requests may fail, be rate-limited, or incur costs."
                  )}
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as exc:
        # Dataset/file errors are local, not provider exceptions. Don't print secrets.
        print(f"Evaluation configuration error: {type(exc).__name__}", file=sys.stderr)
        return 2

    print("MOCK/模拟评测（非真实大模型表现）" if args.mode == "mock" else "LIVE/真实模型评测")
    print(f"Cases passed: {summary['passed_cases']}/{summary['evaluated_cases']}; "
          f"runtime/API errors: {summary['provider_or_runtime_errors']}")
    print(f"Tool selection: {summary['tool_selection_correct']}/{summary['tool_selection_total']} "
          f"({summary['tool_selection_accuracy_pct']}%)")
    print(f"Fault-handling checks: {summary['fault_handling_passed']}/{summary['fault_handling_total']}; "
          f"budget-guard checks: {summary['budget_guard_passed']}/{summary['budget_guard_total']}")
    print(f"Report: {args.output}")
    return 0 if summary["provider_or_runtime_errors"] == 0 and summary["passed_cases"] == summary["evaluated_cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
