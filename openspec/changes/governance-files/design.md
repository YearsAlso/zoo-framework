# 设计：governance-files

## 决策

### D1: `security.txt` 的可达性——用 mkdocs 构建钩子，而不是在 `docs/` 里放副本

**用户选定方案 A（构建钩子）**。三方案对比：

| 方案 | 收益 | 风险 | 改动量 | 结论 |
|---|---|---|---|---|
| **A. mkdocs `hooks:` + `on_post_build` 复制** | 本地 `mkdocs build` 与 CI 行为一致，验收标准"可达"可在合入前**本地验证**；站点组装仍只在 mkdocs 一处 | 新增一个 ~20 行脚本；依赖 mkdocs ≥1.4 的 hooks 特性（CI 与本地都装最新版） | `mkdocs.yml` +3 行、新脚本 ~20 行、`docs.yml` +1 行 | **选定** |
| B. `docs.yml` 构建后 `cp` | 不新增 Python 文件 | 站点组装被拆到两处（mkdocs + 工作流）；本地构建复现不出镜像，验收只能部署后回看 | `docs.yml` +5 行 | 未选 |
| C. 只留根文件，`Canonical` 写 raw 直链 | 零构建机制 | `Canonical` 不是标准位置，对只扫 `/.well-known/` 的工具不可见，评估者观感差 | 0 | 未选 |

**两条实测结论支撑本决策**（都是本次真跑出来的，不是推断）：

1. **mkdocs 忽略点开头的目录**：在 `docs/.well-known/` 放探针文件、
   `docs/probe-plain.txt` 放一份非点开头的对照，构建后 `site/probe-plain.txt` 存在
   而 `site/.well-known/` **不存在**。故 issue #120 里"把文件同时放到
   `docs/.well-known/`"按字面做**不会**让它可达。
2. **GitHub 不 serve 仓库根的 `.well-known/`**：对三个确有该文件的仓库
   （`SAP/open-ux-tools`、`internetstandards/Internet.nl`、`QubesOS/qubesos.github.io`）
   请求 `https://github.com/<owner>/<repo>/.well-known/security.txt` 均返回 **404**。
   所以"放在根目录就自然可达"不成立，可达性必须由我们自己的发布路径提供。

**落地要点**：

- 真源唯一：只有仓库根 `.well-known/security.txt`；`docs/` 下**不放**副本（放副本既
  不可达、又制造漂移）。复制发生在构建期，产物在 gitignore 的 `site/` 内，不入库。
- 钩子从 `config['config_file_path']` 定位仓库根，`Path(config['site_dir'])/'.well-known'`
  为落点；**源文件缺失即 `raise`**（"看起来成功但没有 security.txt" 的站点比没有更糟）。
- `docs.yml` 的 `on.push.paths` 补 `.well-known/**`：该工作流只在 `main` 上构建部署，
  触发路径不覆盖源文件时，单独改 `Expires` 不会重新发布。
- 诚实边界：dev→main 合并并部署完成后 URL 才真正可达；`Canonical` 写的就是该 URL。

### D2: `CODE_OF_CONDUCT.md` 的处置——保留 v2.1、如实披露、另立迁移 issue（用户选定方案 B）

**核对结果**：官方仓 `EthicalSource/contributor_covenant`（默认分支 `release`，
最近推送 2026-05-20）已发布 **v3.0**（`content/version/3/0/code_of_conduct.md`，
99 行，含官方 `code_of_conduct.zh-cn.md` 译本）。本仓写的是
"参考 Contributor Covenant v2.1 制定，并按本项目规模做了精简"。

**用户选定 B**：本变更不迁移版本，只在 CoC 顶部如实披露"官方当前版本已是 v3.0、
本仓仍基于 v2.1 的精简改写版、迁移跟踪于 issue #<迁移 issue>"，另开 issue 跟踪迁移。
理由（也写进迁移 issue）：v3.0 是结构性重写（Encouraged / Restricted Behaviors、
Community Moderators 术语、四级执行阶梯、必须自填举报方式），属于政策文本层面的
独立工作，与"补齐治理材料"不是同一关注点；一个变更一个关注点。

**举报路由（用户选定 A：同一邮箱 + 主题前缀分流）**：

- CoC 举报：`mengxiang931015@live.com`，主题以 `[Code of Conduct]` 开头；
- 平台级骚扰：GitHub 自带的 Report abuse（平台机制，不依赖维护者）；
- 文中显式说明这两条路与**安全漏洞**报送（优先 GitHub 私密安全通告）是不同路径；
- 如实写明单人项目无法提供独立第三方受理，并保留"维护者本人是报告对象"时的处置。

> `SECURITY.md` 的邮箱与本条相同——单维护者项目不可能有真正独立的第二联系人。
> 因此"区分开"落在**路由约定**上（主题前缀 + 平台举报入口），并把这个事实写明，
> 而不是编造一个不存在的新邮箱。

### D3: `ADOPTERS.md` 的条目与口径

依据：`docs/FAQ.md` 已写下"**目前没有可核实的外部使用者。**维护者自己的私有项目在
用，但那**无法被读者核实**，因此不作为证据列出。这是一个诚实的空缺。"——
`ADOPTERS.md` 必须与该口径一致，不能因为多了一个文件就产生更乐观的说法。

