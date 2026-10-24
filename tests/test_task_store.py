"""Task status persistence uses only the standard library and SQLite."""

import sqlite3
from researchflow.task_store import create_task, finish_task, read_task


def test_complete_task(tmp_path):
    db = tmp_path / "status.sqlite"
    initial = {"question": "Compare frameworks", "report": ""}
    create_task(db, "task-1", "mock", initial["question"], initial)
    assert read_task(db, "task-1")["status"] == "running"
    finished = {**initial, "report": "Done [S1]"}
    finish_task(db, "task-1", "completed", finished)
    row = read_task(db, "task-1")
    assert row["status"] == "completed"
    assert row["state"]["report"] == "Done [S1]"
    assert row["created_at"] and row["updated_at"]
    assert row["error_code"] is None


def test_failed_task_is_queryable(tmp_path):
    db = tmp_path / "status.sqlite"
    create_task(db, "task-2", "live", "question", {"question": "question"})
    finish_task(db, "task-2", "failed", {"question": "question"},
                "MODEL_BUSY", "模型忙，请稍后重试")
    row = read_task(db, "task-2")
    assert row["status"] == "failed"
    assert row["error_code"] == "MODEL_BUSY"
    assert row["error_message"] == "模型忙，请稍后重试"


def test_old_checkpoint_only_database(tmp_path):
    db = tmp_path / "old.sqlite"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE writes (test TEXT)")
    assert read_task(db, "missing") is None


def test_rejects_nonterminal_status(tmp_path):
    from pytest import raises
    db = tmp_path / "status.sqlite"
    create_task(db, "task-3", "mock", "question", {"question": "question"})
    with raises(ValueError):
        finish_task(db, "task-3", "running", {})
