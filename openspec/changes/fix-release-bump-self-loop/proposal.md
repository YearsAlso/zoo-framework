# 提案：fix-release-bump-self-loop —— 版本号自环（打 tag 判定漏列 CITATION.cff）

## Why

dev 上的发布自动化从 2026-10-11 起进入**自环**：每次 bump PR 合并后又立刻开出一个新的
bump PR，版本号只涨不发。

实测证据（全部可复跑）：

| 环节 | 事实 |
|---|---|
| bump 提交带几个文件 | `git diff 2d0eaac 3c2f600` → 4 个：`.env`、`pyproject.toml`、`zoo_framework/__init__.py`、`CITATION.cff` |
| 自环防护认几个 | `release.yml` 的 `ONLY_VERSION` 白名单只认前 3 个 → `ONLY_VERSION=0` |
| 判定结果 | 运行日志原文：`本次推送 → bump（分支 dev，版本类型 patch / beta）`——又开一个 bump PR |
| 后果 | `0.11.3-beta → 0.11.11-beta`（每 1–2 分钟一个），**`v0.11.2-beta` 之后一个 tag 都没有**；打 tag 正是由该判定触发，判成 bump 就永远走不到 |

根因不是"判定写错"，而是**同一份清单被抄了三处、其中两处没跟上第四处版本声明**：
`add-paths`（提交哪几处）在 `packaging-standards`（#119）时修好了——它有一条机械校验
（`tests/test_doc_consistency.py::test_release_bump_covers_every_version_place`）——而
`ONLY_VERSION` 白名单与"声明回声检测"的比较清单没有对应校验，于是静默漏列。

`CITATION.cff` 成为第四处版本声明后，凡"只改这四处"的推送都必须判成打 tag：漏一处就
退化成内容推送 → 自环。同理，回声检测漏一处可能把"只有第四处不同"的推送误判成
back-merge 回声而**静默不打 tag**（静默少发一版，同样不报错）。

## What Changes

- `release.yml` 的 `ONLY_VERSION` 白名单补 `CITATION.cff`（四处与 bump 步骤逐项一致），
  注释写明这份清单的维护约束与失效后果。
- `release.yml` 的"声明回声检测" `git diff origin/main HEAD --` 比较清单同样补齐四处
  （同一根因的第二处漏列），`echo` 文案由"三处"改"四处"。
- 新增机械校验
  `tests/test_doc_consistency.py::test_release_tag_decision_covers_every_version_place`：
  按 release.yml 解析出"版本声明处"集合，断言白名单与回声清单都等于它；并配套
  `test_tag_decision_scanner_has_teeth` 防止解析退化空跑。
- 规格 `ci-and-packaging` 的「版本线 MUST 跨分支保持连续」增加自环防护条款与
  「版本号提交不自环」场景，并把陈旧的"仅三处版本声明"改为"版本声明"。

## Non-Goals

- 不改 bump / tag / 发布的既有节奏（dev=patch+beta、main=minor）与人工批准闸门。
- 不改 back-merge PR 的触发逻辑与"回声不打 tag"的语义（只补全它比较的文件集合）。
- 不改 `add-paths`（已正确）与 `scripts/next_version.py`。
- 不清理已经产生的 bump PR / 版本号（`0.11.3-beta`→`0.11.11-beta` 的历史不重写）。

## Impact

- `.github/workflows/release.yml`：2 处清单各 +1 项，注释与 echo 文案。
- `tests/test_doc_consistency.py`：2 个正则 + 2 个解析函数 + 2 个用例。
- `openspec/specs/ci-and-packaging/spec.md`：1 个 Requirement（+1 条款、+1 场景、1 处陈旧
  措辞修正）。
- 合入后的收敛路径：本次修复本身触及 release.yml（在白名单内）→ 仍会开出一个 bump PR；
  合并那个 bump PR 时四处清单一致 → 判定为 `tag` → 自环终止，dev 首次打出 tag 并跑完整
  条发布链路（也就是 `fix-sbom-out-of-dist` 的真实验收点）。
