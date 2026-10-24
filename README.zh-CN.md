# ResearchFlow：基于 LangGraph 的技术调研 Agent（实习简历项目）

适合有 Python 项目基础、尚未接触 LangGraph 的开发者。本仓库是一份**可继续开发的 v0.1 工程骨架**，不是最终版简历项目；请根据实际完成的功能和评测结果撰写简历。

## 0. 先看清楚这两个运行模式

| 模式 | 配置 | 效果 | 用途 |
|---|---|---|---|
| 模拟模式 | `RESEARCHFLOW_MODE=mock`（默认） | 使用合成的演示检索结果，产出标有 DEMO 的报告 | 验证节点、条件路由、数据库与 API，无需密钥 |
| 真实模式 | `RESEARCHFLOW_MODE=live` | 调用 OpenAI 兼容的 LangChain ChatOpenAI 配置与 Tavily 实时搜索 | 真实调研（需要可用 API Key 与配额） |

**重要：模拟模式不能当作真实检索准确率。** 当前的 Validator 只检查引用 `[S1]` 是否存在，不能证明某句话得到了来源的事实支持。

## 1. 最小环境与启动（macOS）

建议 Python 3.11 或 3.12（也声明支持 3.11+），联网安装依赖。

```bash
unzip researchflow-agent-starter.zip
cd researchflow-agent-starter
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
python -m researchflow.cli 'Compare LangGraph and CrewAI for Python developers'
python -m pytest -q
```

模拟模式生成的报告会明确展示 `DEMO` 警告，并不会宣称它访问了真实网页。单机服务：

```bash
uvicorn researchflow.api:app --host 127.0.0.1 --port 8000 --reload
```

打开 `http://127.0.0.1:8000/docs`，先执行 POST `/research`，再将返回的 `task_id` 放入 GET `/research/{task_id}` 中，验证 SQLite 持久化读回。注意：POST 当前是**同步阻塞接口**，不是异步任务系统。请勿未经鉴权将此服务部署为公开 API。

### 切换真实模式

在 `.env` 中改成：

```dotenv
RESEARCHFLOW_MODE=live
OPENAI_API_KEY=your_key
OPENAI_MODEL=gpt-4o-mini
TAVILY_API_KEY=your_key
RESEARCHFLOW_MAX_SEARCHES=3
```

模型和搜索 API 需分别具备有效访问权限，可能产生费用；切勿将 `.env` 或密钥提交到 GitHub。配置完成后运行：

```bash
python -m researchflow.cli 'Compare LangGraph and CrewAI: architecture, state management and tools'
```

## 2. 当前代码结构（已实现的 v0.1）

```text
researchflow-agent-starter/
├── pyproject.toml                 # Python 依赖与 CLI 入口
├── .env.example                   # 模拟/真实模式配置模板
├── README.md                      # 英文说明
├── README.zh-CN.md                # 本文档
├── src/researchflow/
│   ├── schemas.py                 # ResearchState / Source / 引用校验 / URL 去重
│   ├── config.py                  # 配置校验
│   ├── providers.py               # Mock 与 Live 两套 LLM/搜索接口
│   ├── graph.py                   # plan -> search -> reflect -> write -> validate
│   ├── service.py                 # 编译 Graph / SQLite 检查点 / 任务 ID
│   ├── api.py                     # FastAPI POST/GET/health
│   └── cli.py                     # 命令行运行
├── tests/
│   ├── test_schemas.py            # URL 去重与引用检查
│   └── test_workflow.py           # 模拟模式端到端图测试
├── eval/
│   ├── questions.jsonl            # 示例问题（非标注真值）
│   └── run_eval.py                # 运行时长、搜索次数等工程指标
└── docs/
    └── ROADMAP.md                # 4 周开发计划
```

## 3. 核心流程，逐个读懂

```text
START
  └─ plan: 将问题拆为 1~2 条检索查询
      └─ search: 调一次检索工具，规范 URL 并赋予 S1/S2... 证据编号
          └─ reflect: 是否应继续搜索？
              ├─ 是、未到预算：回到 search
              └─ 否/已到预算：write -> validate -> END
```

`max_searches` 为硬性搜索次数上限；`state` 保存已检索词、搜索次数、证据列表、报告和警告。每次运行会生成唯一 `task_id` 用于 SQLite Checkpointer 的 `thread_id`。当前 `plan`/`reflect` 由 LLM 给出结构化输出，但搜索是由固定节点发起。**v0.1 尚未接入模型原生 `bind_tools` 工具选择，更不是多 Agent 项目。**

