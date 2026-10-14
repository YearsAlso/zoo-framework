## MODIFIED Requirements

### Requirement: 仓库根 MUST 提供 `llms.txt`

仓库 SHALL 在根目录提供 `llms.txt`，遵循 llms.txt 约定：H1 标题 + 引用式摘要 + 分节链接列表。

该文件 MUST 至少包含六类内容：这是什么 / 什么时候用它 / 什么时候**不要**用它 / 核心概念 /
最小可运行示例 / 到文档站与 API 参考与 benchmark 报告与 CHANGELOG 的绝对 URL。

"不要用"清单 MUST 明写三条替代方案：需要跨机器 → Celery；需要 cron 表达式 → APScheduler；
多进程 → 本框架未实现。

核心概念 MUST 用**功能名**表达（任务执行单元 / 生命周期入口 / 调度器 …），并 MUST 显式说明
隐喻只影响命名、不影响语义。

文件内列出的绝对 URL MUST 逐个实测可达；未返回成功状态的链接 MUST NOT 写入。

#### Scenario: 结构与约定齐备

- **WHEN** 读取仓库根 `llms.txt`
- **THEN** 首行是 H1、随后是引用式摘要、之后是分节链接列表，且上述六类内容都能在文件内定位到

#### Scenario: 未实现的能力不被写入

- **WHEN** 把 `llms.txt` 中的能力陈述与 README 特性表逐项比对
- **THEN** 多进程、cron 表达式两项按"未实现/不支持"表述
- **AND** 已接通的能力（如健康监控指标链路）按 README 特性表同一口径如实表述，且不存在任何
  特性表标为 ❌ 的能力在 `llms.txt` 里被描述为可用

#### Scenario: 绝对链接实测可达

- **WHEN** 逐个请求 `llms.txt` 中列出的绝对 URL
- **THEN** 每个 URL 都返回成功状态（站点根 / API 参考 / benchmark 报告 / CHANGELOG 四类各自可定位）

### Requirement: README MUST 提供自然语言问答且三处口径一致

`README.md` 与 `README.zh.md` SHALL **各自**提供 FAQ 小节；小节标题 MUST 是自然语言问句，
每组答案 SHALL 为 1–3 行短答。两份 FAQ 覆盖的问题集合 SHALL 一致。

FAQ MUST 至少覆盖：不装 broker 能否跑后台定时任务；与 Celery 的区别与选型；与 APScheduler 的
区别；多进程与跨机器；cron 表达式；任务卡住是否会被强杀；重启后状态是否恢复；隐喻名与功能名
的对应；与 AI Agent 的关系；生产环境使用情况。

FAQ 中所有"不支持/未实现"的表述 MUST 与 README 特性表一致；SHALL NOT 出现特性表未声明的能力。

FAQ 的短答 MUST 与 `docs/FAQ.md` 的详版结论一致：同一问题在两处 MUST NOT 给出相反结论。
`docs/FAQ.md` SHALL 保持详版真源定位。

生产使用情况 MUST 按 `ADOPTERS.md` 如实表述；SHALL NOT 声称未经证实的使用者。

#### Scenario: 问句覆盖清单

- **WHEN** 检查两份 README 的 FAQ 小节
- **THEN** 问题数量不少于 10 组，且上述每个主题都能匹配到至少一问

#### Scenario: 不支持口径与特性表一致

- **WHEN** 抽出 FAQ 中所有"不支持/未实现"陈述并与特性表逐项比对
- **THEN** 两者对多进程、cron 表达式的结论一致，且 FAQ 不出现特性表之外的能力声明

#### Scenario: 与详版结论一致

- **WHEN** 把 README FAQ 的问题集合与 `docs/FAQ.md` 的问题集合比对
- **THEN** 每个问题在详版中都有对应条目，且两处对同一问题的支持/不支持结论不矛盾
