# ResearchFlow V0.5: Observed Tool Trace / 工具调用轨迹

这是基于 V0.4 (`3489a2c` / `feat/tool-evaluation`) 的**增量补丁**，不是独立项目。

## 安装

请先在本地 ResearchFlow 仓库执行：

```bash
git status --short
git switch -c feat/agent-tracing
cp src/researchflow/tool_cli.py src/researchflow/tool_cli.py.v04.bak
unzip -o ~/Downloads/researchflow-tool-trace-v05.zip -d .
python -m compileall -q src/researchflow
python -m pytest -q
```

不要把 `.env`、SQLite `.data/`、模型 Key 或 `.bak` 上传到 GitHub。此补丁不会修改 `.env`、服务 API、原研究 Graph 或数据库 schema，只替换 `tool_cli.py` 并新增 `tool_trace.py`、`tool_trace_cli.py` 和测试文件。

## 离线运行（推荐）

```bash
python -m researchflow.tool_cli --mode mock "帮我查询 LangGraph 的 GitHub 仓库信息"
```

复制输出中的真实 `task_id`，查询轨迹：

```bash
python -m researchflow.tool_trace_cli --task-id <填入刚才的UUID>
```

轨迹直接保存于原 SQLite `researchflow_task_runs.state_json.tool_trace`。不需要修改数据库结构。

输出中的主要字段：

- `synthetic`: `true` 表示脚本模拟，**不是 GLM 的自主选工具能力**。
- `tool_calls_requested`: 模型响应里要求调用的工具数量。
- `tool_results_observed`: 实际看到的 `ToolMessage` 数量；只有得到工具结果，才认为完成了工具执行。
- `events[].result`: `executed` / `error` / `budget_blocked` / `not_observed`。
- `llm_responses_observed`: 执行轨迹中看到的模型响应数，**不保证等于实际计费请求数**（失败的调用可能没有返回消息）。
- `input_tokens_observed` / `output_tokens_observed`: **仅当响应包含 usage_metadata** 时统计；否则为 `null`。不是费用统计。
- `duration_ms`: 整个任务的总耗时，不代表单个工具或模型请求延迟。
- `complete`: 执行到任务终态才为 `true`；异常后可能只能恢复到最近一个 Graph checkpoint。
- `error_code`: 若任务失败，记录统一错误分类，如 `MODEL_BUSY`。

## 真实模型的单次验证（可选）

智谱 `glm-4.7-flash` 之前曾出现 `429/1305`，请不要频繁重试。确定模型可用、Key 配置正确后再运行：

```bash
python -m researchflow.tool_cli --mode live \
  "请使用 github_repo_info 查询 langchain-ai/langgraph 的 Stars 与 Forks"
```

如果报 `MODEL_BUSY`，不会假装 Tool Calling 已经成功。它应当保存一个 `failed` 任务，以及当时有记录的部分 trace。

## 安全边界

轨迹只保存**已观察到的动作**，不包含或推断模型内部推理过程。为避免暴露密钥、私人搜索内容或外部注入，保存的只是工具名称（仅两个已知名称）、允许的参数**字段名**、调用 ID 的短哈希以及工具结果的成功/错误类别。**不保存原始参数值、工具正文、异常原文或 API Key**。

旧任务没有 `tool_trace`，查询会提示该记录创建于旧版本。

## 回滚

```bash
cp src/researchflow/tool_cli.py.v04.bak src/researchflow/tool_cli.py
```

并删除新加的 `tool_trace.py`、`tool_trace_cli.py`、新测试和说明文档（或使用 Git 对比分支变更）。
