# ResearchFlow Agent Starter

A beginner-friendly LangGraph implementation of a **source-traceable technical research workflow** for an AI Agent internship portfolio. Built as an independent teaching scaffold; not a fork of DeepAgents.

## Features in this starter (v0.1)

- Real LangGraph `StateGraph` with `plan -> search -> reflect -> write -> validate` and conditional search loop.
- OpenAI model (via `langchain-openai`) and Tavily search in live mode.
- Offline mock mode requiring no API keys; **its data is synthetic, not factual**.
- Search budget hard limit (default 3, max 5 searches per task).
- Search result URL deduplication, stable source IDs, and unknown citation-ID detection.
- SQLite graph checkpoints keyed by task ID.
- Synchronous FastAPI endpoint, GET by task ID, and CLI.
- Unit tests and simple engineering evaluation CSV export.

**What v0.1 does NOT do:** semantic fact verification; full-page trusted content fetching; async queue, long-running tasks, frontend, human approvals, safe web navigation, MCP, or multi-agent collaboration. Citation-ID validation alone does not prove a claim is supported by its source.

## Requirements

- Python 3.11+ (3.11 or 3.12 is a conservative choice)
- macOS/Linux/Windows
- Internet plus provider credentials for **live** mode only

## Install and run offline demo

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
python -m researchflow.cli 'Compare LangGraph and CrewAI in Python'
```

In the default `RESEARCHFLOW_MODE=mock` configuration, both the planning and search providers use deterministic demo content. The demo verifies the flow; it does not investigate actual websites.

## Run with real model and web search

Edit `.env` to include:

```dotenv
RESEARCHFLOW_MODE=live
OPENAI_API_KEY=your_actual_openai_api_key
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY=your_actual_tavily_api_key
RESEARCHFLOW_MAX_SEARCHES=3
```

Never commit `.env` or API keys. You need valid API credentials and sufficient quota. Provider API calls may incur charges. Live mode uses two kinds of external services: OpenAI model calls and Tavily web search. Query quality and provider latency vary.

Test from CLI:

```bash
python -m researchflow.cli 'Compare LangGraph and CrewAI: architecture and tradeoffs'
```

## API demo

```bash
uvicorn researchflow.api:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```bash
curl -s http://127.0.0.1:8000/health
curl -s -X POST http://127.0.0.1:8000/research \
  -H 'Content-Type: application/json' \
  -d '{"question": "Compare LangGraph and CrewAI for Python developers"}'
```

The `POST /research` response returns a UUID task ID, report, source records, search count, and warnings. Use `GET /research/{task_id}` to retrieve the saved result. This is a **blocking synchronous demo endpoint**, NOT a background job queue. A long search may cause a client timeout; job queues and async processing are later enhancements.

## Tests

```bash
python -m pytest -q
python eval/run_eval.py
```

The evaluation CSV is written to `reports/engineering_eval.csv`; it reports latency, tool-call count, and citation-ID errors. **These metrics are not evidence accuracy scores.** To measure answer correctness or evidence support, build an independently annotated dataset and conduct human/LLM-as-judge evaluation with manual spot checks.

## Agent flow

```text
START -> plan -> search -> reflect --more_needed--> search
                            |
                            +--done--> write -> validate -> END
```

- `plan`: LLM proposes up to two targeted queries.
- `search`: one tool call per graph step; assign stable citation IDs after deduplication.
- `reflect`: continue queued searches; optionally plan a final follow-up; hard budget prevents infinite loops.
- `write`: generate a Markdown report using supplied snippets and source IDs.
- `validate`: detect unknown `[S<number>]` citations; report warnings rather than claiming semantic correctness.

For a real portfolio, improve this starter to support trustworthy source content, evidence-level validation, retry/backoff, precise cost monitoring, and a fixed test set with manually annotated expected evidence.

## File layout

```text
src/researchflow/
  config.py       Environment variables and provider mode
  schemas.py      ResearchState, source normalization, citation checks
  providers.py    Mock / Tavily search and Mock / OpenAI language
  graph.py        LangGraph nodes, edges, conditional loop
  service.py      Run graph and persist to SQLite
  api.py          HTTP endpoints
  cli.py          Command-line entry point
tests/             Unit and graph-level tests
eval/              Example evaluation questions and runner
docs/ROADMAP.md    Learning and interview-oriented milestones
```

## Docs and reference repositories

- https://docs.langchain.com/oss/python/langgraph/quickstart
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/integrations/tools/tavily_search
- https://github.com/langchain-ai/langgraph-101
- https://github.com/langchain-ai/deepagents

This starter is deliberately smaller than a full Deep Research platform so that a Python developer new to LangGraph can understand every function and discuss personal contributions at an interview.
