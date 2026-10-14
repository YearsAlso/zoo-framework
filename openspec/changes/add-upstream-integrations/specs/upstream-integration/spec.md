# upstream-integration 规格变更（add-upstream-integrations delta）

## Purpose

定义本框架与外部上游项目「真实集成」的交付契约：集成示例 MUST 落在唯一的示例根目录、 MUST 可运行并附执行证据、MUST 随附一段可直接投进上游文档的说明文字与一份「何时不该用本框架」的诚实口径；集成本身 MUST NOT 修改框架代码，且争取生态的方式 SHALL 是「被上游文档提及」而非「被上游依赖」。

## ADDED Requirements

### Requirement: 集成示例 MUST 落在唯一的示例根目录 `example/integrations/<upstream>/` 下

仓库 SHALL 只有一个示例根目录，即单数 `example/`；集成示例 MUST 位于 `example/integrations/<upstream>/`，其中 `<upstream>` 为 kebab-case 的上游名。仓库 MUST NOT 同时存在 `example/` 与 `examples/` 两个平行示例根目录。每个集成目录 MUST 含：一个带文件头运行说明的可运行入口，以及一份说明「演示什么 / 怎么跑 / 期望输出」的 README。

#### Scenario: 示例根目录唯一

- **WHEN** 列出仓库顶层的示例目录
- **THEN** 只存在 `example/` 一个示例根目录，且每个上游集成各自位于 `example/integrations/<upstream>/` 下

#### Scenario: 集成目录自述齐备

- **WHEN** 读取任一 `integrations/<upstream>/` 目录
- **THEN** 目录内存在可运行入口与 README，README 覆盖「演示什么 / 怎么跑 / 期望输出」三项

### Requirement: 每个集成示例 MUST 可运行并附执行证据

示例 MUST 能按文件头注释给出的命令在受支持平台上启动并产生可观察输出；随变更提交的 PR MUST 附该输出的执行证据。示例所需的第三方依赖 MUST 在文件头注释中列明，MUST NOT 写入 `pyproject.toml` 的主包依赖；缺少依赖时 MUST 给出显式的安装指引，MUST NOT 静默失败。

#### Scenario: 按文件头命令可跑通

- **WHEN** 按示例文件头的命令安装依赖并启动该示例
- **THEN** 示例启动并产生与其 README「期望输出」一致的输出，失败时以显式错误结束

#### Scenario: 第三方依赖不进主包安装面

- **WHEN** 检查 `pyproject.toml` 的依赖声明
- **THEN** 其中不含任何示例引入的上游依赖，这些依赖只出现在示例文件头注释里

### Requirement: 每个集成 MUST 附一段可直接投给上游的说明文字

每个集成 MUST 提供一段 3–5 行、可原样投进上游文档的说明文字（随示例目录一并交付）。该文字 MUST 同时说明「何时该用本框架替代上游内建方案」与「何时不该」。该文字 MUST NOT 出现框架未实现的能力（跨机器分布式调度、多进程执行、cron 表达式、健康监控指标链路），且与 README 特性表 / `llms.txt` 的表述 MUST 一致。

#### Scenario: 说明文字含正反两面

- **WHEN** 阅读某个集成的说明文字
- **THEN** 其中既有「何时用本框架替代上游内建方案」的正面描述，也有「何时不该用」的反面描述

#### Scenario: 未实现的能力不被写入

- **WHEN** 把说明文字的能力陈述与 README 特性表逐项比对
- **THEN** 多进程、cron 表达式、跨机器、健康指标链路均未被描述为可用

### Requirement: 每个集成 MUST 附「何时不该用本框架」

每个集成目录的 README MUST 含一节「何时不该用本框架」，沿用项目既有的诚实口径（范围声明而非打分表），并 MUST 至少指向更合适的替代方案：需要跨机器 → Celery；需要 cron 表达式 → APScheduler；需要多进程 → 本框架未实现。

#### Scenario: 诚实口径齐备

- **WHEN** 读取某个集成目录的 README
- **THEN** 存在「何时不该用本框架」一节，且给出至少三条指向替代方案的边界说明

### Requirement: 集成 MUST NOT 修改框架代码

本能力的集成变更 MUST NOT 修改 `zoo_framework/` 与 `tests/`。若集成确需适配层，该适配层 MUST 位于示例目录内，且其存在的理由 MUST 在该示例 README 或文件头注释中说明。集成 MUST NOT 引入新的第三方依赖到主包。

#### Scenario: 框架代码零改动

- **WHEN** 审阅本能力集成变更的 diff
- **THEN** `zoo_framework/` 与 `tests/` 下无任何改动

#### Scenario: 适配层留在示例内且说明理由

- **WHEN** 某个集成包含示例内的适配层代码
- **THEN** 该适配层不被框架导入，且其存在理由在示例 README 或文件头注释中写明

### Requirement: 集成示例 MUST 声明跨平台行为

每个示例 MUST 在 Windows、Linux、macOS 上可运行，或在其 README 中写明平台限制。示例 MUST NOT 依赖仅 POSIX 可用的 API（如 `os.fork`、POSIX-only 信号）而不加标注；未标注的平台限制视为规格违背。

#### Scenario: 平台差异被标注或消除

- **WHEN** 在 Windows、Linux、macOS 上按 README 启动某个示例
- **THEN** 三平台都产生一致的期望输出，或 README 明写该平台已知限制

### Requirement: 上游文档贡献 MUST 以「被文档提及」为目标

本能力涉及的对外贡献 SHALL 以上游文档（或其官方示例仓）在「背景任务 / 集成 / 相关项目」一节提及本框架为目标；MUST NOT 要求上游把本框架写入其 `dependencies`。说明文字的措辞 MUST 由维护者在提交前确认。

#### Scenario: 对外贡献形态正确

- **WHEN** 审阅本能力产出的上游 PR 或说明文字草稿
- **THEN** 其形态为「让上游文档提及本框架」，不包含「要求上游声明依赖本框架」的诉求
