"""Read task traces from SQLite without requiring LangGraph or API keys."""

from pathlib import Path
import uuid

from researchflow.task_store import create_task, finish_task
from researchflow.tool_trace_cli import read_tool_trace, main


def test_trace_cli_reads_sqlite_record(tmp_path, capsys):
    db = tmp_path / "tasks.sqlite"
    task_id = str(uuid.uuid4())
    create_task(db, task_id, "mock", "demo", {})
    finish_task(db, task_id, "completed", {"tool_trace": {"synthetic": True, "events": []}})
    row = read_tool_trace(task_id, db)
    assert row["trace"]["synthetic"] is True
    result = main(["--task-id", task_id, "--db", str(db)])
    assert result == 0
    assert '"synthetic": true' in capsys.readouterr().out


def test_trace_cli_returns_not_found(tmp_path):
    assert main(["--task-id", str(uuid.uuid4()), "--db", str(tmp_path / "missing.sqlite")]) == 1
