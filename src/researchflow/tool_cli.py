"""Optional tool-calling demo. Original `python -m researchflow.cli` is unchanged.

Usage:
  python -m researchflow.tool_cli --mode mock "介绍 LangGraph GitHub 仓库"
  python -m researchflow.tool_cli --mode live "介绍 LangGraph GitHub 仓库"
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid

# Use the same serialization safety setting as the existing research service.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver

from .providers import OpenAILanguage, ProviderCallError, _provider_error
from .task_store import create_task, finish_task
from .tool_agent import build_tool_agent
from .research_tools import build_research_tools


class ScriptedDemoModel:
    """Deterministic TEST DOUBLE, not a live LLM making tool-use decisions."""

    def bind_tools(self, tools):
        self._names = {tool.name for tool in tools}
        return self

    def invoke(self, messages):
        last = messages[-1]
        if isinstance(last, ToolMessage):
            return AIMessage(content=(
                "# DEMO ONLY - Tool Calling 流程模拟成功\n\n"
                "本次是脚本模型产生的工具调用，不是真实 LLM 自主决策。\n"
                "工具结果仅用于演示：\n\n" + str(last.content)[:1200]
            ))
        question = " ".join(str(m.content) for m in messages if isinstance(m, HumanMessage))
        if any(marker in question.lower() for marker in ("github", "仓库", "star", "fork")):
            name, args = "github_repo_info", {"repository": "langchain-ai/langgraph"}
        else:
            name, args = "web_search", {"query": question[:200]}
        if name not in self._names:
            raise RuntimeError("Scripted tool is not configured")
        return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": "demo_call_1"}])


def run_tool_task(question: str, *, mode: str = "mock", settings=None, model=None, tools=None):
    """Save terminal task outcome; expose injection points for offline tests."""
    from .config import Settings

    load_dotenv()
    settings = settings or Settings.from_env(require_live_keys=False)
    question = question.strip()
    if not 5 <= len(question) <= 500:
        raise ValueError("Question length must be between 5 and 500 characters")
    if mode not in {"mock", "live"}:
        raise ValueError("mode must be mock or live")

    task_id = str(uuid.uuid4())
    state = {"question": question, "report": "", "warnings": [], "attempts": 0}
    create_task(settings.db_path, task_id, mode, question, state)

    language = None
    try:
        if model is None:
            if mode == "mock":
                model = ScriptedDemoModel()
            else:
                missing = [key for key in ("OPENAI_API_KEY", "TAVILY_API_KEY") if not os.getenv(key)]
                if missing:
                    raise ValueError("Missing required API credentials for live tool mode")
                language = OpenAILanguage(settings.model)
                model = language._model
        if tools is None:
            tools = build_research_tools(mode)

        with SqliteSaver.from_conn_string(str(settings.db_path)) as checkpointer:
            graph = build_tool_agent(model, tools, max_tool_calls=3).compile(checkpointer=checkpointer)
            result = graph.invoke(
                {"messages": [HumanMessage(content=question)], "tool_calls_used": 0, "limit_reached": False},
                config={"configurable": {"thread_id": task_id}, "recursion_limit": 16},
            )

        final = result["messages"][-1]
        answer = str(final.content) if isinstance(final, AIMessage) else ""
        trace = []
        for message in result["messages"]:
            if isinstance(message, AIMessage) and message.tool_calls:
                trace.extend(str(call["name"]) for call in message.tool_calls)
        state = {
            "question": question,
            "report": answer,
            "attempts": result.get("tool_calls_used", 0),
            "tool_names": trace,
            "warnings": (["DEMO MODE: All tool results are synthetic."] if mode == "mock" else [])
            + (["Tool budget reached; pending tool calls were not executed."] if result.get("limit_reached") else []),
        }
        finish_task(settings.db_path, task_id, "completed", state)
        return {"task_id": task_id, "mode": mode, "status": "completed", **state}

    except Exception as exc:
        if isinstance(exc, ProviderCallError):
            failure = exc
        elif isinstance(exc, ValueError) and str(exc).startswith("Missing required API credentials"):
            failure = ProviderCallError("CONFIG_MISSING", "Live 模式缺少模型或搜索 API Key")
        else:
            failure = _provider_error(exc)
        failed = {"question": question, "report": "", "warnings": [f"Task failed: {failure.code}"]}
        finish_task(settings.db_path, task_id, "failed", failed, failure.code, str(failure))
        return {"task_id": task_id, "mode": mode, "status": "failed", "error_code": failure.code,
                "error_message": str(failure), **failed}
    finally:
        if language is not None:
            language.close()


def main():
    parser = argparse.ArgumentParser(description="ResearchFlow isolated Tool Calling example")
    parser.add_argument("question", help="What would you like to research?")
    parser.add_argument("--mode", choices=("mock", "live"), default="mock")
    args = parser.parse_args()
    result = run_tool_task(args.question, mode=args.mode)
    print(f"Mode: {result['mode']}; task_id: {result['task_id']}; status: {result['status']}")
    if result["status"] == "failed":
        print(f"Error: {result['error_code']}: {result['error_message']}")
        sys.exit(1)
    print(result["report"])
    print(f"\nTool calls executed: {result['attempts']}; selected: {result['tool_names']}")
    for warning in result["warnings"]:
        print("Warning:", warning)


if __name__ == "__main__":
    main()