本次可列的两条，都能落到可核对的依据或显式标注：

| 条目 | 标注 | 依据（已核对） |
|---|---|---|
| 维护者自己的私有项目 | **不可核实**——读者无法核对，不作为证据 | 无外部依据，如实说明 |
| `YearsAlso/zoo-code-agent` | **可核实**，但**属维护者自己的**消费者（演示 + 框架 Agent 线验证），**非第三方生产使用者** | 其 `pyproject.toml` 声明 `zoo-framework==0.8.0`；仓库自述为"最小 agent 消费者（演示 + 验证消费方）"；本仓以 submodule 形式固定在 `example/agent` |

结构：先写"如何在生产中使用 → 提 PR 把自己加进来"的邀请句，再列条目；空位是邀请句，
不是留白。`docs/FAQ.md` 里那条指向 `ADOPTERS.md` 的链接由此从悬空变为可解析
（FAQ 文字不动）。

### D4: `GOVERNANCE.md` 的写法——如实单人维护

- **不做的事**：不写技术委员会／章程／选举／投票流程（本项目都没有）；
  不承诺 SLA；不引入 `ROADMAP.md` 之外的新规划。
- **写清五件事**：谁在维护（1 人）、怎么决策（维护者在公开 issue/PR 上裁量 +
  书面理由，重大取舍走 OpenSpec change 留档）、怎么成为共同维护者（持续贡献 →
  邀请，`CODEOWNERS` 已按此预留）、冲突怎么解决（先直接讨论 → 升级到维护者裁定 →
  CoC 流程处理行为问题）、版本与破坏性变更承诺（指向 `docs/VERSION_POLICY.md` 与
  `docs/MIGRATION.md`，不重述以免漂移）。
- **交叉引用**：维护者名单以 `MAINTAINERS.md` 为准，本文不再列一遍（避免两处人数漂移）。

### D5: 机械校验承担验收项（`tests/test_governance_consistency.py`）

issue 的验收项里有四条是**可机械判定**的：字段齐备、`Expires` 未过期、渠道一致、
引用不悬空。按仓库既有做法（`tests/test_doc_consistency.py` 的先例）把它们变成 CI
能拦的断言，而不是留在人工清单里（人维护的清单会漂移）：

| 断言 | 防的是什么 |
|---|---|
| `security.txt` 五字段齐备 + `Expires` 可解析且晚于当日 | 过期文件被发布出去 |
| `Contact` 的邮箱/URL 均出现在 `SECURITY.md` | 改了安全政策渠道而 security.txt 未同步 |
| 治理文件的相对链接目标存在 | README／FAQ 里的悬空引用 |
| 两份 README 的治理小节链接集合相同且含全部七个入口 | 中英 README 漂移 |
| `GOVERNANCE.md` 不出现"技术委员会/TSC/章程/选举"，且维护者人数与 `MAINTAINERS.md` 一致 | 模板文字回潮、人数漂移 |
| `ADOPTERS.md` 每条目带「可核实」（附依据）或「不可核实」标注 | 编造使用者 |
| `docs/` 下不存在 `.well-known/security.txt` 副本；`mkdocs.yml` 声明钩子；`docs.yml` 触发路径含 `.well-known/**` | 可达性机制被静默移除 |
| 钩子函数在 `site_dir` 落点写入、真源缺失时 `raise` | 钩子退化成"静默跳过" |

钩子脚本用 `importlib` 按路径加载（`scripts/` 不是包），因此测试**不依赖 mkdocs**
（`dev` extra 不含 mkdocs，CI 的测试作业也没装它）。

**带牙齿的验收方式**：写完测试后注入违规实现（把 `SECURITY.md` 的邮箱改掉 / 删掉
`docs.yml` 的触发路径条目）确认对应断言变红，再按 md5 逐字节还原。

### D6: 明确不做的事

- **不迁移 CoC 到 v3.0**（D2，另立 issue）。
- **不改 `SECURITY.md` 的政策文本**——渠道不变，只是被 `security.txt` 引用。
- **不把治理链接加进文档站 `nav`**：站点首页是 `docs/README.md`，与仓库根 `README.md`
  是两份文件；issue 只要求 README 可点到，未要求站点页。
- **不引入第三方依赖**，不动 `pyproject.toml` 依赖与发布工作流。
- **不动 `docs/contributing/maintainer-backlog.md`**：该页是 issue 索引，迁移 issue 建立
  后是否补一行由后续维护者决定，本次不顺手改（避免与本变更范围无关的改动）。

## 风险

- **mkdocs hooks 版本特性**：`hooks:` 需 mkdocs ≥1.4；`docs.yml` 与本地都装最新版，
  风险低。若失败，兜底方案是 B（工作流里 `cp`），已在 D1 表内留档。
- **Pages 部署时序**：`docs.yml` 只在推 `main` 时构建部署，因此可达性在 dev→main
  合并后成立；本地构建验证产物路径，不能验证线上 URL。
- **`Expires` 会过期**：文件里的日期是硬编码的，过期后机械校验（D5）会红——这是
  刻意设计：让续期成为一次必须动手的事，而不是静默过期。
- **治理声明与现实的偏离**：人数、响应下界都是可被现实证伪的声明；写作时按当前
  真实情况（1 人、尽力而为）落笔，宁可保守。
