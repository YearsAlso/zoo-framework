# 提案：changelog-backfill

## Why（为什么）

`CHANGELOG.md` 目前只有 `[Unreleased]` + `[0.8.0]` 两条（`grep -c "^## \["` = 2），而仓库
有 **21 个 tag / 15 个 GitHub release**——0.8.1-beta 起 13 个版本零条目。Release 是订阅型
渠道，每个 release 正文只有一句 `Release vX.Y.Z`（模板生成），等于整个渠道浪费。实测
考据数据（tag 日期 + 区间 feat/fix 提交 + openspec 归档）已足以支撑 0.8.1–0.10.6 的
回填；无法考据的部分按口径标注「未回填」，不编造。

## What Changes（做什么）

### 逐条核对表（issue #117 3 条 → 处置）

| # | issue 表述 | 实测证据 | 定性 | 处置 |
|---|---|---|---|---|
| 1 | 回填 0.9.x/0.10.x | tag 21 个；缺条目版本 13 个（0.8.1~0.8.4-beta、0.9.0、0.9.1/0.9.2-beta、0.10.0、0.10.1~0.10.6-beta）。每段区间已逐个 `git log vA..vB` 考据 feat/fix；0.9.0 与 v0.8.4-beta **同日交叉发布**（0.9.0=10-06，0.8.4=10-07 tag 日期晚但内容是 0.9.0 线的一部分，0.9.0 区间内无独立 feat） | 成立 | **修**：`CHANGELOG.md` 新增 13 个版本条目，逐版标注来源与考据方式 |
| 2 | release note 模板 | 当前 release.yml 自动生成 body：提交标题列表（head -20）+ pip install + 文档链接，无「使用者可见的变化 / BREAKING 标注」 | 成立 | **修**：`docs/RELEASE_PROCESS.md` 新增模板；release.yml body 改为「从 CHANGELOG 抽取该版本段落」脚本 + 模板骨架 |
| 3 | workflow 同步 | release.yml:479-492 的 changelog 步骤是 `git log` 标题列表 | 成立 | **修**：改 `scripts/notes_from_changelog.py`（新脚本，从 CHANGELOG 抽节），release body 含主题/可见变化/BREAKING/已知问题四段；CI 风险低（纯读取脚本，失败时正文回退为提交列表） |

### 考据结果（每版来源）

- **0.8.1-beta**：`fix(ci) tag 推送改用 PAT`——否则「打 tag → 发布」静默断链。
- **0.8.2-beta**：即 `v0.8.0..v0.9.0` 区间的四个 feat 的**前半**（#50 切片一载体登记表、
  #51 语义确定性、调度策略缓存）＋ `@worker` 出导出面弃用 + 执行原语对齐（去 gevent 等）。
  注意 0.8.1~0.8.4 是 0.9.0 发布线上**先合进 dev 的内容**，其条目应与 [0.9.0] 段一致、
  避免重复叙述——用「见 [0.9.0] 段」交叉引用。
- **0.8.3-beta**：thread_pool 容器换 queue.Queue（#47 P2）。
- **0.8.4-beta**：载体收编（#50 交付 1，方案 A）。
- **0.9.0**：正式版区间含上述全部 + `[0.9.0]` 段承接（fallback：0.9.0 无独立 feat，
  聚合 0.8.1~0.8.4 的内容并标 BREAKING：cage 已删（在 0.8.0）、gevent 移除（0.8.1~0.8.4
  区间合入）、@worker 弃用、validation/@cage 移除）。
- **0.9.1-beta**：`event:delay` / `stateMachine:delay`（#73）、状态读盘恢复（#72）。
  与 `[Unreleased]` 已有条目重合——回填后正是把它归档进 `[0.9.1-beta]` 段的理由；
  `[Unreleased]` 的 #72/#73 条目迁移至该段。
- **0.9.2-beta**：`fix(ci) 版本线跨分支连续（#82）`。
- **0.10.0**：正式版，聚合 0.9.2~0.10.0 区间：无独立 feat/fix（仅 bump + 归档）；
  正文标注「0.9.2-beta 内容的正式版聚合」。
- **0.10.1-beta**：token 权限收紧 + actions 钉 SHA + release 产物签名（#90 #91 #94）；
  删 requirements-dev.txt 的前身 requirements.txt（#93）。
- **0.10.2-beta**：epsilon-greedy bandit + `DualArmWorker`（`adaptive:enabled` 默认 false）、
  推模型事件管道、批量投递、Rust 探针升级。
- **0.10.3-beta**：原生任务执行（可选 Rust 扩展 `zoo_framework_native` + `native:*`
  配置键族 + `NativeTaskWorker`）。
- **0.10.4-beta**：docstring 英文化 + runtime 报错英文化（写入 `Breaking? no`——对外行为不变，
  归 Changed）。
- **0.10.5-beta**：文档信息架构重建（mkdocstrings API 自动生成 + 迁移指南 + 版本政策 +
  教程 03-05 + 品牌规范）。
- **0.10.6-beta**：用户文档入口指向独立 VitePress 站点。

### 验收锚点（对应 issue 验收标准）

- `grep -c "^## \[" CHANGELOG.md` 与已发布版本数一致（21 tag 中 0.5.x/0.6.x/0.7.1 的
  5 个版本无考据基础 → 保留「历史版本」表归位，**不编造**；差异处有明确说明）
- BREAKING 条目（gevent / @cage / @worker / validation / event:sleep）全部标注 + 迁移
  说明（迁移正文锚定到 `docs/MIGRATION.md` 对应小节）
- `docs/RELEASE_PROCESS.md` 存在四段模板
- release.yml body 步骤改为从 CHANGELOG 抽取

## Capabilities（能力）

- **New**: `changelog-backfill` — CHANGELOG 完整性、release note 模板与生成链路
- **Modified**: 无

## 影响（Impact）

- `CHANGELOG.md`：新增 13 个版本条目；`[Unreleased]` 的 #72/#73/#82 条目迁移至对应版本段；
  「历史版本」表说明保留（无考据基础 → 未回填标注）
- 新增 `docs/RELEASE_PROCESS.md` + `scripts/notes_from_changelog.py`
- `.github/workflows/release.yml`：Generate Changelog 步骤改为脚本抽取 + 回退分支
- 不碰：PyPI 发布 / 签名 / OIDC 逻辑（纯 body 生成层）
