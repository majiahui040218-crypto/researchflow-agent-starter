"""Research service, with durable success AND failure task records."""

import logging
import os
import uuid
from dataclasses import dataclass

# Treat untrusted checkpoint data as strictly serialized messages.
os.environ.setdefault("LANGGRAPH_STRICT_MSGPACK", "true")

from langgraph.checkpoint.sqlite import SqliteSaver

from .config import Settings
from .graph import build_graph
from .providers import MockLanguage, MockSearch, OpenAILanguage, ProviderCallError, TavilyProvider
from .schemas import ResearchState
from .task_store import create_task, finish_task, read_task

_LOG = logging.getLogger(__name__)


@dataclass
class ResearchResult:
    task_id: str
    state: ResearchState
    mode: str
    status: str = "completed"
    error_code: str | None = None
    error_message: str | None = None

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "mode": self.mode,
            "question": self.state.get("question", ""),
            "report": self.state.get("report", ""),
            "sources": self.state.get("sources", []),
            "search_count": self.state.get("attempts", 0),
            "searched_queries": self.state.get("tried_queries", []),
            "invalid_citations": self.state.get("invalid_citations", []),
            "warnings": self.state.get("warnings", []),
            "error": (
                {"code": self.error_code, "message": self.error_message}
                if self.error_code else None
            ),
        }


def _providers(settings: Settings):
    if settings.mode == "mock":
        return MockLanguage(), MockSearch()
    return OpenAILanguage(settings.model), TavilyProvider()


def run_research(question: str, settings: Settings | None = None) -> ResearchResult:
    settings = settings or Settings.from_env()
    question = question.strip()
    if not 5 <= len(question) <= 500:
        raise ValueError("Question length must be between 5 and 500 characters")

    task_id = str(uuid.uuid4())
    state: ResearchState = {
        "question": question,
        "queue": [],
        "next_query": "",
        "tried_queries": [],
        "sources": [],
        "attempts": 0,
        "budget": settings.max_searches,
        "keep_searching": True,
        "report": "",
        "invalid_citations": [],
        "warnings": ["DEMO MODE: All search records are synthetic."] if settings.mode == "mock" else [],
    }
    # This table is independent of LangGraph's checkpoint tables. A task is
    # visible even when model invocation fails before the first graph checkpoint.
    create_task(settings.db_path, task_id, settings.mode, question, state)

    language = None
    try:
        with SqliteSaver.from_conn_string(str(settings.db_path)) as checkpointer:
            language, searcher = _providers(settings)
            graph = build_graph(language, searcher).compile(checkpointer=checkpointer)
            try:
                final_state = graph.invoke(
                    state,
                    config={"configurable": {"thread_id": task_id}, "recursion_limit": 20},
                )
            except Exception:
                # Preserve the last successful node's state if checkpointing worked.
                try:
                    snapshot = graph.get_state({"configurable": {"thread_id": task_id}})
                    if snapshot and snapshot.values:
                        state = dict(snapshot.values)
                except Exception:
                    _LOG.warning("Checkpoint snapshot unavailable for task %s", task_id)
                raise
        final_state = dict(final_state)
        finish_task(settings.db_path, task_id, "completed", final_state)
        return ResearchResult(task_id, final_state, settings.mode, "completed")
    except Exception as exc:
        if isinstance(exc, ProviderCallError):
            code, message = exc.code, str(exc)
        else:
            # Do not put raw exception messages into API responses or SQLite;
            # providers sometimes include user data or request credentials.
            code, message = "WORKFLOW_FAILED", "研究任务执行失败，请检查服务端日志和任务配置。"
        _LOG.warning("Research task %s failed: code=%s exception_type=%s", task_id, code, type(exc).__name__)
        state = dict(state)
        state["warnings"] = [*state.get("warnings", []), f"Task failed: {code}"]
        finish_task(settings.db_path, task_id, "failed", state, code, message)
        return ResearchResult(task_id, state, settings.mode, "failed", code, message)
    finally:
        if language is not None:
            close = getattr(language, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    _LOG.warning("Unable to close language provider for task %s", task_id)


def load_research(task_id: str, settings: Settings | None = None) -> ResearchResult | None:
    # Read-only status queries must not require an active model API key.
    settings = settings or Settings.from_env(require_live_keys=False)
    try:
        task_id = str(uuid.UUID(task_id))
    except ValueError:
        return None
    record = read_task(settings.db_path, task_id)
    if record is not None:
        return ResearchResult(
            task_id=task_id,
            state=record["state"],
            mode=record["mode"],
            status=record["status"],
            error_code=record["error_code"],
            error_message=record["error_message"],
        )

    # Older versions only stored LangGraph checkpoints. Read them without
    # building a live provider or making network connections.
    if not settings.db_path.is_file():
        return None
    with SqliteSaver.from_conn_string(str(settings.db_path)) as checkpointer:
        graph = build_graph(MockLanguage(), MockSearch()).compile(checkpointer=checkpointer)
        snapshot = graph.get_state({"configurable": {"thread_id": task_id}})
    if not snapshot or not snapshot.values:
        return None
    return ResearchResult(task_id=task_id, state=snapshot.values, mode=settings.mode)
