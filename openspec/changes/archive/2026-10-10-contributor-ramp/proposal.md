## Why

本项目**零外部贡献者**，而把潜在贡献者挡在门外的不是代码，是**入口的成本结构**（issue #123）。
2026-10-10 在本 worktree 实测：

| 项 | 实测 |
|---|---|
| `CONTRIBUTING.md` | 单文件 **542 行**（中英两半各约 271 行），要求读完分支规范、提交规范、质量门禁、类型门禁与 OpenSpec 流程 |
| 贡献者文档份数 | **3 份重叠**：根 `CONTRIBUTING.md`、`docs/contributing/contributing.md`（414 行）、`docs/BRANCHING.md` |
| `.claude/` | 52 文件 / 5,333 行 |
| `openspec/changes/archive/` | 126 文件 / 6,411 行 |
| 产品代码 | 12,265 行 |
| 仓库对外信号 | `forks = 0`、`stars = 0`、`watchers = 1`；最近 30 条 issue/PR **全部**由维护者提交；**没有任何带 `good first issue` 标签的 issue** |

结论：**流程资产（≈11,700 行）已经接近产品代码（12,265 行）**，而收益侧是空的——没有
good-first-issue、没有贡献者名单、README 只承诺"尽力而为"。一个想修 typo 的人需要先理解
作者整套方法论，这是 0 star 项目唯一的天然增长渠道被自己焊死。

一句话：**入口的门槛要降、收益要可见，其余材料照旧，只是换个位置。**

## What Changes

- **`CONTRIBUTING.md` 拆成两份**：根文件变为面向外部贡献者的**精简入口**（验收口径为
  **文件总计 ≤ 100 行**——它是中英双半，故每半约 45 行），只保留五件事：建环境 → 跑测试 →
  提 PR → **哪些改动不需要流程** → 怎么提问；原有完整规范**逐段搬移**（`git mv` + 剪切粘贴，
  不重写）到新增的 `docs/CONTRIBUTING_MAINTAINER.md`。
- **免流程通道写进显著位置**：拼写 / 文档 / 示例 / 注释类改动 **不需要** OpenSpec 提案，
  直接开 PR。该声明 MUST 出现在**每一半的前 20 行内**（两半各自可见，不必翻过语言切换）。
- **门槛表述降级**：把"一律必须走 OpenSpec"改为"**涉及外部可观察行为、兼容性或数据格式的
  改动**需先写提案；其余由 CI 与评审把关"。**已实测：与 `openspec/config.yaml` 不冲突**——
  该文件只固定产物语言（zh-CN）与结构性标题英文，没有任何"必须走 OpenSpec"的机械约束；
  CI 里也没有 openspec 校验作业，唯一入口是 PR 模板的一个勾选项。
- **新增 `docs/GOOD_FIRST_ISSUES.md` + GitHub 上落地 5 条可上手任务**：每条含具体文件路径、
  30 分钟量级、明确验收标准、**对使用者可见的结果**。其中 **2 条立即可做**（给 #131 与新建的
  死链 issue 打 `good first issue` 标签）、**3 条标注 `blocked by`**（#110 / #116 / #122 实测均
  OPEN）——**暂不可开始的 3 条不打该标签**，避免把人引向一条走不通的路径。
- **贡献者收益可见**：新增 `CONTRIBUTORS.md`（初始仅维护者，写明"欢迎成为下一位"）；
  README 中英两份把"尽力而为"改成**可预期的承诺**，并以 `MAINTAINERS.md`（已写明"issue 或
  PR → 7 天内首次回应"）为唯一权威，避免第二份数字。
- **收敛重叠文档**：`docs/contributing/contributing.md` 改为指向 `docs/CONTRIBUTING_MAINTAINER.md`
  的指针——它已声称覆盖"分支规范、提交规范、质量门禁、OpenSpec 流程"，且第 31 行
  `# 从 main 分支创建功能分支` 与 `dev → main` 双分支模型**矛盾**（实测）。
- **流程资产可见性：只写文档，不移动文件**（见 design 的风险评估）：`.claude/` 是工具约定
  的发现路径，`openspec/changes/archive/` 是 `openspec` CLI 自身的归档路径——移动会让本仓库
  的 AI 工作流与归档命令同时失效。改为在维护者文档里说明"这些目录是流程资产、不是产品代码"。
- **不新增第三方依赖、不改 `zoo_framework/**` 任何行为、不改变任何 CI 门禁的严格度**
  （"哪些门禁建议放宽"只作为**建议**列入，由维护者决定）。

