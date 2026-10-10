# repo-metadata 设计

## Context

- `pyproject.toml` 现状：`description` 已是正确的新文案（"Python declarative multi-task orchestration framework powering next-gen Agents and workflows"）；`keywords` 仅 `framework / multi-threaded / async / state-machine / event-driven`；`classifiers` 无 3.14、无 `Topic :: System :: Distributed Computing`；`project.urls` 有 Homepage/Documentation/Repository/Issues，缺 Changelog 与 Benchmark。
- GitHub 侧元数据（topics / About / homepage）**无法从代码仓库管理**，必须人工在仓库设置页粘贴——所以真源必须是一份可版本化、可评审、可复制粘贴的文档。
- 项目定位关键词：进程内（in-process）、无 broker、长任务调度、事件管道、状态机持久化、为 AI 生成代码而设计（README "Built for AI-agent-generated code"）。
- 可用 URL：文档站 `https://yearsalso.github.io/zoo-framework/`（pyproject 已有）；benchmark 报告 `https://yearsalso.github.io/zoo-bench/`（README 已引用）；CHANGELOG 随仓库 `CHANGELOG.md`。

## Goals / Non-Goals

**Goals:**
- 让三类目标读者在 GitHub 搜索 / PyPI 搜索 / AI 提问三个渠道都能命中本项目。
- 元数据唯一真源：pyproject 与 REPO_METADATA.md 不再是两份各自漂移的清单。

**Non-Goals:**
- 不改 README 正文（`readme-first-screen` 负责）。
- 不做 llms.txt / AGENTS.md（`agent-discoverability` 负责）。
- 不改发布流程、不改依赖集合、不加新依赖。

## Decisions

### D1 词表按三类检索意图组织，而非按功能罗列

| 意图 | 读者在搜什么 | 词 |
|---|---|---|
| 找"调度 / 后台任务" | task scheduler, background jobs, job queue, task orchestration | `task-scheduler`、`background-jobs`、`orchestration`、`task-queue`、`job-scheduling` |
| 找"高并发 / 线程" | threading, concurrency, thread pool | `threading`、`concurrency`、`thread-pool`、`worker-pool`、`in-process` |
| 找"AI Agent 基础设施" | agent runtime, agent framework, llm tooling | `agent`、`agent-framework`、`llm`、`ai-agents`、`workflow-automation` |

理由：GitHub topic 上限 20 个，按意图选词保证每个词都有真实检索人群，避免"每个功能都起一个词"稀释匹配度。`agent` 与 `llm` 是审计验收标准点名必须包含的词。

### D2 GitHub About 描述以 PyPI description 为准，不另写一套

About ≤160 字符且需含核心关键词。直接复用 pyproject `description`（"Python declarative multi-task orchestration framework powering next-gen Agents and workflows"，实测 97 字符）——它已含 orchestration / Agents / workflows 三个检索词，且 PyPI summary 与 GitHub About 一致消除了审计发现的"两处描述不一致"问题。Alternative（另写一句更短口号）被否：两处描述再次漂移正是要修的病。

### D3 Homepage = 文档站 URL

`https://yearsalso.github.io/zoo-framework/`——在线、由 docs.yml 自动构建、指向用户指南。审计验收标准即此值。

### D4 REPO_METADATA.md 是真源，pyproject 是其投影；一致性靠"改一处抄一处"约定 + 验收命令

不引入构建期校验（用脚本对 pyproject 与 md 做一致性检查属于过度工程，`doc-consistency-sweep` 的 C1 会建立可执行文档一致性测试，届时把"pyproject keywords/classifiers 与 REPO_METADATA.md 一致"加入其断言范围——本 change 只在 REPO_METADATA.md 里写明这条约定并留给 C1 落地）。Alternative（本 change 内新增 tests/test_repo_metadata.py）被否：与 C1 的测试职责重叠。

### D5 classifiers 只加两个，不动现有七个

`Programming Language :: Python :: 3.14`：`requires-python = ">=3.13"` 使 3.14 兼容，PyPI 页面按 classifier 过滤时 3.14 用户能找到包；`Topic :: System :: Distributed Computing`：审计验收标准点名（注：语义上它是进程内框架，此 classifier 的选择记录了"面向分布式计算领域开发者的检索意图"，是否更贴切由 `Topic :: Software Development` 系配合，不删现有 Topic）。

## Risks / Trade-offs

- [GitHub 侧粘贴由人工完成，可能再次漂移] → REPO_METADATA.md 每项给"为什么选这个词"，评审时能发现未同步；C1 的文档一致性测试落地后 pyproject 侧自动把关，GitHub 侧依赖发布 checklist（CHANGELOG 模板 change 会加）。
- [`Topic :: System :: Distributed Computing` 语义不完全精确] → 检索收益优先于分类学严谨；在 REPO_METADATA.md 中如实记录此取舍。
- [`python -m build` 对新字段失败] → PEP 621 标准字段，风险极低；验收含构建 + twine check 回归。

## Migration Plan

1. 改 pyproject 元数据 + 新增 REPO_METADATA.md，PR → dev。
2. 验收：`pip install -e .` 成功、`python -c "import zoo_framework"` 正常、`python -m build` + `twine check dist/*` 通过。
3. 维护者按 REPO_METADATA.md 在 GitHub 设置页粘贴 topics/About/homepage（一次性操作，文档含可复制字符串）。
4. 回滚：revert 两个文件即可，无运行时影响。

## Open Questions

（无。）
