# docs-roadmap Specification

## Purpose
本能力规定路线图文档的读者定位与口径：面向使用者陈述能力（不搬内部 backlog），与既有文档口径一致，索引只做指针不复制内容，并随文档站同步收录。

## Requirements

### Requirement: ROADMAP 面向使用者陈述能力

`docs/contributing/roadmap.md` SHALL 以使用者可感知的能力句式陈述路线图条目，
 SHALL NOT 混入仅维护者关心的内部债务或流程项。

每一条目 SHALL 包含三个字段：

- **能做什么了**（使用者视角，写"你将能…"或"你现在能…"）；
- **影响谁**（目标使用场景）；
- **衡量方式**（可观测的完成判据，譬如"文档站出现 X 页""配置键 Y 可用"，而 NOT 内部过程指标）。

条目 SHALL 按 Now（进行中）/ Next（已确认）/ Later（在考虑）三档组织，单条
不超过 3 行。

内部债务、CI 修复、合规材料、重构类工作 SHALL NOT 出现在该页条目中；该页顶部
SHALL 指向 `docs/contributing/maintainer-backlog.md` 并说明分工。

#### Scenario: 条目句式与字段完整性

- **WHEN** 审阅 `docs/contributing/roadmap.md` 任一条目
- **THEN** 该条目以使用者视角陈述能力（不含"重构/引入/修复 CI"式实现语言）
- **AND** 三字段（能做什么了 / 影响谁 / 衡量方式）齐全且"衡量方式"是可观测判据
- **AND** 页内不存在内部债务条目（bug 修复、覆盖率、合规徽章等）

#### Scenario: 内部债务有独立去处

- **WHEN** 维护者想查看当前未落地的内部项
- **THEN** `docs/contributing/maintainer-backlog.md` 存在并按类别索引
- **AND** ROADMAP 顶部一句话反链该文件说明分工

### Requirement: ROADMAP 与既有文档口径一致

`docs/contributing/roadmap.md` SHALL NOT 与 README、`docs/benchmark.md` 各自声明的
事实冲突，包括但不限于：健康监控 statement 不得比 README 限制表更乐观
（指标链路未接通须如实承认）；性能声明 SHALL 以 zoo-bench / `docs/benchmark.md`
为证据来源；版本门槛 SHALL 与 `pyproject.toml` 的 `requires-python` 一致。

#### Scenario: 与 README 限制表一致

- **WHEN** roadmap 页陈述健康监控（SVM）相关能力
- **THEN** 承认"指标链路未接通"的现状（与 README.md 限制表同一口径），任何
  指标相关条目以"接通指标链路"为完成判据
- **AND** 页内无"生产就绪（已验证）"式无公开证据的绝对化评级

#### Scenario: 证据来源锚定

- **WHEN** roadmap 页引用性能或基准数据
- **THEN** 指向 zoo-bench 仓库或 `docs/benchmark.md`，不使用内部项目作为公开证据

### Requirement: maintainer-backlog 索引不复制内容

`docs/contributing/maintainer-backlog.md` SHALL 只做索引（类别 + issue 编号 +
一句话描述 + 状态快照日期），SHALL NOT 复制 issue 正文；条目 SHALL 在对应
issue 关闭时归档或删除，避免与 issue tracker 双源漂移。

#### Scenario: 索引式条目

- **WHEN** 审阅 maintainer-backlog 任一条目
- **THEN** 条目含 issue 编号（可点击链接）、一句话描述、最近一次核对日期
- **AND** 不存在从 issue 复制的长段落正文

### Requirement: business-plan 不再与对外文档冲突

`docs/internal/business-plan.md` SHALL 保留为维护者内部材料（不进入文档站构建），
但 SHALL 去除与 README/roadmap 冲突的绝对化声明："生产就绪/已在生产验证"仅可
以维护者实测为由的限定表述出现，评估、监控能力不得表述为"完善"；指向 roadmap
的链接 SHALL 使用当前有效路径。

#### Scenario: 冲突用语清理

- **WHEN** 对 `docs/internal/business-plan.md` 全文检索"生产就绪""完善""自动故障检测"
- **THEN** 任一出现处均带限定（指标链路未接通等现状说明）或已删除
- **AND** 不再有指向已删除路径（如 `ROADMAP.md`）的链接

### Requirement: 站点与索引收录同步

`mkdocs.yml` 导航、`docs/contributing/README.md` 与 README 双语链接 SHALL 与
变更后的文件布局一致：roadmap 页路径不变；`docs/contributing/README.md` SHALL
同时列出路线图与维护者待办两个入口；`mkdocs build` SHALL 通过（无 dead link）。

#### Scenario: 导航与索引无死链

- **WHEN** `mkdocs build` 构建
- **THEN** 构建成功且无 dead-link 报错
- **AND** `docs/contributing/README.md` 的表格含"路线图"与"维护者待办"两行
