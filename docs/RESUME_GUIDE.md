# 简历项目经历与面试准备

## 可以直接调整后放到简历的版本

**ResearchFlow｜LangGraph 技术调研与工具调用 Agent（个人项目）**

技术栈：Python、LangGraph、LangChain、OpenAI 兼容 API、Qwen、GitHub REST API、Tavily、SQLite、pytest、GitHub Actions。

- 设计并实现研究型 LangGraph 工作流和独立的 Tool Calling Agent，使用 `bind_tools` / `ToolNode` 支持模型自主选择 GitHub 仓库查询和网页检索工具，通过工具调用次数限制避免无限循环。
- 使用 SQLite 持久化任务状态、成功/失败记录和执行轨迹；对外提供 `task_id` 查询，记录已观察到的模型响应、工具调用、Token 使用量及耗时，并对错误进行安全分类。
- 建立 Mock 离线测试与工具选择、异常处理、预算保护评测用例；完成真实 Qwen 模型的 GitHub 工具调用闭环验证，并配置 GitHub Actions 自动运行离线回归测试。

**发布简历前确认：** V0.6 的 GitHub Actions 工作流真正绿色通过后，才能把「CI 已通过」写为既成事实。此前 V0.5 `50 passed` 不等于 V0.6 最新测试数；应更新为你新跑出的数字。

## 真实可描述的单次验证

- 模型：`qwen3.8-chat`；日期：2026-10-26
- 工作流：模型选择 `github_repo_info` → Python 执行 GitHub REST 查询 → 模型生成回答 → 保存 SQLite 工具轨迹。
- 单次轨迹：2 条模型响应、1 个工具请求、1 个工具结果，输入 Token 1,130，输出 Token 154，总耗时 6.55 秒。
- 这些不是平均性能、P95、成功率、准确率或成本下降百分比。若面试官追问，请说明是**一个成功案例**，评测框架与稳定性统计仍在继续建设。

## 重点面试问题

1. **为什么用 LangGraph？** 需要明确可观察状态、条件路由、循环与 Checkpointer；并非简单封装顺序函数。
2. **`bind_tools` 和普通 JSON 输出区别？** 前者通过模型接口返回结构化工具调用，由 Agent/ToolNode 执行；输出 JSON 本身不代表工具已调用。
3. **为什么 Mock 评测 100% 不代表 Agent 准确率 100%？** Mock 是脚本预定义决策，缺乏真实模型不确定性和真实网页数据分布。
4. **如何控制 Agent 费用？** 工具调用预算、`max_retries=0`、有上限的搜索次数、Token usage 观测。
5. **SQLite 记录和 LangGraph Checkpointer 各做什么？** 前者负责面向用户的终态查询及安全轨迹，后者保存 LangGraph 中间状态以供恢复/调试。
6. **为什么轨迹不保存原始 Tool 参数与返回正文？** 防止 API Key、私有查询、第三方不可信文本在日志中永久留存；代价是不能直接重放完整输入。
7. **你如何排查 `MODEL_ACCESS_DENIED`？** 比较 `.env` 与 shell 实际生效配置；当时旧的 `deepseek-v4-flash` 被环境变量覆盖，切换为有权限的 `qwen3.8-chat` 后真实调用成功。
8. **为什么不能称为生产级系统？** 目前没有异步队列、鉴权/多租户隔离、事实语义评测，也未测量长期性能稳定性。
