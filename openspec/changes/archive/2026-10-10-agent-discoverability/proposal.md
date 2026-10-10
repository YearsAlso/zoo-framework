## Why

本项目的定位是"**为 AI 生成的代码而设计的编排框架**"，但仓库里**没有任何一处是写给"检索"看的**（issue #122）：

- **没有 `llms.txt`**：LLM 联网检索按约定取站点根的 `/llms.txt`，本仓库一份都没有。
- **没有根 `AGENTS.md`**：通用编码 agent（Cursor / Copilot / Codex）读的是仓库根的 agent 说明。
  现有 `CLAUDE.md` 是"**在这个仓库里改代码**"的内部指引，不是"**用这个库写代码**"的公开说明。
- **README 没有问答结构**：全文是特性表、对比表与徽章。像"Python 里怎么跑进程内后台任务、
  不想装 Redis"这种真实提问，README 里找不到**一句问句形状的答案**——而模型回答这类问题时
  最依赖的正是这种结构。
- **最深的一份自然语言问答其实已经存在**：`docs/FAQ.md` 有 10 组问句，已覆盖 issue 点名的
  **全部**问题；但它是中文，且 README 没有链接到它——英文语料与首屏访问者都取不到。

一句话：**内容基本已经写好，缺的是让检索看得见的那层壳。**

实测到三处必须先说清的事实（详见 design 的「实测与口径」）：

1. issue 里"现成内容见 `artifacts/llms.txt` / `artifacts/AGENTS.md`"的两份草稿**在本机不存在**
   （已搜 `F:\Python\zoo`、`.orca/`、`F:\` 三层）：两份文件只能按 issue 的内容清单，从仓库的
   **实测状态**写出，不得转述未经核对的宣传口径。
2. 本项目自己的 Pages 站点（`docs.yml`，仅 `main` 触发）今天只有 `/benchmark/` 返回 200，
   `/api/`、`/install/`、`/FAQ/` 均 404（`main` 落后 88 个提交）。因此 llms.txt 里的绝对 URL
   **逐个 curl 过才写**——写站点页面链接今天就是死链。
3. `README.md` 与 `README.zh.md` 是**严格镜像维护**的（`tests/test_doc_consistency.py` 已比对
   两者的隐喻表），FAQ 只加英文会造成静默不对称。

## What Changes

- **新增仓库根 `llms.txt`**：H1 标题 + 引用式摘要 + 分节链接列表；含「什么时候用 / 什么时候
  **不要**用」两个清单（后者明写"需要跨机器 → Celery""需要 cron → APScheduler""多进程 →
  本框架未实现"）；核心概念一律用**功能名**，并显式说明隐喻只影响命名、不影响语义；
  最小可运行示例；指向文档站 / API 参考 / benchmark 报告 / CHANGELOG 的**实测可达**绝对 URL。
- **新增仓库根 `AGENTS.md`**：面向通用编码 agent 的接入说明，与 `CLAUDE.md` 分工划清
  （前者"用这个库写代码"，后者"在这个仓库里改代码"）——安装与版本门槛、**Worker 必须以
  "类"注册**（附三类真实报错原文）、配置与实现分离（Worker 只依赖 `props`）、「失败要大声」
  的四个实例（附实测报错串）、以及验证改动的方式（跑哪个测试命令）。
- **`README.md` 与 `README.zh.md` 各自新增 `## FAQ`**：≥10 组自然语言问句 + 每组 1–3 行短答，
  覆盖 issue 点名的全部问题（含"生产环境有人用吗"——按 `ADOPTERS.md` 如实回答）；
  短答与 `docs/FAQ.md` 逐条对应，语言各自本地化。
- **`docs/FAQ.md` 保持"详版真源"定位**（正文不改），与 README FAQ 的对应关系由新增的
  **机械校验**守住：问题集合覆盖、支持/不支持结论一致、"不支持"表述与 README 特性表一致。
- **`scripts/mkdocs_hooks.py` 泛化**：构建期把仓库根 `llms.txt` 复制到站点产物根，使其在
  `https://yearsalso.github.io/zoo-framework/llms.txt` 可达；保留既有的"**源缺失即构建失败**"
  语义；`docs.yml` 的触发路径补 `llms.txt`（否则只改它不会重新发布——与既有的
  `.well-known/**` 同理）。
- **不新增第三方依赖、不改 `zoo_framework/` 运行时行为、不放松也不收紧任何"未实现"清单的口径。**

## Capabilities

### New Capabilities

- `ai-discoverability`: 面向 AI 检索与通用编码 agent 的**发现层契约**——`llms.txt` 的结构与
  「不得写入未实现能力」的准确性约束；`AGENTS.md` 的接入说明范围（含"Worker 必须为类"这一
  历史坑与其真实报错）；README FAQ 的问句覆盖、短答篇幅与"不支持"口径的三方一致性
  （README ｜ 特性表 ｜ `docs/FAQ.md`）。

### Modified Capabilities

- `ci-and-packaging`: 新增一条要求——文档站产物 MUST 发布仓库根 `llms.txt`（真源唯一、
  构建期复制、源文件缺失即构建失败、部署触发路径 MUST 覆盖它）。

## Impact

- **新增文件**：`llms.txt`、`AGENTS.md`、`tests/test_agent_discoverability.py`。
- **修改文件**：`README.md`、`README.zh.md`（各一节 FAQ）、`scripts/mkdocs_hooks.py`
  （约 +20 行）、`.github/workflows/docs.yml`（触发路径 +1 行）。
- **不改**：`docs/FAQ.md` 正文、`CLAUDE.md`、`zoo_framework/**`、依赖集合、发版流程、
  README 既有的特性表与对比表。
- **发现但本次不修**（如实记录，避免丢失）：`docs/FAQ.md` 的"装不上/版本不对怎么办"一节写着
  "仓库的 `uv.lock` 当前与 `pyproject.toml` 不一致"，而实测 `uv lock --check` 通过
  （`Resolved 79 packages`）——该句已过期。它不在本变更的问题清单内，本变更也不重复这句话；
  修与不修由维护者决定。
- **风险**：① llms.txt / AGENTS.md 里任何"未实现"表述一旦与 README 特性表不一致，会立刻
  变成新的自相矛盾——故三方一致性做成**机械断言**而不是人工检查；② FAQ 短答是详版的压缩，
  压缩会自然产生"第二口径"，故断言比对的是**问题集合**与**支持/不支持结论**，不是逐字文本；
  ③ 站点发布只由 `main` 触发、本次改动在 `perfect/docs`，所以"站点根可达"只能在合并后生效——
  按 #121 的同一口径如实标注，**不声称已生效**。
