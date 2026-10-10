# 设计：roadmap-user-facing

## 决策

### D1: ROADMAP 重写为何落在 `docs/contributing/roadmap.md` 原路径？

issue 中写的是 `docs/ROADMAP.md`，但仓库实际布局是 `docs/contributing/roadmap.md`
（docs 站导航 mkdocs.yml:96、README 双语链接、docs/contributing/README.md 均指向该路径）。
**保留原路径原地换血**，避免三处入口链接失效；不新增 docs/ROADMAP.md 别名（不制造
第二真源，同一能力只留一个 URL）。

### D2: BUSINESS_PLAN 降级到什么程度？

三方案：
- **方案 A（选定）：保留在 docs/internal/，仅去冲突**——该文档是维护者当初的
  商业可行性思考记录，删除即丢失决策上下文；它已不在 mkdocs 发布范围
  （mkdocs.yml:118 注释排除 docs/internal/），对外曝光面为 GitHub 代码搜索，
  去掉绝对化用语与死链即可满足"不与 README 冲突"的验收。
- 方案 B：移入 openspec 归档作为历史记录——过度迁移，openspec 是规格体系不是文档回收站，架构不一致。
- 方案 C：整篇删除 + CHANGELOG 说明——丢失决策记录，违反业务逻辑连续性。

改动量最小（约 ±10 行），架构一致性（docs/internal/ = 维护者工作日志的既定分区）与
业务连续性（保留可行性思考）都满足。

### D3: roadmap 条目如何保证"可被使用者感知"？

每条强制三字段骨架：**能做什么了**（使用者视角一句话）/ **影响谁** / **怎么知道
做完了**（可观测的完成判据，不写"覆盖率 80%"这类内部指标）。条目从四个来源考据，
不凭空发明：

1. 已有 openspec 能力/change 里已确认的方向（如 adaptive-scheduling、native SDK #139）；
2. issue #118 列举的 6 个方向（跨平台一致、cron、OTel、Web 集成、指标链路、Python 门槛）；
3. README 已声明但未兑现的"承诺兑现"类（指标链路接通）；
4. zoo-bench / benchmark.md 已测出的纯 Python 优化兑现（DECISION.md 四项 12x~800x）。

Later 区允许"在考虑"的开放项，但每条仍须是使用者可感知的能力句式，不许是
"重构 X 模块""引入 Y 框架"这类实现语言。

### D4: maintainer-backlog 的收录口径

收录**: 对使用者无直接感知、但影响可信度/合规/开发者体验债务的 open issue 与流程项**。
当前考据（21 open issues 扫描）收录候选：

| 类别 | 项（issue #） |
|---|---|
| 打包/规范 | PEP 639 许可证 + CITATION.cff + SBOM（#119）、requires-python 门槛（#124）、类型注解（#141） |
| 安全/供应链 | 安全收口 + SECURITY_MODEL.md（#121）、native CI/wheel（#129） |
| 可发现性 | llms.txt/AGENTS.md（#122）、上游集成（#138）、native SDK（#139） |
| 流程/合规 | OpenSSF 徽章前置材料（#120）、总纲与工作队列（#125，元 issue） |
| 工程债 | macOS 间歇红（#144）、zfc --worker 契约（#131）、类名 PascalCase（#112）、原生字节包络（#130） |

不收录: 已关闭/已归档（#114~#117 已在本分支落地）。

backlog 每条注明 issue 编号与状态快照日期，不复制 issue 全文（避免双源漂移，
issue 本身是真源，backlog 只做索引）。

### D5: 结构——Now / Next / Later 三档

- **Now（进行中）**：有 in-flight change 或已合并但未发版的项。考据当前
  openspec/changes/ 非归档目录 + 最近 CHANGELOG [Unreleased]，诚实标注状态
  （如"已合并发版待验证"），不把已完成的写成"进行中"占位。
- **Next（已确认要做）**：issue 里已立项（有编号）的能力项。 规模预期 ≤6 条。
- **Later（在考虑）**：issue #118 里"供评审"的方向、尚未立项的。允许开放措辞
  （"评估……哪些值得做"），但须是能力句式。

每档 ≤3 行/条，整页 ~100 行——verifiable 的落点是"每条三字段齐全 + 无内部债务词"，
由 spec delta 的 SHALL 承载，不引入机械测试（条目语义无法用 grep 判定，机械校验
会漂移成摆设；与 docs-consistency-sweep 的教训一致——枚举式检查不如机制）

## 文件清单

| 文件 | 动作 | 要点 |
|---|---|---|
| docs/contributing/roadmap.md | 重写 | Now/Next/Later + 三字段骨架 + 顶部反链 backlog |
| docs/contributing/maintainer-backlog.md | 新建 | 按类别索引 + issue 编号 + 快照日期 |
| docs/internal/business-plan.md | 修订 | 去绝对化用语、修死链 |
| docs/contributing/README.md | 修订 | 表格加一行 backlog 入口 |
| mkdocs.yml | 不动 | 路径不变，导航自动收录 |
| README.md / README.zh.md | 不动 | 链接已存在且路径不变 |

## 风险与缓解

- **条目考据不足**：只从 openspec change / issue / README / bench DECISION 四处
  已定方向取材；无法考据的就不写，宁缺毋滥（与 CHANGELOG 回填同一口径）。
- **backlog 与 issue 双源漂移**：backlog 只存索引（issue 编号 + 一句话），状态
  细节留在 issue；条目失败闭环（issue 关闭时 backlog 行同步归档/删除）写进 spec 的场景。
- **"路线图"从商业叙事换成能力叙事的读者落差**：在页首保留一段"本页与
  maintainer-backlog 的分工"说明，管理预期。
