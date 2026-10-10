# repo-metadata 任务清单

## 1. pyproject.toml 元数据（不碰依赖与版本号）

- [x] 1.1 按三类检索意图扩展 `keywords`（含 `agent`、`orchestration`），词表与 REPO_METADATA.md 一致（验证：`pip install -e .` 成功且 `python -c "import zoo_framework"` 正常——实测 editable 安装成功、导入正常）
- [x] 1.2 `classifiers` 增加 `Programming Language :: Python :: 3.14` 与 `Topic :: System :: Distributed Computing`（验证：`python -m build` 后 dist 元数据含两个新 classifier——见 build-metadata-check.txt）
- [x] 1.3 `[project.urls]` 增加 `Changelog = "https://github.com/YearsAlso/zoo-framework/blob/main/CHANGELOG.md"` 与 `Benchmark = "https://yearsalso.github.io/zoo-bench/"`（验证：构建产物 METADATA 中含两个 URL——见 build-metadata-check.txt）

## 2. docs/REPO_METADATA.md 真源文档

- [x] 2.1 新建 `docs/REPO_METADATA.md`：GitHub Topics ≥15 个单行可粘贴字符串（含 `task-scheduler` / `background-jobs` / `orchestration` / `agent` / `llm`）+ About 描述（与 pyproject description 一致，≤160 字符）+ Homepage 值 + PyPI keywords/classifiers/urls 建议值（验证：文档存在且含可复制的单行 topics 字符串——17 个 topic）
- [x] 2.2 每个词条附"为什么选这个词、面向谁的检索"说明，按三类意图分节（验证：三类意图各有独立小节）
- [x] 2.3 写明维护约定：pyproject 是 GitHub 侧内容的投影、修改流程是"先改本文档再同步 pyproject / GitHub 设置页"，并注明一致性测试由 doc-consistency-sweep 落地（验证：文档含此段落）

## 3. 回归验证

- [x] 3.1 `python -m build` + `twine check dist/*` 全部通过，原始输出记录到 change 目录（验证：输出存档——build-metadata-check.txt；twine 双 PASSED）
- [x] 3.2 确认未触碰依赖集合与版本号：`git diff pyproject.toml` 只含 keywords/classifiers/urls 变更（验证：diff 审查——29 insertions / 1 deletion，零依赖与版本行）
- [x] 3.3 `openspec validate repo-metadata --strict` 通过（验证：退出码 0）

## 4. 移交维护者（代码仓库外的一次性操作）

- [x] 4.1 提醒维护者按 REPO_METADATA.md 在 GitHub 仓库设置粘贴 topics / About / homepage
      （验证：PR 描述含操作清单；GitHub 侧生效后 `gh api repos/YearsAlso/zoo-framework --jq '.topics'` 返回 ≥15 个 topic）
  - 实测（2026-10-10 联网核验，GitHub 侧已生效）：`gh api repos/YearsAlso/zoo-framework`
    返回 **20 个 topic**（≥15 达标）、`homepage` = `https://yearsalso.github.io/zoo-framework/`、
    `description` = "In-process task orchestration for Python: scheduled, observable,
    stateful — no broker, no cron daemon."（与「无 broker」定位一致）
  - 未完成子项：「PR 描述含操作清单」——本分支尚无 PR（`gh pr list --head perfect/docs
    --state all` 返回空），待本包统一 PR 时把该操作清单（已由维护者执行完毕）附入 PR 描述
