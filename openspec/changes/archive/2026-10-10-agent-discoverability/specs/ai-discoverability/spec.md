## Purpose

定义本项目的"AI 检索发现层"契约：仓库根 MUST 提供 `llms.txt` 与 `AGENTS.md` 两个面向检索与
编码 agent 的入口，README MUST 提供自然语言问答；这三处对"支持 / 不支持"的表述 MUST 与
特性表一致，且 MUST NOT 出现任何未实现的能力。

## ADDED Requirements

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
- **THEN** 多进程、cron 表达式、健康监控指标链路三项均按"未实现/不支持"表述，且不存在任何
  特性表标为 ❌ 或 ⚠️ 的能力在 `llms.txt` 里被描述为可用

#### Scenario: 绝对链接实测可达

- **WHEN** 逐个请求 `llms.txt` 中列出的绝对 URL
- **THEN** 每个 URL 都返回成功状态（站点根 / API 参考 / benchmark 报告 / CHANGELOG 四类各自可定位）

### Requirement: 仓库根 MUST 提供 `AGENTS.md`

仓库 SHALL 在根目录提供 `AGENTS.md`，面向"**用本库写代码**"的通用编码 agent；它 MUST 与面向
"**在本仓库改代码**"的 `CLAUDE.md` 分工区分开。

该文件 MUST 至少包含：安装方式与版本门槛；Worker 必须以**类**注册；配置与实现分离的约定；
"失败要大声"的实例（至少三例）；验证改动的测试命令。

Worker 注册约束 MUST 写明被拒绝的输入类型及各自会看到的报错形态；MUST NOT 只写"必须是类"
而不给出可据以自我纠正的报错文本。

`AGENTS.md` SHALL NOT 声称任何未实现的能力，SHALL NOT 给出未经验证的性能数字或生产使用案例。

#### Scenario: 按说明即可完成接入

- **WHEN** 只读 `AGENTS.md` 并照其步骤执行
- **THEN** 能完成安装、写出一段可运行的 Worker、知道必须注册类而不是实例或函数、知道用哪条
  测试命令验证自己的改动

#### Scenario: 历史坑与真实报错一致

- **WHEN** 按文档描述把函数或实例传给 Worker 注册入口
- **THEN** 得到的是 `AGENTS.md` 中列出的同一形态报错（而非静默成功），文档所写报错与实际
  抛出的报错一致

#### Scenario: 与仓库内部指引不混淆

- **WHEN** 比对 `AGENTS.md` 与 `CLAUDE.md` 的受众与范围
- **THEN** 前者只讲"用本库写代码"，后者只讲"在本仓库改代码"，两者的安装/门槛/测试命令不冲突

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
- **THEN** 两者对多进程、cron、健康监控指标的结论一致，且 FAQ 不出现特性表之外的能力声明

#### Scenario: 与详版结论一致

- **WHEN** 把 README FAQ 的问题集合与 `docs/FAQ.md` 的问题集合比对
- **THEN** 每个问题在详版中都有对应条目，且两处对同一问题的支持/不支持结论不矛盾

### Requirement: 发现层的一致性 MUST 可机械校验

仓库 SHALL 提供自动化校验，把上述约束变成 CI 能拦住的断言。

校验 SHALL NOT 依赖网络：需要联网核对的链接可达性 MUST 以可复跑命令留档，而 SHALL NOT 写成
测试断言（三平台 CI 上的联网断言只会带来假红）。

#### Scenario: 违规可被拦住

- **WHEN** 把 `llms.txt` 里的多进程描述为可用，或从 README FAQ 删掉一个 issue 点名的问题，
  或把 Worker 注册说明里的报错改成与真实不符
- **THEN** 至少一条断言失败

#### Scenario: 断言自带牙齿

- **WHEN** 对每类断言注入一次违规实现
- **THEN** 对应断言变红；还原后文件与注入前逐字节一致
