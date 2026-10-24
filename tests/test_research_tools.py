"""All Tool Calling tests are offline; no GLM, Tavily, or GitHub API calls."""

import json
import pytest

pytest.importorskip("langchain_core")

from researchflow.research_tools import build_research_tools, _validate_repo


class FakeSearch:
    def search(self, query):
        return [{"title": "Test search", "url": "https://example.test/docs", "snippet": "synthetic"}]


def test_repo_slug_validation():
    assert _validate_repo("langchain-ai/langgraph")
    assert not _validate_repo("https://github.com/langchain-ai/langgraph")
    assert not _validate_repo("../../etc/passwd")
    assert not _validate_repo("foo/bar/baz")


def test_mock_search_contains_explicit_demo_flag():
    tools = {x.name: x for x in build_research_tools("mock", search_provider=FakeSearch())}
    data = json.loads(tools["web_search"].invoke({"query": "LangGraph quickstart"}))
    assert data["demo"] is True
    assert data["results"][0]["url"] == "https://example.test/docs"


def test_repo_tool_uses_injected_fetcher_not_network():
    calls = []
    def fake_fetch(repository):
        calls.append(repository)
        return {"repository": repository, "stars": 17}
    tools = {x.name: x for x in build_research_tools("live", search_provider=FakeSearch(), github_fetch=fake_fetch)}
    response = json.loads(tools["github_repo_info"].invoke({"repository": "langchain-ai/langgraph"}))
    assert response["repository"]["stars"] == 17
    assert calls == ["langchain-ai/langgraph"]


def test_invalid_repo_does_not_call_fetcher():
    def impossible_fetch(repository):
        raise AssertionError("Never query an unsafe repository")
    tools = {x.name: x for x in build_research_tools("live", search_provider=FakeSearch(), github_fetch=impossible_fetch)}
    response = json.loads(tools["github_repo_info"].invoke({"repository": "https://example.com/secret"}))
    assert response["error"] == "INVALID_REPOSITORY"
