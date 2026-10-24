"""Inspect persisted, sanitized tool traces without executing any API calls.

Example:
    python -m researchflow.tool_trace_cli --task-id <uuid>
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv
from .task_store import read_task


def read_tool_trace(task_id: str, db_path: Path) -> dict | None:
    uuid.UUID(task_id)  # fail fast on invalid IDs
    record = read_task(db_path, task_id)
    if record is None:
        return None
    return {
        "task_id": record["task_id"],
        "status": record["status"],
        "mode": record["mode"],
        "error_code": record["error_code"],
        "trace": record["state"].get("tool_trace"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read an existing ResearchFlow tool trace")
    parser.add_argument("--task-id", required=True, help="UUID returned by tool_cli")
    parser.add_argument("--db", type=Path, help="Override SQLite database path")
    args = parser.parse_args(argv)
    load_dotenv()
    db_path = args.db or Path(os.getenv("RESEARCHFLOW_DB", ".data/researchflow.sqlite"))
    try:
        record = read_tool_trace(args.task_id, db_path)
    except ValueError:
        parser.error("--task-id must be a valid UUID")
    if record is None:
        print("Task not found in database")
        return 1
    if record["trace"] is None:
        print("This task predates V0.5 or no trace was captured")
        return 1
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
