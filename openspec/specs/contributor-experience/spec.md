# contributor-experience Specification

## Purpose
定义外部贡献者进入本项目的**入口契约**：入口文档的规模上限与必备内容、免流程改动的适用范围与位置、
完整规范的单一存放点与零丢失、可上手任务的入选标准，以及贡献者能看到的回报。它约束的是
"一个陌生人从看到仓库到提第一个 PR"这段路径的可观察属性，不约束任何产品行为。

## Requirements

### Requirement: 精简贡献者入口

根 `CONTRIBUTING.md` SHALL 作为面向外部贡献者的精简入口，**文件总计不超过 100 行**（该文件为中英双半，
故每半约 45 行），且 MUST 覆盖五类内容：如何搭建环境、如何运行测试、如何提交 PR、**哪些改动不需要流程**、
如何提问。精简入口 MUST 以显著方式给出完整维护者规范的位置。

#### Scenario: 入口行数不超过上限

- **WHEN** 统计根 `CONTRIBUTING.md` 的总行数
- **THEN** 总行数 ≤ 100，且中英两半各不超过 60 行

#### Scenario: 五类内容齐备

- **WHEN** 在根 `CONTRIBUTING.md` 中查找环境搭建、运行测试、提交 PR、免流程改动、提问渠道五类内容
- **THEN** 两类语言各有五类内容的对应段落，且每类至少给出一条可执行的具体做法（命令、链接或模板）

#### Scenario: 精简入口链向完整规范

- **WHEN** 检查根 `CONTRIBUTING.md` 的每一半
- **THEN** 每半都包含指向完整维护者规范的链接，且链接目标文件真实存在

### Requirement: 免流程通道

贡献者文档 SHALL 明确：拼写、文档、示例、注释类改动**不需要** OpenSpec 提案，直接提交 PR 即可。
该声明 MUST 出现在根 `CONTRIBUTING.md` **每一半的前 20 行内**（两半各自可见，无需翻过语言切换）。
文档 MUST 同时说明：涉及外部可观察行为、兼容性或数据格式的改动需先写提案。文档中 SHALL NOT 出现
"任何改动一律必须走 OpenSpec"这类与免流程通道相矛盾的绝对表述。PR 模板中关于提案/delta spec 的勾选项
MUST 允许贡献者标注"不适用"。

#### Scenario: 免流程声明位于显著位置

- **WHEN** 取根 `CONTRIBUTING.md` 中英两半各自的前 20 行
- **THEN** 两段中都出现免流程声明，且该声明的措辞明确表达"无需提案/不需要流程"

#### Scenario: 门槛表述与免流程通道不矛盾

- **WHEN** 通读根 `CONTRIBUTING.md` 与完整维护者规范
- **THEN** 不存在"一律必须走 OpenSpec"式的绝对表述，需要提案的改动范围被描述为"外部可观察行为、兼容性或数据格式"

#### Scenario: PR 模板允许标注提案不适用

- **WHEN** 查看 `.github/PULL_REQUEST_TEMPLATE.md` 中与 OpenSpec 提案/delta spec 相关的条目
- **THEN** 该条目存在"不适用"或等价的允许项，而不是只能勾选"已提交"

### Requirement: 完整维护者规范的单一存放与零丢失

原有完整贡献者规范 SHALL 逐段搬移到单一文件，内容不得丢失；精简入口 SHALL NOT 复制该内容而形成第二份。
搬移后的完整规范 MUST 与项目实际的 `dev → main` 双分支模型一致——SHALL NOT 保留"从 main 分支创建
功能分支"这类与双分支模型矛盾的表述。

#### Scenario: 原规范章节无丢失

- **WHEN** 逐一取出搬移前的完整规范中的各二级/三级章节标题，在搬移后的完整规范中查找
- **THEN** 每个章节标题都能在搬移后的文件中定位到对应段落

#### Scenario: 分支模型表述一致

