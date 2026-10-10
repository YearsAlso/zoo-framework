## Context

动机见 `proposal.md` —— Why。本节只记**约束**与**实测事实**，它们决定了下面的每个选择。

**贡献者入口的既存契约**

- `CONTRIBUTING.md` 542 行，中英双半：`## 🇬🇧 English` 在第 8 行、`## 🇨🇳 中文` 在第 286 行，
  每半 13 个 `###` 章节（英文：Before you write code / Development setup / Branch strategy /
  Commit messages / Quality gates / Tests / Spec-driven changes / Documentation contributions /
  Pull requests / Good first issues / Reporting bugs and proposing features / Code of Conduct）。
- **双语平行是本文件已被其它 change 引用的明文契约**（`readme-first-screen`、`example-hygiene`
  的 design 都写明"grep 双半命中"）。拆分后两半仍必须平行。
- 文件内有 4 类**仓库根相对链接**：`SECURITY.md`、`CODE_OF_CONDUCT.md`、
  `.github/PULL_REQUEST_TEMPLATE.md`、`docs/BRANCHING.md`（各出现 2 次），
  以及两个页内语言锚点 `#english` / `#中文`。
- 文件内 2 处 ```` ```python ```` 围栏各含一行 `from zoo_framework.workers import BaseWorker`。

**搬进 `docs/` 会撞上三条既存机械校验**（`tests/test_doc_consistency.py`，扫描范围 =
`docs/**/*.md` + 仓库根 `README.md`，**不含**根 `CONTRIBUTING.md`——所以这些约束今天是隐形的）：

| 校验 | 触发条件 | 后果 |
|---|---|---|
| `test_no_cjk_anchor_links` | `](...)` 的锚点含 CJK | 搬入后 `[中文](#中文)` **必然变红**（mkdocs 的 slugify 把中文剥成空锚点） |
| `test_relative_links_resolve` | 相对链接指向磁盘上不存在的文件 | 搬入后 `SECURITY.md` / `docs/BRANCHING.md` **必然变红**（基准目录变了） |
| `test_documented_imports_execute` | python 围栏内的 import 执行失败 | 两个 `from zoo_framework.workers import BaseWorker` 可执行，**不受影响** |

**mkdocs 侧的同类约束**：`mkdocs.yml:143` 已启用 `attr_list`（故可用显式 ASCII 锚点）；
`mkdocs.yml` 末尾的注释本身就写明"`docs/` 下按仓库内相对路径写的链接在站点上不存在，
构建会告警；若要转 `--strict`，需先把这些链接改写为绝对 GitHub URL"。

**外部引用面**（拆分后必须仍然成立）：`GOVERNANCE.md:61/114`、`README.md:415/424`、
`README.zh.md:385/393`、`docs/BRANCHING.md:4/24/48`、`mkdocs.yml:21` 的注释，以及
`tests/test_governance_consistency.py:52` 把 `CONTRIBUTING.md` 列为 README 治理段必须链接的治理文件
——**根 `CONTRIBUTING.md` 必须留在根目录**。

**流程资产的发现机制**（issue 第 6 条要求评估的两问，证据在 Decisions D6）。

## Goals / Non-Goals

**Goals:**

- 入口首屏给出**完整最小路径**（建环境 → 跑测试 → 提 PR）与**免流程通道**，且这两件事在
  中英两半各自开头即可见。
- 完整规范零丢失地落在单一文件，且该文件在**文档站上可读、链接不失效**。
- 仓库内不再有第二份贡献流程描述（今天有 2 份重叠的权威描述 + 1 份与之矛盾的指南）。
- 5 个 good-first-issue 全部具备"文件路径 + 量级 + 验收标准 + 使用者可见结果"，且阻塞关系显式。
- 上述全部属性**由机械测试守护**，而不是靠人记得。

**Non-Goals:**

- 不移动任何文件（详见 D6）——`git mv` 只用于把完整规范从根移到 `docs/`。
- **不修改 `docs/BRANCHING.md`**：它的 `../CONTRIBUTING.md` 死链是 GFI-2 的**交付物**，
  本变更碰了就等于把这个 good-first-issue 做掉（见 proposal 的 GFI 表）。
- 不改 `.github/workflows/**` 的任何判定、不改门禁严格度、不新增第三方依赖、不改 `zoo_framework/**`。
- 不改 `CONTRIBUTING.md` 的**双语契约本身**：精简后仍是中英双半。
- 不追求把文档站链接告警清零（那是 GFI-2 的事），只要求本变更**新增 0 条**。

## Decisions

### D1 拆分的落地方式：`git mv` 完整规范进 `docs/`，根文件另写

`git mv CONTRIBUTING.md docs/CONTRIBUTING_MAINTAINER.md`，再新写一个 ≤100 行的根 `CONTRIBUTING.md`。
这样完整规范的**全部历史**（`git log --follow`）跟着内容走，符合 issue 的"用 `git mv` + 逐段搬移，
不要重写"；新写的根文件是"入口"，本就没有历史可继承。

**替代方案**（不选）：① 复制后两边裁剪 —— 失去 git 的改名检测与历史连续性；
② 在根目录保留完整规范、另建短入口（如 `START_HERE.md`）—— 违反 issue 明确指定 `CONTRIBUTING.md`
必须是精简入口，且入口不在默认文件名上等于没降门槛。

### D2 完整规范进 `docs/` 后的三条改写规则

其一，**语言锚点改显式 ASCII id**：`## 🇬🇧 English {#english}` / `## 🇨🇳 中文 {#zh}`，
页内链接改为 `[中文](#zh)` / `[English](#english)`。（`attr_list` 已在 `mkdocs.yml:143` 启用；
根 `CONTRIBUTING.md` 不进 `docs/**` 扫描范围，GitHub 的 slugify 也保留 Unicode，
故**精简版可保持不变**——只有搬进 `docs/` 的那份必须改。）

其二，**跨出 `docs_dir` 的链接改写为 dev 分支的绝对 GitHub URL**：
`SECURITY.md`、`CODE_OF_CONDUCT.md`、`.github/PULL_REQUEST_TEMPLATE.md` →
`https://github.com/YearsAlso/zoo-framework/blob/dev/<path>`。这正是 `mkdocs.yml` 末尾注释
与 A3（`llms.txt` / README FAQ）采用的既存写法；不改写就会给文档站新增链接告警，与
本变更的验收口径冲突。`docs/BRANCHING.md` → 同目录相对链接 `BRANCHING.md`。

其三，**`docs/` 内的相对链接按新基准重算**，全部由 `test_relative_links_resolve` 兜底。

### D3 免流程通道的写法：两半各一段引用块，位置固定在语言标题之后

在每一半的语言标题下、第一个 `###` 之前放一段 `> ` 引用块（"先读这个"的视觉重量），
内容 = "拼写 / 文档 / 示例 / 注释类改动**不需要** OpenSpec 提案，直接开 PR" +
"完整规范见 `<维护者版>`"。引用块落在此处可保证落在**每半前 20 行内**（两半各自的 `## 🇬🇧/🇨🇳`
标题分别在第 2 / 约 10 行附近）。

**替代方案**（不选）：放在文件末尾的 FAQ —— 违反"前 20 行内可见"；写在半页中部 —— 需要读者
先滚过环境搭建。

### D4 门槛表述：改为"分类"，不删除 SDD

把"必须走 OpenSpec"改写为"**涉及外部可观察行为、兼容性或数据格式的改动**需先写提案；其余
由 CI 与评审把关"，并保留 `openspec validate --strict` 作为提案本身的校验命令。

**与 `openspec/config.yaml` 的冲突评估（issue 要求如实评估）**：**无冲突**。实测该文件只有
`schema: spec-driven` 与一个 `context` 块（正文 zh-CN、结构性标题与 SHALL/MUST 保持英文），
**没有任何"必须为改动创建 change"的机械约束**；`.github/workflows/` 下也没有任何 openspec
校验作业。今天"一律必须走 OpenSpec"的唯一载体是**文档表述与 PR 模板的一个勾选项**，两者都在
本变更的改动范围内。因此降门槛是**表述层面的调整，不需要改动任何工具或门禁**。

### D5 重叠文档的收敛：`docs/contributing/contributing.md` 改成指针页，保留 URL

该页改为短页（贡献方式概述 + 指向完整维护者规范的链接 + 指向 `development.md` / `BRANCHING.md`
的分流），`mkdocs.yml` 的 `贡献指南` nav 项**保持指向它**，并新增 `维护者规范` nav 项指向
`docs/CONTRIBUTING_MAINTAINER.md`。

**替代方案**（不选）：删除该页并把 nav 改指 `CONTRIBUTING_MAINTAINER.md` —— 会 404 掉一个已发布的
页面 URL，且 `docs/contributing/README.md` 的分区表里"读者：改框架的人"这一层会缺一个概述入口。
选保留 URL 也避免触发"所有被移动的文件不再有失效链接"这条验收的反向问题（改动的文件同样不该制造死链）。

### D6 流程资产：不移动，只写文档说明（issue 第 6 条要求的两问，逐条给证据）

**问一：移动 `.claude/` 会破坏自动发现路径吗？—— 会，且是静默破坏。**

实测 `.claude/` 的结构是 5 个**约定目录**：`agents/`(10 文件)、`commands/`(6)、`rules/`(5)、
`skills/`(23)、`workflows/`(8)，**没有 `settings.json`**——即没有任何"把发现路径重定向到
`tools/ai-agents/`"的现有机制可改。而 `.claude/rules/*.md` 的 5 个文件当前正被当作
**project instructions 注入到 AI 会话上下文**（`ask-dont-assume` / `assertion-integrity` /
`plain-summary` / `pyramid-answer` / `sdd`）。改路径的后果是：**5 条项目规则、10 个 agent、
6 个命令、23 个 skill、8 个 workflow 全部静默失效**，且失效时没有任何报错——这与本项目的
"失败要大声"原则直接冲突。仓库内向 `.claude/` 的文本引用只有 2 处（一个测试的 docstring、
一个 change 的 design），所以问题不在文本，在**发现机制**。

**问二：移动 `openspec/changes/archive/**` 会影响 `openspec` 命令吗？—— 会，且路径写死在 CLI 里。**

实测 CLI 源码 `@fission-ai/openspec/dist/core/root-selection.js:67`：

```js
archiveDir: path.join(rootPath, 'openspec', 'changes', 'archive'),
```

`archiveDir` 由 `path.join` 硬拼，**不是配置项**（全仓只有 `changesDir` / `specsDir` / `archiveDir`
三个派生字段，前两者同样硬拼）。`dist/commands/validate.js:442` 会 `readdir(root.archiveDir)`
遍历归档来统计"已归档 change"，`core/archive.js` 会往该目录写入。移动后：`openspec archive`
会在旧位置重建一个空目录，`validate` / `list` 对既有 **126 个归档 change** 的识别能力丢失。

**结论**：两问的答案都是"高风险、且失败静默"——按 issue 的明文授权
（"风险高则只做文档说明，不移动文件"）**不移动**，改为在 `docs/CONTRIBUTING_MAINTAINER.md` 里
新增一节说明这些目录属于**流程资产**、为何不能移动（引用上述两条机制理由）。

### D7 good-first-issue 的 5 条组成与阻塞标注

`good first issue` 标签**已存在**（GitHub 默认标签），当前**无任何 issue 使用它**（实测 `gh issue list
--label "good first issue" --state all` 为空）。5 条按用户已确认的"2 立即可做 + 3 blocked"落地：

| # | 任务 | 落地方式 | 状态 |
|---|---|---|---|
| GFI-1 | `zfc --worker` 在项目外静默成功（`exit_code = 0`、无输出、留下游离 `workers/`，实测复现） | 给现有 #131 打 `good first issue` | 立即可做 |
| GFI-2 | 修文档站唯一死链 `docs/BRANCHING.md:4 → ../CONTRIBUTING.md` | 新建 issue | 立即可做 |
| GFI-3 | 脚手架 demo Worker 增加一行更清楚的输出 | 新建 issue，**blocked by #110** | 阻塞 |
| GFI-4 | `example/` 增加一个 FastAPI 集成示例 | 新建 issue，**blocked by #116** | 阻塞 |
| GFI-5 | 补一组 FAQ 问答（中英各一问一答） | 新建 issue，**blocked by #122** | 阻塞 |

**被剔除的候选方向**（issue 原文列出的另两条，均以实测否掉）：

- 「补 README 英文站缺失章节」——两份 README 的三级标题 **15 : 15 逐一平行**（`grep -n "^### "`），
  没有"缺失章节"；文档站按 `mkdocs.yml` 的 `language: zh` 只有中文，补英文站点不是 30 分钟量级。
- 「给错误信息增加可搜索的关键词」——用户可见的报错串已是可检索英文短语（如
  `Must inherit from BaseWorker: …`）；`core/adaptive/stats_store.py:125,129` 的两处中文 `TypeError`
  被同函数的 `except (KeyError, TypeError, ValueError, AttributeError, json.JSONDecodeError)`
  就地捕获，**从不外泄给使用者**。

另注：issue 候选里的依赖编号按**今天的实际状态**标注（`#110` / `#116` / `#122` 实测均 OPEN），
不用 issue 正文里的快照。

### D8 门禁放宽建议的落点：维护者规范的独立小节 + 台账交叉引用

在 `docs/CONTRIBUTING_MAINTAINER.md` 新增一节列出**建议放宽**的候选（如"覆盖率的
`--cov-fail-under=30` 对 0.x 阶段偏高"），每条标注**建议、尚未生效**，并从
`docs/contributing/maintainer-backlog.md` 交叉引用一行。

**替代方案**（不选）：只写进 `maintainer-backlog.md` —— 该页自己的口径是"issue tracker 是唯一真源，
本页只写一行索引、不复制正文"，建议条目没有对应 issue，塞进去会破坏该页的口径；新建第四份文档 ——
又制造一个重复源。

### D9 机械校验：新增 `tests/test_contributor_ramp.py`

沿用本仓库的"**单份手写真源 + 机械测试**"惯用法（与 `tests/test_agent_discoverability.py`、
`tests/test_governance_consistency.py` 同构）：`REPO_ROOT = Path(__file__).resolve().parents[1]`、
中文 docstring 并写明「牙齿」、断言失败信息给出可执行修法。覆盖范围见 `tasks.md` 第 6 节。

**唯一手写真源的选取**：`CONTRIBUTING.md` 的**提交去向**与**响应天数**这类事实很容易在
多处漂移，故测试断言"两份 README 的天数与 `MAINTAINERS.md` 一致、且都链接到
`MAINTAINERS.md`"，而不是断言某个具体天数——天数只有一个权威源。

## Risks / Trade-offs

- **[精简入口砍掉内容后，贡献者看不到全部门禁细节]** → 精简版 MUST 链到维护者版（机械断言），
  且维护者版 MUST 含原 13 个章节标题（机械断言，防"搬丢了"）。
- **[100 行口径歧义]** 按**文件总计 ≤100 行**（双半各 ≤60）落地并写进 spec 与测试；
  若按"每半 100 行"理解则等于没减负。
- **[新增第 3 份贡献者文档被视为又一层重复]** → 同时把 `docs/contributing/contributing.md`
  从 414 行收敛成指针页，净体量下降而非上升；并在 `docs/contributing/README.md` 的分区表里
  明确三者的分工（入口 / 完整规范 / 概述与分流）。
- **[`CONTRIBUTORS.md` 初始只有维护者，可能被读成"没人用"]** → 写明收录方式与欢迎语；
  SHALL NOT 声称任何未经核实的第三方贡献者或使用者（与 `ADOPTERS.md` 同口径）。
- **[搬移后链接失效]** → D2 的三条改写规则 + `test_relative_links_resolve` 兜底 +
  `test_no_cjk_anchor_links`（搬入 `docs/` 后**这条会立刻变红**，是本次最容易踩的坑）。
- **[新增 `docs/` 页面未入 nav]** → 会产生"not in nav"提示（非告警）：D5 已为
  `CONTRIBUTING_MAINTAINER.md` 与 `GOOD_FIRST_ISSUES.md` 加 nav 项。
- **[文档站链接告警增加]** → 验收口径 = 非 strict 构建的新增链接告警为 **0**（基线 1 条 =
  `docs/BRANCHING.md` 的既存死链，属 GFI-2，本变更不碰）。
- **[ruff-format 会重排 markdown 里 ```python 围栏]** → 既知坑：提交前对改动的 `.md` 先跑一次
  `pre-commit run ruff-format`，把重排结果一并 staged（否则提交会被钩子中止）。
- **[GFI 在被依赖项就绪前无人能做]** → 显式 `blocked by` 标注 + `docs/GOOD_FIRST_ISSUES.md`
  区分"可立即开始/暂不可开始"，避免贡献者踩空后失去信任。
- **[GitHub 侧动作不可回滚成代码]** → 创建 issue 与打标签是外向动作，需用户单独授权；
  回滚需手工去除标签/关闭 issue（代码 revert 不会撤销它们）。

## Migration Plan

- **无运行时迁移**：改动全部是 markdown、一个新增测试文件、一个 PR 模板勾选项、mkdocs nav 与注释；
  `zoo_framework/**` 不受影响，无配置键、无持久化格式、无公共 API 变更。
- **执行顺序**（apply 阶段）：先建 GitHub issue 拿到编号 → 再写 `docs/GOOD_FIRST_ISSUES.md`
  （编号必须回填真实值，不允许占位）→ 再拆 `CONTRIBUTING.md` → 最后收敛重叠文档与 README。
- **回滚**：`git revert` 单个提交即可恢复文档与测试；GitHub 上的 5 个 issue 与标签需手工处理。
- **生效范围如实标注**：README / 文档站的改动**合并到默认分支后才对外可见**——本变更只保证
  文件与构建就位，不声称"已生效"（与 `#121`、`#122` 同一口径）。

## Open Questions

（无。已知的未决项都已在本文档内决策；`docs/GOOD_FIRST_ISSUES.md` 的 issue 编号属 apply 阶段的
执行顺序问题，不是未决设计问题。）
