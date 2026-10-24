"""Simple engineering metrics only; do not mistake them for factuality scores."""

import csv
import json
from pathlib import Path
from time import perf_counter

from researchflow.service import run_research


def main() -> None:
    dataset = Path(__file__).with_name("questions.jsonl")
    output_dir = Path("reports")
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "engineering_eval.csv"
    rows = []
    for line in dataset.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        start = perf_counter()
        try:
            result = run_research(item["question"]).as_dict()
            rows.append({
                "id": item["id"],
                "success": True,
                "elapsed_sec": round(perf_counter() - start, 3),
                "source_count": len(result["sources"]),
                "search_count": result["search_count"],
                "unknown_citation_count": len(result["invalid_citations"]),
                "mode": result["mode"],
                "error": "",
            })
        except Exception as exc:
            rows.append({
                "id": item["id"], "success": False,
                "elapsed_sec": round(perf_counter() - start, 3),
                "source_count": 0, "search_count": 0,
                "unknown_citation_count": 0,
                "mode": "error", "error": type(exc).__name__,
            })
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} evaluations to {out}")
    print("WARNING: Engineering metrics do NOT evaluate source relevance or factual accuracy.")


if __name__ == "__main__":
    main()