## 4. 4 周开发与可验收目标

| 时间 | 自己真正要完成的改动 | 验收方式 |
|---|---|---|
| 第 1 周 | 阅读 StateGraph、实现/调整 `ResearchState`、跑通 2 种模式、跟踪一次完整节点日志 | mock CLI 与 API 运行、真实模式完成 1 个任务、可讲清每个状态字段 |
| 第 2 周 | 加入 `tools/`，将网页搜索和后续 GitHub API 封装为结构化工具；实现一个原生 Tool Calling 分支（LLM 可以在工具间做选择）；设置次数上限和参数校验 | 证明模型根据不同问题调用不同工具；测试无工具、工具出错、无搜索结果三种情况 |
| 第 3 周 | 证据校验：按事实陈述建立来源映射；完整内容抓取与不可信内容隔离；重试/超时/成本记录；异步任务（可按时间延期） | 给出至少 3 例失败分析、恢复日志和错误处理自动化测试 |
| 第 4 周 | 建立至少 30 道固定测试题、人工标注重要证据；比较 v0.1 基线与改进版，并补充演示页面、README 和技术架构图 | 形成公开可复现的对照表，分析效果、延迟、费用和失败原因 |

### 第二周建议增加的最终目录（尚未在 v0.1 实现）

```text
src/researchflow/
├── tools/
│   ├── web_search.py              # web_search(query)
│   └── github_repo.py             # github_repo(repo_url) 元数据工具
├── agents/
│   └── tool_agent.py              # bind_tools / ToolNode / 工具路由
├── evaluation/
│   ├── retrieval.py               # 证据命中指标
│   └── citation_support.py        # 人工标注支持率评测
└── observability/
    └── tracing.py                 # 关键步骤日志与调用消耗
```

先做 1 个工具，再做 2 个工具，不要一开始就把搜索、浏览器、GitHub、数据库、MCP 全部塞进一个 Agent。

## 5. 简历可以怎样写（功能完成后再写）

> **ResearchFlow｜基于 LangGraph 的技术调研 Agent**：设计技术研究规划、网页检索、条件反馈与报告生成工作流；实现检索次数/成本预算、来源追踪、SQLite 状态持久化和 FastAPI 服务。构建固定评测集，评估来源支持率、任务完成率、P95 延迟与模型成本，并通过 A/B 实验分析改进效果。

不能直接把框架自带的功能写成个人创新。没有实现 `bind_tools` 就不要写“模型自主调用多工具”；没有证据语义标注就不要写“幻觉降低 X%”。

## 6. 面试必须能够解释的 8 个问题

1. LangGraph 解决了普通 Python `if/else` + 函数调用中的什么问题？
2. StateGraph 的 State 和节点返回值有什么区别？
3. 条件边何时让搜索循环结束？如何避免无限循环和费用失控？
4. 结构化输出与原生 Tool Calling 有什么区别？你的第一版属于哪一种？
5. 为什么使用 SQLite Checkpointer？`thread_id` 对一次任务意味着什么？
6. 一个引用 ID 存在，为什么不能证明报告陈述为真？
7. 如何保证搜索到的网页文本不能通过提示词注入干扰 Agent？
8. 比较两种 Agent 方案时，如何固定数据集、模型和预算才能公平？

## 7. 当前构建验证范围

已执行静态编译和基础测试。基础测试 **3 passed，1 skipped**，跳过的是需要 LangGraph 依赖的端到端测试。构建环境因网络解析限制无法下载依赖，所以**没有对真实 LangGraph 运行或外部 API 访问作出已验证声明**。在自己的开发环境安装依赖后执行 `python -m pytest -q`，并分别验证 mock/live 两种模式。

### 参考项目和文档

- LangGraph: https://github.com/langchain-ai/langgraph
- LangGraph Quickstart: https://docs.langchain.com/oss/python/langgraph/quickstart
- LangGraph SQLite: https://reference.langchain.com/python/langgraph.checkpoint.sqlite
- Tavily: https://reference.langchain.com/python/langchain-tavily/tavily_search/TavilySearch
- DeepAgents: https://github.com/langchain-ai/deepagents
