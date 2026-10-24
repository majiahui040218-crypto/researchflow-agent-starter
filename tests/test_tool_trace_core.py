"""Pure stdlib tests for task traces. No LLM, LangGraph, or API calls."""

from types import SimpleNamespace

from researchflow.tool_trace import summarize_tool_trace


def message(kind, **attrs):
    return SimpleNamespace(type=kind, **attrs)


def test_observed_tool_call_and_tokens_not_raw_results():
    secret = "API_SECRET_DO_NOT_PERSIST"
    messages = [
        message("human", content="Private user question " + secret),
        message("ai", content="", tool_calls=[{
            "name": "github_repo_info",
            "args": {"repository": "org/private-" + secret},
            "id": "private_call_" + secret,
        }], usage_metadata={"input_tokens": 10, "output_tokens": 5}),
        message("tool", content="{\"repo\": \"" + secret + "\"}",
                name="github_repo_info", tool_call_id="private_call_" + secret,
                status="success"),
        message("ai", content="Answer includes " + secret, tool_calls=[],
                usage_metadata={"input_tokens": 20, "output_tokens": 7}),
    ]
    trace = summarize_tool_trace(messages, mode="mock", complete=True, duration_ms=123.45)
    assert trace["tool_calls_requested"] == 1
    assert trace["tool_results_observed"] == 1
    assert trace["llm_responses_observed"] == 2
    assert trace["input_tokens_observed"] == 30
    assert trace["output_tokens_observed"] == 12
    assert trace["synthetic"] is True
    assert trace["complete"] is True
    assert trace["events"][0]["argument_keys"] == ["repository"]
    assert trace["events"][0]["result"] == "executed"
    assert secret not in str(trace)
    assert "private_call" not in str(trace)


def test_budget_blocked_request_is_not_executed():
    messages = [message("ai", tool_calls=[
        {"name": "web_search", "id": "first", "args": {"query": "hello"}},
        {"name": "web_search", "id": "second", "args": {"query": "world"}},
    ], usage_metadata={})]
    trace = summarize_tool_trace(messages, mode="mock", complete=True, limit_reached=True)
    assert trace["tool_calls_requested"] == 2
    assert trace["tool_results_observed"] == 0
    assert all(row["result"] == "budget_blocked" for row in trace["events"])
    assert trace["usage_available"] is False


def test_tool_error_only_stores_boolean_status():
    secret = "RAW_ERROR_SECRET_VALUE"
    messages = [
        message("ai", tool_calls=[{"name": "web_search", "id": "abc", "args": {"query": "foo"}}]),
        message("tool", tool_call_id="abc", status="success", content='{"error":"' + secret + '"}'),
    ]
    trace = summarize_tool_trace(messages, mode="live", complete=True)
    assert trace["events"][0]["result"] == "error"
    assert trace["synthetic"] is False
    assert secret not in str(trace)


def test_failure_with_only_human_message_keeps_empty_trace():
    trace = summarize_tool_trace(
        [message("human", content="Private question")],
        mode="live", complete=False, error_code="MODEL_BUSY", duration_ms=35,
    )
    assert trace["error_code"] == "MODEL_BUSY"
    assert trace["llm_responses_observed"] == 0
    assert trace["tool_calls_requested"] == 0
    assert trace["duration_ms"] == 35
    assert trace["complete"] is False


def test_unknown_tool_and_argument_name_are_redacted():
    secret = "supersecret123456"
    messages = [message("ai", tool_calls=[
        {"name": "tool" + secret, "id": "id", "args": {secret: "somevalue"}},
    ])]
    trace = summarize_tool_trace(messages, mode="live", complete=False)
    assert trace["events"][0]["tool"] == "unknown_tool"
    assert trace["events"][0]["argument_keys"] == ["other"]
    assert secret not in str(trace)


def test_bounded_event_count_and_total_request_count():
    calls = [{"name": "web_search", "id": str(i), "args": {"query": "hello"}} for i in range(60)]
    trace = summarize_tool_trace([message("ai", tool_calls=calls)], mode="mock", complete=False)
    assert trace["tool_calls_requested"] == 60
    assert len(trace["events"]) == 40
    assert trace["events_truncated"] is True
