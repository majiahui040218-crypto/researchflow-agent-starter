"""Read-only LangChain tools for the optional Tool Calling agent.

Demo tools contain only synthetic records and never access the network.
Live tools retrieve public sources; retrieved content must be treated as untrusted data.
"""

from __future__ import annotations

import json
import re
from typing import Callable

from langchain_core.tools import tool

from .providers import MockSearch, TavilyProvider

_REPO = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{0,38}/[A-Za-z0-9_.-]{1,100}$")


def _validate_repo(repository: str) -> bool:
    """Only accept an owner/repository slug; reject URLs and path traversal."""
    if not isinstance(repository, str) or not _REPO.fullmatch(repository):
        return False
    owner, name = repository.split("/", 1)
    return not owner.endswith("-") and name not in {".", ".."}


def fetch_github_repo(repository: str) -> dict:
    """Query one fixed public GitHub REST endpoint (no arbitrary URLs)."""
    if not _validate_repo(repository):
        raise ValueError("Expected a public GitHub repository in owner/repository format")

    import httpx2

    with httpx2.Client(
        transport=httpx2.HTTPTransport(local_address="0.0.0.0"),
        trust_env=False,
        timeout=15.0,
        follow_redirects=False,
    ) as client:
        response = client.get(
            f"https://api.github.com/repos/{repository}",
            headers={"Accept": "application/vnd.github+json", "User-Agent": "researchflow-agent-demo"},
        )
        response.raise_for_status()
        data = response.json()

    if not isinstance(data, dict) or "full_name" not in data:
        raise ValueError("Unexpected GitHub API response")
    return {
        "repository": str(data.get("full_name", repository))[:150],
        "description": str(data.get("description") or "")[:500],
        "language": data.get("language"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "archived": bool(data.get("archived", False)),
        "url": data.get("html_url"),
        "updated_at": data.get("updated_at"),
    }


def build_research_tools(
    mode: str,
    *,
    search_provider=None,
    github_fetch: Callable[[str], dict] | None = None,
):
    """Build tools with dependency injection so all tests can avoid network calls."""
    if mode not in {"mock", "live"}:
        raise ValueError("mode must be mock or live")
    searcher = search_provider or (MockSearch() if mode == "mock" else TavilyProvider())

    if github_fetch is None:
        if mode == "mock":
            github_fetch = lambda repository: {
                "demo": True,
                "repository": repository,
                "description": "SYNTHETIC DEMO: No GitHub API was called.",
                "stars": None,
                "forks": None,
                "url": "https://example.com/mock-github-repo",
            }
        else:
            github_fetch = fetch_github_repo

    @tool
    def web_search(query: str) -> str:
        """Search public technical documentation. Input is a short search query."""
        query = query.strip() if isinstance(query, str) else ""
        if not 2 <= len(query) <= 250:
            return json.dumps({"error": "INVALID_QUERY", "results": []})
        try:
            raw = searcher.search(query)
        except Exception:
            # Do not expose the raw provider exception; it could contain credentials.
            return json.dumps({"error": "SEARCH_FAILED", "results": []})
        records = []
        for item in raw[:3] if isinstance(raw, list) else []:
            if not isinstance(item, dict):
                continue
            records.append({
                "title": str(item.get("title", ""))[:150],
                "url": str(item.get("url", ""))[:500],
                "snippet": str(item.get("snippet", item.get("content", "")))[:900],
            })
        return json.dumps({"mode": mode, "demo": mode == "mock", "results": records}, ensure_ascii=False)

    @tool
    def github_repo_info(repository: str) -> str:
        """Read public GitHub repository metadata; argument format is owner/repository."""
        if not _validate_repo(repository):
            return json.dumps({"error": "INVALID_REPOSITORY"})
        try:
            info = github_fetch(repository)
        except Exception:
            return json.dumps({"error": "GITHUB_REQUEST_FAILED"})
        if not isinstance(info, dict):
            return json.dumps({"error": "GITHUB_INVALID_RESPONSE"})
        return json.dumps({"mode": mode, "demo": mode == "mock", "repository": info}, ensure_ascii=False)

    return [web_search, github_repo_info]
