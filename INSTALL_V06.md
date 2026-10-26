# V0.6 增量补丁安装（适用于已完成 V0.5 的本机项目）

本 ZIP **不包含 `.env`、真实 API Key、数据库、真实 GitHub 查询数据**。不包含完整 `providers.py` 或 `.gitignore`，避免粗暴覆盖你的本地修改；安装脚本会对 V0.5 已知代码做**精确匹配**、先备份，无法匹配时安全停止并让你提供文件差异。

## 1. 创建分支

```bash
git switch feat/agent-tracing
git status --short
git switch -c feat/portfolio-v06
```

如果存在未提交的自定义修改，先备份或提交再继续。

## 2. 解压 + 应用

下载 ZIP 到 `~/Downloads/` 后，在项目根目录运行：

```bash
unzip -o ~/Downloads/researchflow-portfolio-v06.zip -d .
python scripts/apply_v06_provider_patch.py
```

安装器会：
- 备份 `src/researchflow/providers.py` 为 `providers.py.v05.bak`；
- 将 LLM 网络初始化改为可选的 `RESEARCHFLOW_HTTP_PROXY`，**未设置时继续沿用 IPv4 直连**；
- 显式传入已生效的 `OPENAI_BASE_URL` / `OPENAI_API_KEY`；
- 向 `.gitignore` **追加**忽略规则，而不是覆盖原有规则。

失败后不应继续覆盖 `providers.py`，把不含密钥的 `git diff -- src/researchflow/providers.py` 发给开发助手检查。

## 3. 回归验收（不用真实 API）

```bash
python -m compileall -q src/researchflow
python -m pytest -q
python -m researchflow.config_doctor
python -m researchflow.tool_eval --mode mock
python -m researchflow.tool_cli --mode mock '请查询 LangGraph 的 GitHub 仓库信息'
```

`config_doctor` 如果发现 shell 的 `OPENAI_MODEL` 和 `.env` 不一致，会显示警告并返回状态 1，但不会打印密钥；这是设计行为。修复方式通常为 `unset OPENAI_MODEL`，**不要**在聊天中贴密钥。

本补丁在一个未安装 LangGraph 的离线环境验证了语法和部分单元测试；要以你本机完整 `python -m pytest -q` 为正式回归结果。CI 也不执行真实模型请求。

## 4. 避免影响已经成功的 Live 链路

你的 V0.5 已通过校内网络 + ClashX 规则完成一次真实工具调用，因此 **V0.6 不要求你修改 `.env` 或 ClashX**。只有在模型连接确实需要显式 7890 端口时，才向本机 `.env` 添加：

```dotenv
RESEARCHFLOW_HTTP_PROXY=http://127.0.0.1:7890
```

在修改前，先运行 `python -m researchflow.config_doctor` 确认终端没有旧模型覆盖 `.env`。

## 5. 审核、提交、运行 CI

```bash
git status --short
git diff --check
```

检查无敏感文件后，显式暂存本补丁文件：

```bash
git add .env.example .gitignore README.md README.zh-CN.md INSTALL_V06.md \
  .github/workflows/tests.yml docs/ARCHITECTURE.md docs/RESUME_GUIDE.md \
  src/researchflow/providers.py src/researchflow/network.py src/researchflow/config_doctor.py \
  tests/test_v06_config.py tests/test_v06_patcher.py scripts/apply_v06_provider_patch.py

git diff --cached --check
git diff --cached --name-only
git commit -m 'feat: add configuration diagnostics CI and portfolio docs'
git status --short
```

如果 GitHub remote 已配置，推送该分支后，在仓库的 Actions 标签页确认绿色运行，再在简历中写「CI 已通过」。

## 回滚

可直接切回 `feat/agent-tracing` 分支。若想在当前工作区恢复 provider，使用备份文件（在 Git 提交前）或 `git restore src/researchflow/providers.py`。不要覆盖 `.env`。
