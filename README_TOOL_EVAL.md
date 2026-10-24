# ResearchFlow V0.4 - Agent Tool Calling evaluation (offline-first)

## What this patch adds

- `src/researchflow/tool_eval.py`: a fixed-case evaluator with an isolated LangGraph run for each case
- `eval/tool_cases.jsonl`: six deterministic cases (GitHub, web search, no tool, GitHub failure, web search failure, tool budget exceeded)
- `tests/test_tool_eval_core.py`: input validation and trustworthy metric denominators
- `tests/test_tool_eval_integration.py`: integration checks using **scripted mock models only**

This patch **only adds files**. It does not change `providers.py`, `tool_agent.py`, `tool_cli.py`, `.env` or the existing SQLite database.

## Install from project root

1. Create a feature branch from the clean V0.3 commit:
   `git switch -c feat/tool-evaluation`
2. Extract the patch ZIP into the project root:
   `unzip -o ~/Downloads/researchflow-tool-eval-v04.zip -d .`
3. Run `python -m pytest -q` and `python -m researchflow.tool_eval --mode mock`.
4. The JSON report is written to `eval/results/tool_eval.json`. Do NOT commit generated reports unless you intentionally wish to publish test artifacts.

Add `eval/results/` to `.gitignore` (for example, `printf '\neval/results/\n' >> .gitignore`).

## Evaluation scenarios

| Scenario | What it validates | Real model called? |
| --- | --- | --- |
| github_metadata | tool call routing to GitHub | No (mock mode) |
| web_docs | tool call routing to web search | No |
| no_external_tool | LLM choosing to answer without a tool | No |
| github_provider_failure | error returned as safe tool JSON | No |
| web_provider_failure | timeout converted to safe tool error | No |
| budget_overflow_blocked | two requested calls blocked when budget=1 | No |

### Metrics

- `tool_selection_accuracy_pct`: exact requested-tool-name sequence match for **normal/no_tool only**; **does not** measure real LLM tool-choice intelligence in mock mode.
- `case_pass_rate_pct`: passing among cases that actually ran. API/runtime errors are reported separately and excluded from this denominator.
- `fault_handling_passed/total`: simulated tool exceptions produce expected error codes.
- `budget_guard_passed/total`: budget overflow prevented tool execution, not just logged a warning.
- `requested`: model emitted requests; `executed`: actual ToolMessages. This distinction matters when the budget stops requests.

The scripted mock policy is fixed. 100% simulated selection accuracy is an **engineering smoke test**, not a generalization estimate or a resume-worthy accuracy claim.

### Optional live evaluation, after GLM is available

`python -m researchflow.tool_eval --mode live --max-cases 1`

The CLI intentionally defaults to **one** live case, with no injected failure scenarios. It may call the configured `glm-4.7-flash` model and public GitHub/Tavily tools. You need valid provider credentials and sufficient service capacity. Model overload (`429 / 1305`) will be recorded as `MODEL_BUSY`, not as a wrong tool selection. Check costs/quotas before expanding the dataset.

Do not put API keys in the JSONL cases; do not publish private questions or provider responses.

## Validation checklist

```bash
python -m compileall -q src/researchflow
python -m pytest -q
python -m researchflow.tool_eval --mode mock
python -m json.tool eval/results/tool_eval.json > /dev/null
```

**Suggested next phase:** build a manually labeled, more diverse real-model evaluation dataset (30-50 cases, including ambiguous queries) and run it only when the free API is stable. Include the dataset source, evaluation criteria, error cases and honest denominators in the portfolio write-up.
