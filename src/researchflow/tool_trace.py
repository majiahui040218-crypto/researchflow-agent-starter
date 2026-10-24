"""Privacy-conscious traces of *observed* Agent tool calls.

We never record prompts, tool arguments/values, results, provider response text,
exception strings, or API keys. An LLM's internal reasoning is not observable.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

_MAX_EVENTS = 40
_SAFE_LABEL = re.compile(r"[^a-zA-Z0-9_.-]")


def _label(value: Any, limit: int = 80) -> str:
    # Filter rather than quoting potentially sensitive or untrusted text.
    return _SAFE_LABEL.sub("_", str(value or ""))[:limit]


def _call_ref(value: Any) -> str:
    # Store only a stable shortened digest, not provider-supplied tool IDs.
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()[:12]


def _tool_failed(message: Any) -> bool:
    if getattr(message, "status", None) == "error":
        return True
    payload = getattr(message, "content", None)
    if isinstance(payload, str) and len(payload) <= 50000:
        try:
            parsed = json.loads(payload)
        except (ValueError, TypeError):
            return False
        return isinstance(parsed, dict) and isinstance(parsed.get("error"), str)
    return False


def _message_type(message: Any) -> str:
    kind = getattr(message, "type", "")
    if kind:
        return str(kind)
    name = type(message).__name__.lower()
    if name.endswith("aimessage") or name == "fakeai":
        return "ai"
    if name.endswith("toolmessage") or name == "faketool":
        return "tool"
    return "other"


def summarize_tool_trace(
    messages: list[Any],
    *,
    mode: str,
    complete: bool,
    limit_reached: bool = False,
    duration_ms: float | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Extract requested/executed events from LangChain messages.

    A requested tool is NOT considered executed unless its ToolMessage appears.
    When a workflow fails, the caller can pass messages recovered from a
    LangGraph checkpoint. Only checkpoints that actually exist are included.
    """
    events: list[dict[str, Any]] = []
    pending: dict[str, list[int]] = {}
    total_requested = total_executed = observed_ai = 0
    input_tokens = output_tokens = 0
    usage_found = False
    truncated = False

    for message in messages:
        kind = _message_type(message)
        if kind == "ai":
            observed_ai += 1
            usage = getattr(message, "usage_metadata", None)
            if isinstance(usage, dict):
                for name in ("input_tokens", "output_tokens"):
                    value = usage.get(name)
                    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                        usage_found = True
                        if name == "input_tokens":
                            input_tokens += value
                        else:
                            output_tokens += value
            for call in (getattr(message, "tool_calls", None) or []):
                if not isinstance(call, dict):
                    continue
                total_requested += 1
                if len(events) >= _MAX_EVENTS:
                    truncated = True
                    continue
                call_id = str(call.get("id", ""))
                args = call.get("args")
                # Only recognize schema-defined parameter names. Arbitrary keys
                # could themselves contain credentials or prompt-injected text.
                allow_keys = {"repository", "query"}
                keys = (sorted(key if key in allow_keys else "other" for key in args)
                        if isinstance(args, dict) else [])
                pending.setdefault(call_id, []).append(len(events))
                name = call.get("name")
                safe_tool = name if isinstance(name, str) and name in {
                    "github_repo_info", "web_search"
                } else "unknown_tool"
                events.append({
                    "call_ref": _call_ref(call_id),
                    "tool": safe_tool,
                    "argument_keys": keys[:20],
                    "result": "not_observed",
                })
        elif kind == "tool":
            total_executed += 1
            call_id = str(getattr(message, "tool_call_id", ""))
            match = pending.get(call_id, [])
            if match:
                index = match.pop(0)
                events[index]["result"] = "error" if _tool_failed(message) else "executed"

    if limit_reached:
        for event in events:
            if event["result"] == "not_observed":
                event["result"] = "budget_blocked"

    report: dict[str, Any] = {
        "schema_version": 1,
        "mode": mode,
        "synthetic": mode == "mock",
        "complete": bool(complete),
        "limit_reached": bool(limit_reached),
        "llm_responses_observed": observed_ai,
        "tool_calls_requested": total_requested,
        "tool_results_observed": total_executed,
        "events": events,
        "events_truncated": truncated,
        "usage_available": usage_found,
        "input_tokens_observed": input_tokens if usage_found else None,
        "output_tokens_observed": output_tokens if usage_found else None,
        "duration_ms": round(max(0.0, duration_ms), 1) if isinstance(duration_ms, (float, int)) else None,
        "error_code": _label(error_code) if error_code else None,
    }
    return report
