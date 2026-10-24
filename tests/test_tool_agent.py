"""Deterministic tests for graph routing and tool budget; no API calls."""

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langchain_core")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from researchflow.research_tools import build_research_tools
from researchflow.tool_agent import build_tool_agent
from researchflow.tool_cli import ScriptedDemoModel


class FakeSearch:
    def search(self, query):
        return [{"title": "Mock result", "url": "https://example.com/data", "snippet": "synthetic"}]


def test_scripted_demo_makes_one_tool_call():
    tools = build_research_tools("mock", search_provider=FakeSearch())
    graph = build_tool_agent(ScriptedDemoModel(), tools, max_tool_calls=2).compile()
    state = graph.invoke({"messages": [HumanMessage(content="请检查 GitHub 仓库")], "tool_calls_used": 0})
    assert state["tool_calls_used"] == 1
    assert any(isinstance(x, ToolMessage) for x in state["messages"])
    assert "DEMO ONLY" in state["messages"][-1].content
    assert not state.get("limit_reached", False)


def test_tool_budget_prevents_execution():
    class GreedyModel:
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            return AIMessage(content="", tool_calls=[
                {"name": "web_search", "args": {"query": "query one"}, "id": "call_1"},
                {"name": "web_search", "args": {"query": "query two"}, "id": "call_2"},
            ])

    class NeverSearch:
        def search(self, query):
            raise AssertionError("Tools must not run when call budget is exceeded")

    tools = build_research_tools("mock", search_provider=NeverSearch())
    graph = build_tool_agent(GreedyModel(), tools, max_tool_calls=1).compile()
    state = graph.invoke({"messages": [HumanMessage(content="test")], "tool_calls_used": 0})
    assert state["tool_calls_used"] == 0
    assert state["limit_reached"] is True
    assert not any(isinstance(x, ToolMessage) for x in state["messages"])


def test_model_without_tool_call_finishes():
    class NoToolsModel:
        def bind_tools(self, tools):
            return self
        def invoke(self, messages):
            return AIMessage(content="No tools needed")

    graph = build_tool_agent(NoToolsModel(), build_research_tools("mock"), max_tool_calls=1).compile()
    state = graph.invoke({"messages": [HumanMessage(content="hello")], "tool_calls_used": 0})
    assert state["messages"][-1].content == "No tools needed"
    assert state["tool_calls_used"] == 0
