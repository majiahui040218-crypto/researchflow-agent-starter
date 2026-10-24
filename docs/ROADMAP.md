# 4-week roadmap (adjust based on time and API access)

## Week 1: fundamentals and v0.1 baseline

Study only what is used: prompts/messages, tool calling, `StateGraph`, node/edge, `TypedDict` state, conditional edges. Read `src/researchflow/graph.py` and diagram the execution steps. Run mock CLI/API + tests. Get one live task working after configuring valid keys.

**Acceptance:** end-to-end flow runs; 1 question yields saved report and sources; changing source snippets changes generated answer; the loop always respects MAX_SEARCHES.

## Week 2: evidence reliability (your first differentiator)

Replace snippets-only knowledge with vetted source content extraction, caching, domain controls, dedup by canonical URL/content fingerprint, source timestamps, and per-claim evidence checks. Add a counterexample that contains an instruction-injection inside a retrieved snippet; demonstrate that source content remains untrusted data.

**Acceptance:** 20 fixed examples with expected source IDs; no nonexistent IDs pass validation; mark unsupported claims explicitly; document at least three failure cases.

## Week 3: engineering improvements

Add tool call timeouts/retries with exponential backoff, structured tracing, actual token/cost counters (using model metadata where available), endpoint authentication/rate limits if publicly hosted, and an async task queue for longer work. Avoid unbounded concurrency and long synchronous HTTP requests. Use a real checkpointer and verify restart/recovery.

**Acceptance:** recoverable failure tests, a configured cost/search budget, persisted tasks across process restart, and clean logs with secrets excluded.

## Week 4: evaluation, demo and resume packaging

Create 30-50 domain-specific evaluation tasks. Separate retrieval relevance, report factual support, refusal/uncertainty, task completion, latency, and cost. Run A/B comparisons at the same model, budget, dataset, and search provider. Annotate the correct evidence in a portion of cases; manually inspect a random sample for factual support.

**Acceptance:** versioned dataset, benchmark script, baseline vs changed system table, a one-click demo, README architecture diagram, setup instructions, failure analysis, and an honest resume entry with measured outcomes.

## Explicitly postponed

- Multi-agent supervisor / subagents: only add if task decomposition measurably improves results.
- Graph-RAG or a vector DB: not necessary for public web research MVP.
- MCP: useful as a later enhancement once the basic tool interface is stable.
- React frontend: optional after core backend and evaluation are reliable.

## Suggested interview questions

1. Why use LangGraph rather than direct sequential Python functions?
2. What state is persisted and how does `thread_id` relate to tasks?
3. How do you prevent recursive search calls from running forever?
4. Does a valid citation ID prove a claim is true? What extra checks are necessary?
5. How do you distinguish retrieval quality improvements from simply using a better LLM?
6. What changes for many concurrent users and slower tasks?
7. How do you handle malicious text in retrieved content?
