# changelog-backfill 设计

## 决策记录

### 1. 考据口径：区间 `git log` + 归档映射，无编造

每个版本的条目由三层来源交叉验证：
1. `git log vA..vB --format="%s"` 区间内 feat/fix/perf 提交（一手事实）；
2. `openspec/changes/archive/**` 的变更提案（提供"第几号变更、对使用者影响为何"）；
3. 已合并 PR 标题（公共语言）。

无法考据的（0.5.x–0.7.1，2026-02~09 之间的 5 个版本）**保留现有「历史版本」表**并加
「未回填（考据基础不足）」标注——它们已是自动生成提交列表，链接仍在，只是不做人工整理。

### 2. 交叉发布（0.8.1–0.8.4-beta 与 0.9.0）的呈现方式

实测发现 0.9.0 与 0.8.4-beta 同日交叉发布：0.8.1~0.8.4 是 0.9.0 发布线的**前置 beta**，
区间内 feat 与 [0.9.0] 的内容是同一批。呈现策略：
- `[0.9.0]` 段承接全部 BREAKING / Added / Changed（一个版本说全，读者不用拼）；
- `[0.8.1-beta]` ~ `[0.8.4-beta]` 段各写一句主题 + 「同一内容服务于 [0.9.0] 正式版，
  完整清单见 [0.9.0] 段」，避免漂移。
- `[0.10.0]` 同理标注=0.9.2-beta 的正式版聚合（区间内零独立 feat）。

### 3. `[Unreleased]` 条目的去向

`[Unreleased]` 现有条目（#73 节拍、#72 读盘、#82 版本线）与 [0.9.1-beta]/[0.9.2-beta]
的考据结果**精确对应**——它们是同一次内容但被记成了 Unreleased。回填后这些条目
**迁移**至对应版本段，`[Unreleased]` 清空为空节（保留标题）。这同时解决
"Unreleased 描述的变更其实早已发布"的矛盾。

### 4. release note 生成：脚本读 CHANGELOG，模板文档双轨

三件套：
- `docs/RELEASE_PROCESS.md`：四段模板（**一句话主题 / 使用者可见的变化 / 破坏性变更
  与迁移 / 已知问题**）+ 规则「内部重构不写进使用者可见段」+ 具体指引：
  **发版前把本版本段人工写进 CHANGELOG，release 自动抽取**。
- `scripts/notes_from_changelog.py`：从 `CHANGELOG.md` 抽 `## [VERSION]` 段落文本，
  stdout 输出；版本段缺失时 exit 1（让维护者先补 CHANGELOG 而非静默空正文）。
- `release.yml` Generate Changelog 步骤改为调脚本；**回退分支**：脚本失败或版本段
  缺失时用原 `git log` 列表兜底，保证发布流水线不因文档问题阻塞。

### 5. release.yml 的修改边界

只动 body 生成这一步（步骤名 `Generate Changelog` + body 模板），不碰：
OIDC trusted publishing、签名（.sig/.pem）、sign-commits、tag 生成、back-merge PR、
版本算术。body 段在模板四段基础上保留 📦 安装 / 📚 文档两段（原有内容）。

## 风险与边界

- 脚本 Regex 匹配 `## [0.10.6-beta]` 一类标题需要转义；实现以行首 `## [` + 精确版本
  锚定，避免抓到别的节。
- CHANGELOG 条目日期用 **tag 的 creatordate**（GitHub release 显示的 UTC 日期与
  tag 对齐）。
- 0.10.4 英文化对外行为不变（报错含义等同、api docstring 仅注释）——归 Changed
  而非 BREAKING；但「报错语言 English」对直接 grep 中文报错文本的使用者有感知,
  在 Changed 里写明。
- 本变更不改任何 Python 运行时行为；新增脚本供 CI 与维护者使用。
