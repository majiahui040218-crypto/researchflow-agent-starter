from researchflow.schemas import canonical_url, invalid_citations, merge_sources, used_citations


def test_source_dedup_and_stable_ids():
    inputs = [
        {"title": "A", "url": "https://example.org/doc?utm_source=ad", "snippet": "note"},
        {"title": "duplicate", "url": "https://example.org/doc", "snippet": "same page"},
        {"title": "B", "url": "https://example.org/other", "snippet": "new page"},
    ]
    rows = merge_sources([], inputs, "original query")
    assert [s["id"] for s in rows] == ["S1", "S2"]
    assert [s["url"] for s in rows] == ["https://example.org/doc", "https://example.org/other"]
    assert len(merge_sources(rows, inputs, "retry")) == 2


def test_rejects_invalid_urls():
    assert canonical_url("file:///etc/passwd") == ""
    assert canonical_url("javascript:alert(1)") == ""
    assert canonical_url("https://example.org/path#section") == "https://example.org/path"


def test_citation_validation():
    sources = [{"id": "S1", "url": "https://example.org", "title": "One", "snippet": "", "query": ""}]
    report = "Statement [S1] other statement [S9]."
    assert invalid_citations(report, sources) == ["S9"]
    assert used_citations(report) == {"S1", "S9"}
