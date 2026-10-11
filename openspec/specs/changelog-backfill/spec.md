# changelog-backfill Specification

## Purpose
本能力规定变更日志的覆盖范围与 release 正文模板：可考据的已发布版本 MUST 都在日志里，发版说明由日志驱动、按固定四段组织，而不是每次临时拼凑。

## Requirements

### Requirement: CHANGELOG SHALL 覆盖全部可考据的已发布版本

`CHANGELOG.md` SHALL 为每个有考据基础的已发布版本（0.8.1-beta 起，含 0.8.1–0.8.4-beta、
0.9.0、0.9.1/0.9.2-beta、0.10.0、0.10.1–0.10.6-beta）提供按 Keep a Changelog 分类的
条目列；考据不足的版本（0.5.x–0.7.1）SHALL 保留在历史版本表中并标注「未回填」。
无考据基础的条目 MUST NOT 编造。交叉发布（0.8.1–0.8.4-beta 先行于 [0.9.0]）SHALL 用
交叉引用指向承载全部内容的正式版段落，避免同一事实多处叙述漂移。

#### Scenario: 版本条目覆盖
- **WHEN** `grep -c "^## \[" CHANGELOG.md` 并与 tag 清单比对
- **THEN** 0.8.1-beta 起每个版本都有 `## [版本]` 条目；无考据基础版本集中在历史
  版本表并带「未回填」标注，差异点逐个可解释

#### Scenario: BREAKING 条目带迁移说明
- **WHEN** 读取条目中标注 BREAKING 的（gevent 移除 / `@cage` / `@worker` /
  `@validation` / `event:sleep`）
- **THEN** 每条含迁移说明或显式锚定到 `docs/MIGRATION.md` 的对应小节

### Requirement: release 正文 SHALL 有固定四段模板并由 CHANGELOG 驱动

每个 GitHub release 的正文 SHALL 包含：一句话主题 / 使用者可见的变化 / 破坏性变更与
迁移 / 已知问题（无则写「无」）；内部重构 MUST NOT 出现在使用者可见段。正文的主内容
SHALL 由该版本的 `CHANGELOG.md` 段落抽取生成（`scripts/notes_from_changelog.py`），
抽取失败时 SHALL 回退到提交列表并在正文标注「未整理」。

#### Scenario: 模板文档存在
- **WHEN** 打开 `docs/RELEASE_PROCESS.md`
- **THEN** 含四段模板 + 「内部重构不进使用者可见段」规则 + 「发版前先写 CHANGELOG」
  的操作顺序

#### Scenario: 抽取脚本行为
- **WHEN** 对一个 `CHANGELOG.md` 里有节的版本执行
  `python scripts/notes_from_changelog.py <版本>`
- **THEN** stdout 输出该节全文，exit 0；对没有节的版本 exit 非 0（不静默输出空）。
  release.yml 的 body 生成 SHALL 优先脚本、失败回退提交列表