## Capabilities

### New Capabilities

- `contributor-experience`: 贡献路径的**入口契约**——精简入口的行数与必备内容、免流程通道的
  位置与适用范围（与 SDD 口径一致，不得相互矛盾）、完整维护者规范的**单点存放与零丢失**、
  good-first-issue 的入选标准（文件路径 / 量级 / 验收标准 / 使用者可见结果）、贡献者收益的
  可见性（名单 + 可预期的响应承诺，且承诺数字只有一个权威源）。

### Modified Capabilities

（无。本变更不改变任何既有能力的规范级行为——它只重塑贡献者入口与叙述，不改产品的可观察行为。）

## Impact

- **新增文件**：`docs/CONTRIBUTING_MAINTAINER.md`、`docs/GOOD_FIRST_ISSUES.md`、
  `CONTRIBUTORS.md`、`tests/test_contributor_ramp.py`（机械校验）。
- **修改文件**：`CONTRIBUTING.md`（542 → ≤100 行）、`docs/contributing/contributing.md`
  （改为指针）、`docs/contributing/README.md`（表格一行）、`README.md` / `README.zh.md`
  （贡献段与响应承诺）、`.github/PULL_REQUEST_TEMPLATE.md`（`openspec/` 勾选项允许"不适用"）、
  `mkdocs.yml`（nav 新增「维护者规范」与「Good First Issue」两项 + 注释里对 CONTRIBUTING 分支规范的引用）。
- **GitHub 侧动作**：新建 4 个 issue（GFI-2 ~ GFI-5），并给其中**可立即开始的 2 条**
  （#131 与新建的死链 issue）打 `good first issue` 标签（已获用户授权）。
- **不改**：`zoo_framework/**`、`tests/**` 既有断言、`.github/workflows/**`（门禁严格度）、
  `openspec/config.yaml`、`CONTRIBUTING.md` 的既有中英双半结构契约、`docs/FAQ.md`。

**实测与口径（本机 2026-10-10，非转述）**

1. **issue 候选方向核实**：`补 README 英文站缺失章节` **不成立**——两份 README 的三级标题
   **15 : 15 逐一平行**（`grep -n "^### "`），文档站按 `mkdocs.yml` 的 `language: zh` 只有中文，
   补英文站点不是 30 分钟量级。`给错误信息增加可搜索的关键词` 经核实**不适用**——用户可见的
   报错串已是可检索英文短语（"Must inherit from BaseWorker …" 等），而 `core/adaptive/stats_store.py`
   的两处中文 `TypeError` 被同函数的 `except (KeyError, TypeError, …)` 就地捕获、从不外泄。
   两条均以**实测可行的**条目替换（见 design 的「候选方向核实表」）。
2. **`#112`（zfc 类名 PascalCase）经实测已实现**：`_worker_names("My_Task")` 返回
   `('My_Task_worker', 'MyTaskWorker')`，不再是 issue 里的 `My_TaskWorker`——故它**不是**
   good-first-issue 的候选（已有独立变更 `scaffold-worker-naming`）。
3. **`#131` 实测复现**（用作立即可做的 GFI）：在非项目目录执行 `zfc --worker my_task`，
   `exit_code = 0`、**无任何输出**、并在当前目录生成了游离的 `workers/`。
4. **`docs/BRANCHING.md` 是文档站唯一死链**（链接 `../CONTRIBUTING.md`，目标不在 docs 目录内）
   ——用作第 2 个立即可做的 GFI。
5. **免责/范围口径**：本变更只重塑**入口**，不改变任何门禁的严格度；`.claude/` 与
   `openspec/changes/archive/` **不移动**，只在维护者文档里说明其性质——理由是二者都是
   **工具的约定路径**（移动即失效），属 issue 明文允许的"风险高则只做文档说明"分支。

**风险**

① 精简入口砍掉完整规范后，贡献者**看不到**全部门禁细节——靠"完整规范在
`docs/CONTRIBUTING_MAINTAINER.md`"的显著链接与**机械断言**（精简版 MUST 链到维护者版）
兜底；② "≤100 行"是**文件总计**口径（双半各约 45 行），若按每半 100 行理解则等于没减负；③
新增第 3 份贡献者文档会被 `docs/contributing/` 的既有分区规定质疑——故同时把重叠的第 2 份
收敛为指针，净增为 0；④ `CONTRIBUTORS.md` 初始只有维护者，若被读成"没人用"反而减分——须
写明"名单按合入时间排列，欢迎成为下一位"，且**不得**声称任何未经核实的第三方使用者。