- **WHEN** 在贡献者文档中查找关于创建功能分支的表述
- **THEN** 不出现"从 main 分支创建功能分支"式的表述，且明确 PR 目标为 `dev`

### Requirement: 重叠贡献者文档收敛

文档站内已有的贡献指南（`docs/contributing/contributing.md`）MUST NOT 继续复述分支规范、提交规范与
质量门禁而形成第二份权威描述，而 SHALL 指向完整维护者规范这一唯一权威。

#### Scenario: 站点指南改为指针

- **WHEN** 查看 `docs/contributing/contributing.md`
- **THEN** 该文件包含指向完整维护者规范的链接，且不再包含"从 main 分支创建功能分支"式表述

### Requirement: 可上手任务的入选标准

仓库 SHALL 提供一份可上手任务清单文档，逐条指向 GitHub 上的对应 issue。每条任务 MUST 给出：
涉及的具体文件路径、预期耗时量级、可判定的验收标准、以及对使用者可见的结果。清单 MUST 区分
"可立即开始"与"暂不可开始"两组；尚不可开始的任务 MUST 显式标注其阻塞来源，SHALL NOT 与可立即
开始的任务混列而不加区分。只有**可立即开始**的任务 SHALL 带 `good first issue` 标签；暂不可开始的
任务 SHALL NOT 带该标签（避免贡献者被引向一条走不通的路径）。

#### Scenario: 清单条目要素齐备

- **WHEN** 逐条检查可上手任务清单
- **THEN** 每条都含具体文件路径、耗时量级、"验收标准"与"使用者可见的结果"四项，并携带对应的 issue 编号

#### Scenario: 阻塞项显式标注且不带新手上手标签

- **WHEN** 检查清单中依赖其他工作才能开始的任务
- **THEN** 每条这类任务都标注了阻塞来源（相关 issue 或变更编号），清单中区分了可立即开始与暂不可开始，
  且只有可立即开始的任务带 `good first issue` 标签

### Requirement: 贡献者收益可见

仓库 SHALL 提供贡献者名单文件，说明收录方式并欢迎新贡献者加入。`README.md` 与 `README.zh.md` 的贡献段落
MUST 给出可预期的响应承诺，并以 `MAINTAINERS.md` 为承诺数字的唯一权威——两份 README SHALL NOT 引入与
`MAINTAINERS.md` 不一致的时间承诺。文档 SHALL NOT 声称任何未经核实的第三方使用者或贡献者。

#### Scenario: 贡献者名单存在且说明收录方式

- **WHEN** 查看仓库根的贡献者名单文件
- **THEN** 文件存在，含收录方式说明与欢迎新贡献者的表述，且不包含未经核实的第三方名单

#### Scenario: 响应承诺与权威源一致

- **WHEN** 在 `README.md` 与 `README.zh.md` 的贡献段落中查找响应时间承诺，并与 `MAINTAINERS.md` 比对
- **THEN** 两份 README 都指向 `MAINTAINERS.md` 作为权威，且不出现与 `MAINTAINERS.md` 不同的天数

### Requirement: 流程资产不移动

维护者规范 SHALL 说明仓库内 `.claude/` 与 `openspec/changes/archive/` 等目录属于**流程资产**而非产品代码，
并说明它们不被移动的原因。这些目录 MUST 保持在其既有位置。

#### Scenario: 流程资产位置不变

- **WHEN** 检查 `.claude/` 与 `openspec/changes/archive/` 目录
- **THEN** 两者仍位于仓库既有的约定路径下，且维护者规范中对这两个路径有性质说明

### Requirement: 门禁严格度不变

本变更 SHALL NOT 放宽或收紧任何 CI 门禁。文档中可以列出"建议放宽"的候选，但 MUST 明确标注为**建议、
尚未生效**，并 MUST NOT 声称其已生效。

#### Scenario: 建议被标注为尚未生效

- **WHEN** 在维护者规范中查找关于放宽门禁的内容
- **THEN** 相关内容被标注为建议且尚未生效，而不是已生效的规则
