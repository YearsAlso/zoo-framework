# 仓库元数据单一真源 (REPO_METADATA)

> 本文是 GitHub 仓库侧元数据（topics / About / homepage）与 PyPI 检索元数据的**唯一真源**。
> GitHub 的 topics / About / homepage 无法通过代码仓库管理（只能在仓库设置页人工粘贴），
> 所以把建议值放在这里：可版本化、可评审、可复制。
>
> **维护约定**：修改任何检索元数据时，**先改本文档，再同步 pyproject 与 GitHub 设置页**。
> pyproject 中的 keywords / classifiers / urls 是本文档对应章节的投影，两处 MUST 保持一致
> （一致性测试由 `doc-consistency-sweep` change 落地到 CI；落地前靠评审把关）。

## GitHub Topics

在仓库设置页 → General → Topics 粘贴以下单行字符串（20 个上限，本表 17 个）：

```text
task-scheduler,background-jobs,task-orchestration,orchestration,job-scheduling,threading,concurrency,thread-pool,in-process,agent,agent-framework,llm,ai-agents,workflow-automation,python,python-framework,state-machine
```

### 为什么是这些词（按三类检索意图）

| Topic | 面向谁的检索 | 为什么选它 |
|---|---|---|
| `task-scheduler` | 找"调度 / 后台任务"的人 | 项目的一句话定位里的第一能力；GitHub 上高流量 topic |
| `background-jobs` | 同上 | 搜"后台任务"的标准词，README 的 "long-lived background tasks" 与之对应 |
| `task-orchestration` / `orchestration` | 同上 | 与 PyPI description 的 "orchestration" 呼应，保证 GitHub 与 PyPI 检索都命中 |
| `job-scheduling` | 同上 | 常见变体拼写，覆盖 APScheduler 迁移人群 |
| `threading` / `concurrency` / `thread-pool` | 找"高并发 / 线程"的人 | 执行模型是线程（+ 协程），区别于进程模型框架 |
| `in-process` | 同上 | 差异化卖点：嵌入宿主进程、无 broker；帮助排除型搜索者快速命中 |
| `agent` / `agent-framework` / `llm` / `ai-agents` | 找"AI Agent 基础设施"的人 | "Built for AI-agent-generated code" 是项目核心定位；2026 年此检索面流量最大 |
| `workflow-automation` | 介于调度与 Agent 之间的人群 | 与 description 的 "workflows" 呼应 |
| `python` / `python-framework` | 生态兜底 | GitHub 生态默认词，帮助仓库进入语言聚合视图 |
| `state-machine` | 按能力搜的人 | 持久化状态机是文档中最常被单独引用的能力 |

## GitHub About 描述

在仓库设置页 → General → Description 粘贴（97 字符，≤160）：

```text
Python declarative multi-task orchestration framework powering next-gen Agents and workflows
```

**为什么**：直接复用 pyproject `[project].description`——它已含 `orchestration` / `Agents` /
`workflows` 三个检索词，且让 GitHub About 与 PyPI summary 恒一致（此前两者曾长期不一致）。

## Homepage

仓库设置页 → General → Website 填：

```text
https://yearsalso.github.io/zoo-framework/
```

**为什么**：文档站在线、由 `.github/workflows/docs.yml` 自动构建，且 PyPI 的 Documentation
URL 已指向它——保持两处一致。

## PyPI 元数据（pyproject 投影区）

以下值已同步进 `pyproject.toml`，修改时先改本文档再动 pyproject：

- **keywords**（19 个，与上面三类意图一一对应，另保留 `framework` / `async` /
  `state-machine` / `event-driven` 四个原有领域词）：见 pyproject `[project].keywords`。
- **classifiers** 必须含：
  - `Programming Language :: Python :: 3.14` —— `requires-python = ">=3.13"` 使 3.14
    兼容；PyPI 按 classifier 过滤时 3.14 用户能找到包
  - `Topic :: System :: Distributed Computing` —— 面向"分布式计算领域开发者"的检索意图。
    **如实记录一个取舍**：本项目是进程内（in-process）框架、不做跨机调度，该 Topic 的
    语义并非精确匹配；保留它是因为该 Topic 下的浏览人群与目标读者重合度最高，且它是
    审计验收点名的检索入口。语义精确性由 README 的对比表负责澄清。
- **license**：用 PEP 639 的 SPDX 表达式声明（`license = "Apache-2.0"` +
  `license-files = ["LICENSE"]`），**不写** `License :: OSI Approved :: ...`
  classifier —— 两者并存时工具会报错，且 SPDX 表达式才是可机器读取的真源
  （变更 `packaging-standards` / #119）。
- **project.urls** 必须含（其余 Homepage / Documentation / Repository / Issues 已有）：
  - `Changelog = https://github.com/YearsAlso/zoo-framework/blob/main/CHANGELOG.md`
  - `Benchmark = https://yearsalso.github.io/zoo-bench/`（独立基准仓库的在线报告）

## 姊妹仓库 zoo-bench

GitHub 描述建议：`Version-by-version benchmark report for zoo-framework — live report in Pages, raw data published`（对外选型证据，与本仓库 Benchmark URL 对应）。
