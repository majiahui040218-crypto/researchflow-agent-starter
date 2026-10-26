# ResearchFlow Agent

[中文说明](README.zh-CN.md) · [Architecture](docs/ARCHITECTURE.md) · [Tool calling guide](README_TOOL_CALLING.md) · [Tool evaluation](README_TOOL_EVAL.md) · [Trace guide](README_TOOL_TRACE.md)

A small but working **LangGraph research agent** with two separate execution paths: a planning/search/report workflow, and an LLM-driven tool-calling agent. Designed to be understandable, testable, and safe to demonstrate in an AI Agent engineering internship interview.

> **Evidence boundary:** Mock runs use synthetic scripted data. One **real** `qwen3.8-chat` + GitHub tool-calling run was completed and traced on 2026-10-26. This does **not** establish reliability, accuracy, or latency percentiles across runs.

## What is implemented

- **Research graph:** `plan → search → reflect → write → validate` with a search budget.
- **Tool agent:** LangGraph `bind_tools` + `ToolNode`; tool selection by the LLM in live mode, deterministic scripted selection in mock mode; per-task tool-call budget.
- **Read-only tools:** `github_repo_info(owner/repo)` and `web_search(query)`.
- **Durability:** SQLite checkpoints and terminal task records (success/failure).
- **Observability:** queryable execution trace: model responses observed, tool requests/results, safe argument *names* (not values), available token usage, duration, error category.
- **Evaluation:** scripted, offline tool-selection/fault/budget cases; results explicitly marked as mock, **not** real LLM accuracy.
- **CI:** GitHub Actions runs offline tests and scripted smoke checks; **no API secrets or model calls**.
- **Configuration doctor:** a local CLI surfaces shell-versus-`.env` differences without printing API keys.

## Run locally

Use Python 3.12 (3.11+ is declared in `pyproject.toml`):

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python -m researchflow.config_doctor
python -m pytest -q
python -m researchflow.tool_cli --mode mock '查询 LangGraph 的 GitHub 仓库信息'
python -m researchflow.tool_eval --mode mock
```

The `mock` mode does **not** call an LLM or GitHub and must never be reported as real-world research performance.

### Live OpenAI-compatible model

Set `.env` with credentials and a model ID actually available to your provider:

```dotenv
RESEARCHFLOW_MODE=live
OPENAI_BASE_URL=https://api.llm.ustc.edu.cn/v1
OPENAI_MODEL=qwen3.8-chat
OPENAI_API_KEY=YOUR_NEW_KEY
TAVILY_API_KEY=YOUR_NEW_TAVILY_KEY
RESEARCHFLOW_LLM_RETRIES=0
```

These are **examples** from one validated USTC environment, not universal model names or access guarantees. The tool-agent currently initializes both GitHub and Tavily tools, so it expects a Tavily key even for GitHub questions. Live calls may be rate-limited or billed.

Configuration priority is **shell environment > `.env`** (`load_dotenv()` without override). If shell and file disagree, run:

```bash
python -m researchflow.config_doctor
unset OPENAI_MODEL  # only if the doctor reports a stale shell override
```

V0.6 also supports an optional explicit model HTTP proxy:

```dotenv
# RESEARCHFLOW_HTTP_PROXY=http://127.0.0.1:7890
```

Leave it unset if your existing IPv4-direct/TUN route already works. This setting affects **model** requests, not Tavily or GitHub traffic; it does not modify macOS system proxy settings. Do not use `verify=False` to work around TLS issues.

Run exactly one live tool test once configuration is verified:

```bash
python -m researchflow.tool_cli --mode live \
  '请调用 GitHub 工具，查询 langchain-ai/langgraph 仓库的 Stars 和 Forks'
python -m researchflow.tool_trace_cli --task-id YOUR_TASK_UUID
```

Check `mode=live`, `synthetic=false`, and `tool_results_observed >= 1` before claiming real tool execution.

## Observed live validation (one sample)

In a user-run `qwen3.8-chat` test on 2026-10-26, the agent completed a real GitHub repository lookup with **1 tool call, 2 model responses observed, 1 tool result, 1,130 input tokens, 154 output tokens, and 6,553.4 ms task duration**. These are **single-run observations**, not benchmark averages or an SLA. A previous V0.5 local test run returned **50 passed**; V0.6 requires a fresh regression run.

## Security and limitations

- `.env`, SQLite databases, generated evaluation output, and local backups are ignored by Git.
- Traces intentionally omit raw prompt text, argument values, tool result content, and exception bodies.
- Search snippets/tool responses are treated as untrusted external data.
- The current report validator checks unknown citation IDs, **not semantic factual entailment**.
- FastAPI research endpoint is synchronous and not safe for public unauthenticated deployment.
- Provider/model availability and tool-calling support vary; never treat `models.list()` alone as proof of tool calling.

See [Architecture](docs/ARCHITECTURE.md) and [Resume / interview guide](docs/RESUME_GUIDE.md) for design trade-offs and supported claims.
