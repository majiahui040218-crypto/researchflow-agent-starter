"""Types and basic validation for search evidence and graph state."""

import re
from typing import TypedDict
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, Field


class Source(TypedDict):
    id: str
    title: str
    url: str
    snippet: str
    query: str


class ResearchState(TypedDict, total=False):
    question: str
    queue: list[str]
    next_query: str
    tried_queries: list[str]
    sources: list[Source]
    attempts: int
    budget: int
    keep_searching: bool
    report: str
    warnings: list[str]
    invalid_citations: list[str]


class SearchPlan(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=4)


class ResearchReview(BaseModel):
    needs_more_search: bool
    followup_query: str = ""
    rationale: str = ""


_CITATION = re.compile(r"\[(S\d+)\]")
_TRACKING = {"fbclid", "gclid", "mc_cid", "mc_eid"}


def canonical_url(url: str) -> str:
    """Normalize a URL for search-result deduplication, not for fetching."""
    try:
        parts = urlsplit(url.strip())
        if parts.scheme.lower() not in {"http", "https"} or not parts.netloc:
            return ""
        query = urlencode([
            (key, value) for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if not key.lower().startswith("utm_") and key.lower() not in _TRACKING
        ])
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", query, ""))
    except ValueError:
        return ""


def merge_sources(existing: list[Source], results: list[dict], query: str) -> list[Source]:
    """Keep first appearance of each URL; assign monotonically increasing source IDs."""
    output = list(existing)
    seen = {canonical_url(row["url"]) for row in existing}
    for row in results:
        if not isinstance(row, dict):
            continue
        url = canonical_url(str(row.get("url", "")))
        if not url or url in seen:
            continue
        seen.add(url)
        output.append(
            {
                "id": f"S{len(output) + 1}",
                "title": str(row.get("title", "Untitled"))[:180],
                "url": url,
                "snippet": str(row.get("snippet", row.get("content", "")))[:1800],
                "query": query[:300],
            }
        )
    return output


def invalid_citations(report: str, sources: list[Source]) -> list[str]:
    """Syntactic citation check only; does NOT prove factual support."""
    allowed = {row["id"] for row in sources}
    return sorted(set(_CITATION.findall(report)) - allowed)


def used_citations(report: str) -> set[str]:
    return set(_CITATION.findall(report))
