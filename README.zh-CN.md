# ResearchFlow：基于 LangGraph 的技术调研 Agent

[English README](README.md) · [架构说明](docs/ARCHITECTURE.md) · [工具评测](README_TOOL_EVAL.md) · [执行轨迹](README_TOOL_TRACE.md) · [简历与面试](docs/RESUME_GUIDE.md)

一个可运行、可测试、可追溯的 **LangGraph Agent 工程项目**，适用于展示大模型应用开发实习相关能力。项目保留两条独立链路：规划/检索/报告工作流，以及由真实模型使用 `bind_tools` 选择工具的 Tool Calling Agent。

> **证据边界：** Mock 是脚本模拟，不代表模型智能。2026-10-26 已在本机用 `qwen3.8-chat` 成功完成一次真实 GitHub 工具调用并保存 SQLite 轨迹，但一次成功不等于模型长期稳定或评测准确率。

## 1. 功能与实现情况

| 模块 | 实现 | 验证方式 |
|---|---|---|
| 研究流程 | `plan → search → reflect → write → validate`，检索预算 | Mock 工作流测试 |
| 自主工具选择 | LangGraph `bind_tools` + `ToolNode`，GitHub / Web Search | Qwen 真实 Tool Calling 成功一次 |
| 外部工具 | 只读 GitHub 仓库 API / Tavily 搜索 | GitHub 实时数据返回 |
| 状态持久化 | SQLite checkpoint + 任务成功/失败记录 | 用 `task_id` 查询 |
| 可观测性 | 工具请求/执行、Token 观测、耗时、异常分类 | `tool_trace_cli` |
| 评测 | 工具选择、工具故障、预算拦截离线场景 | `tool_eval --mode mock`，非真实模型准确率 |
| 工程质量 | pytest、GitHub Actions 离线 CI、配置诊断 | 本机与 CI 测试 |

## 2. 五分钟启动（Mock，不需要密钥）

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
cp .env.example .env
python -m researchflow.config_doctor
python -m pytest -q
python -m researchflow.tool_cli --mode mock '请查询 LangGraph 的 GitHub 仓库信息'
python -m researchflow.tool_eval --mode mock
```

Mock 输出会明确标注 `DEMO`，GitHub 数据为合成数据。CI 同样只运行离线测试，**不消耗 API 额度**。

## 3. 真实模型接入（以已验证的 USTC Qwen 为例）

在**本机** `.env` 中配置（以下占位符不是实际密钥）：

```dotenv
RESEARCHFLOW_MODE=live
RESEARCHFLOW_DB=.data/researchflow.sqlite
RESEARCHFLOW_MAX_SEARCHES=1
RESEARCHFLOW_LLM_RETRIES=0

OPENAI_BASE_URL=https://api.llm.ustc.edu.cn/v1
OPENAI_MODEL=qwen3.8-chat
OPENAI_API_KEY=YOUR_NEW_USTC_KEY
TAVILY_API_KEY=YOUR_NEW_TAVILY_KEY

# 可选：仅给模型 HTTP 客户端指定显式代理
# RESEARCHFLOW_HTTP_PROXY=http://127.0.0.1:7890
```

上述模型名及接口依赖服务商当前授权；不同提供方应使用自己控制台列出的模型 ID。即使只问 GitHub，当前 Tool Agent 仍会初始化 Tavily 搜索工具，所以 Live 模式需要 Tavily Key；后续可优化为按需初始化。

**配置优先级为终端环境变量 > `.env`。** 这正是一次真实排错中发现的坑：终端旧 `OPENAI_MODEL=deepseek-v4-flash` 覆盖了 `.env` 的 `qwen3.8-chat`，导致 Agent 失败。V0.6 提供不打印密钥的诊断命令：

```bash
python -m researchflow.config_doctor
# 如果提示 OPENAI_MODEL 冲突：
unset OPENAI_MODEL
python -m researchflow.config_doctor
```

网络默认沿用 V0.5 已工作过的 IPv4 直连客户端，并显式忽略 `HTTP_PROXY` 等环境变量。**如需模型 API 经过 ClashX**，可设置 `RESEARCHFLOW_HTTP_PROXY=http://127.0.0.1:7890`。此选项只影响模型请求，不影响 GitHub/Tavily；不用为了项目关闭 ChatGPT 的系统代理。不要关闭 TLS 证书校验。

执行真实 Tool Calling（可能产生调用费用/额度消耗，建议先单次验证）：

```bash
python -m researchflow.tool_cli --mode live \
  '请调用 GitHub 工具，查询 langchain-ai/langgraph 仓库的 Stars 和 Forks'
```

复制成功输出中的 `task_id`：

```bash
python -m researchflow.tool_trace_cli --task-id YOUR_TASK_UUID
```

检查 `status=completed`、`mode=live`、`synthetic=false`、`tool_results_observed>=1`、`complete=true`，才能说明真实工具执行与轨迹保存均完成。

## 4. 单次真实验证结果（不是性能基准）

2026-10-26 的一次用户本机运行记录：

| 记录项 | 单次观测值 |
|---|---:|
| 模型 | `qwen3.8-chat` |
| 工具 | `github_repo_info` |
| 模型响应次数（已观测） | 2 |
| 工具调用请求 | 1 |
| 工具结果已观测 | 1 |
| 输入 / 输出 Token | 1,130 / 154 |
| 任务耗时 | 6,553.4 ms |
| SQLite 轨迹 | `complete=true`，`synthetic=false` |

此前 V0.5 本机回归测试 `50 passed`；V0.6 引入新测试后须重新运行，不能沿用旧测试数作为新版本结果。Mock V0.4 评测 `6/6` 只验证脚本场景，不代表真实 LLM 工具选择准确率为 100%。

## 5. 代码结构

```text
src/researchflow/
  graph.py              研究工作流 StateGraph
  tool_agent.py         bind_tools + ToolNode 条件路由与预算保护
  research_tools.py     GitHub / Tavily 工具与输入校验
  providers.py          Mock/Live Provider 与异常分类
  network.py            显式模型 HTTP 代理（V0.6）
  config.py             模式、模型、数据库等配置
  config_doctor.py      无网络、无密钥泄漏的配置诊断（V0.6）
  service.py            研究任务执行、SQLite 持久化
  tool_cli.py           Agent 工具调用 CLI
  tool_trace.py         安全执行轨迹汇总
  tool_trace_cli.py     按 task_id 查询轨迹
  tool_eval.py          Mock 工具评测
.github/workflows/tests.yml  仅离线 pytest + Mock CI
```

## 6. 已知限制和安全原则

- 当前没有完成 **人工标注事实支持率** 评测，不能宣称消除幻觉或达到生产级准确率。
- 任务耗时和 Token 是**单次结果**，不代表平均时延、P95 或成本。
- Mock 模式的工具数据不真实；只读 GitHub 工具不会修改仓库。
- Tool Trace 不保存原始模型 Prompt、工具参数值、工具正文、API Key 或异常原文，只记录观察到的事件。
- FastAPI 的 POST `/research` 是同步接口；没有任务队列、权限验证或多租户隔离，不能直接对公网开放。
- `.env`、数据库、生成的评测结果、备份文件应保持在 Git 仓库之外。

建议把真正证明做过的功能写进简历。详见 [面试说明](docs/RESUME_GUIDE.md)。
