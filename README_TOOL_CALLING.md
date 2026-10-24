# ResearchFlow Tool Calling V0.3 (optional module)

This patch **only adds new files**, preserving the working research CLI, existing `providers.py`, task store, `.env`, and current 16 tests.

## Apply on your Mac

From `~/Downloads/researchflow-agent-starter`:

```bash
git status --short
git switch -c feat/tool-calling
# If your patch folder is inside the project:
cp -v researchflow-tool-calling-patch/src/researchflow/*.py src/researchflow/
cp -v researchflow-tool-calling-patch/tests/test_*.py tests/
python -m compileall -q src/researchflow
python -m pytest -q
```

If `git switch -c` says the branch exists, use `git switch feat/tool-calling` instead.

## Run offline (no API calls)

```bash
python -m researchflow.tool_cli --mode mock "帮我查询 LangGraph 的 GitHub 仓库"
```

Expected: `Mode: mock`, `status: completed`, a `DEMO ONLY` report, and one executed tool call. A **scripted test double**, not an LLM, chooses the tool in mock mode. All results are synthetic. To query the task history:

```bash
python -m researchflow.cli --task-id <the-UUID-printed-above>
```

## Run live (only after tests pass)

`.env` needs:

```dotenv
OPENAI_API_KEY=YOUR_ZHIPU_API_KEY
OPENAI_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
OPENAI_MODEL=glm-4.7-flash
TAVILY_API_KEY=YOUR_TAVILY_API_KEY
RESEARCHFLOW_LLM_RETRIES=0
```

Then:

```bash
python -m researchflow.tool_cli --mode live "查一下 langchain-ai/langgraph 的 GitHub 仓库信息"
```

Live mode explicitly opts in to API calls; the standard research CLI remains unchanged. GLM 4.7 Flash can support function calling, but model load / account restrictions may still produce 429/1305. GitHub unauthenticated REST requests also have rate limits. Web search consumes Tavily quota. `--mode mock` never queries these APIs.

## Implementation

- `research_tools.py`: `@tool` definitions for read-only public web search and GitHub repository metadata. Strict `owner/repo` validation prevents accepting arbitrary URLs.
- `tool_agent.py`: LangGraph `StateGraph`, model `bind_tools()`, `ToolNode`, conditional routes, max **3 executed tool calls** per task.
- `tool_cli.py`: separate CLI and task persistence into the existing SQLite task table. Does not replace or change `service.py`.
- `test_research_tools.py`, `test_tool_agent.py`, `test_tool_task_status.py`: offline tests. Fake tool choice is scripted and not evidence of real LLM behavior.

The tool result is *untrusted external data*. Syntactic safety and the prompt reduce risks but do not guarantee full resistance to prompt injection. SQLite result persistence is implemented; resuming mid-tool-call is not part of this version.

## Commit after tests

```bash
git add src/researchflow/research_tools.py src/researchflow/tool_agent.py src/researchflow/tool_cli.py tests/test_research_tools.py tests/test_tool_agent.py tests/test_tool_task_status.py
git commit -m "feat: add bounded tool calling research agent"
```

Do not commit `.env`, database files, virtual environments, or downloaded patch folders.
