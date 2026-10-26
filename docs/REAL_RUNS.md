cat > docs/REAL_RUNS.md <<'EOF'
# Real LLM Tool Calling Verification

Date: 2026-10-26
Provider: USTC OpenAI-compatible API
Model: qwen3.8-chat

## Test A: Web Search

- Task ID: 554b6a46-98f4-4cf2-90df-4f6889b97eb0
- Mode: live
- Status: completed
- Synthetic: false
- Tool: web_search
- Tool calls requested: 1
- Tool results observed: 1
- Duration: 12339.4 ms
- Input tokens observed: 2819
- Output tokens observed: 648
- Trace complete: true

## Test B: GitHub Repository Lookup

- Task ID: f099518a-5e3d-48a9-936f-0a4988262185
- Mode: live
- Status: completed
- Synthetic: false
- Tool: github_repo_info
- Tool calls requested: 1
- Tool results observed: 1
- Duration: 4554.1 ms
- Input tokens observed: 1142
- Output tokens observed: 159
- Trace complete: true

## Notes

These are two successful live execution samples, not a
statistical reliability benchmark. Latency and token usage
may vary across runs. No API keys are stored in this report.
EOF