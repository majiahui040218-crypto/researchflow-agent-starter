"""Durable task outcomes, separate from LangGraph's execution checkpoints.

Only short, curated provider error codes/messages are stored. Never persist
raw exception text because it can include authorization headers or URLs.
"""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from typing import Any


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(str(path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def _prepare(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(_connect(path)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS researchflow_task_runs (
                task_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                question TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT NOT NULL,
                error_code TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )


def create_task(path: Path, task_id: str, mode: str, question: str, state: dict[str, Any]) -> None:
    """Record intent before making any external network calls."""
    _prepare(path)
    stamp = _utc_now()
    with closing(_connect(path)) as connection, connection:
        connection.execute(
            """
            INSERT INTO researchflow_task_runs
                (task_id, mode, question, status, state_json, created_at, updated_at)
            VALUES (?, ?, ?, 'running', ?, ?, ?)
            """,
            (task_id, mode, question, json.dumps(state, ensure_ascii=False), stamp, stamp),
        )


def finish_task(
    path: Path,
    task_id: str,
    status: str,
    state: dict[str, Any],
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    if status not in {"completed", "failed"}:
        raise ValueError("Final status must be 'completed' or 'failed'")
    with closing(_connect(path)) as connection, connection:
        cursor = connection.execute(
            """
            UPDATE researchflow_task_runs
               SET status=?, state_json=?, error_code=?, error_message=?, updated_at=?
             WHERE task_id=?
            """,
            (
                status,
                json.dumps(state, ensure_ascii=False),
                error_code,
                error_message,
                _utc_now(),
                task_id,
            ),
        )
        if cursor.rowcount != 1:
            raise LookupError("Cannot finish a task that has not been recorded")


def read_task(path: Path, task_id: str) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    with closing(_connect(path)) as connection:
        try:
            row = connection.execute(
                "SELECT * FROM researchflow_task_runs WHERE task_id=?", (task_id,)
            ).fetchone()
        except sqlite3.OperationalError as exc:
            # Backward compatibility: an old checkpoint-only database has no task table.
            if "no such table" in str(exc).lower():
                return None
            raise
    if row is None:
        return None
    return {
        "task_id": row["task_id"],
        "question": row["question"],
        "mode": row["mode"],
        "status": row["status"],
        "state": json.loads(row["state_json"]),
        "error_code": row["error_code"],
        "error_message": row["error_message"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
