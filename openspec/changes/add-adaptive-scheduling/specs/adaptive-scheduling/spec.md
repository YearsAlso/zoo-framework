# Delta Spec: adaptive-scheduling

> **⚠️ 状态：已延后（维护者 2026-10-09 决定）**——本 delta 未实施、不合并；
> 属冻结的规划资产，重启条件见 proposal.md 文首状态块。

## ADDED Requirements

### Requirement: 特征日志采集 (Feature Log Collection)

框架 SHALL 在任务结算后采集该次执行的特征记录：任务标识、特征向量（执行时长、错误结果、输入尺寸、派发瞬间的队列深度统计量）、实际选择的执行路径。特征记录 SHALL 异步批量追加到 JSONL 日志文件（独立于既有日志），单次采集操作 MUST 为 O(1) 且 MUST NOT 阻塞结算路径。日志写入失败 MUST NOT 影响任务执行与投递。

#### Scenario: 任务完成后落一条特征记录

- **WHEN** adaptive 启用且一个任务在结算点完成（成功或失败）
- **THEN** 恰好一条特征记录被加入待写缓冲
- **AND** 记录包含任务标识、特征值、执行路径与结果状态

#### Scenario: 日志失败不伤任务

- **WHEN** 特征日志文件不可写（磁盘满/权限）
- **THEN** 采集被跳过，任务执行与投递结果不受影响

#### Scenario: 记录格式自描述

- **WHEN** 特征日志被训练项目读取
- **THEN** 每条记录自带特征 schema 版本字段，训练项目可按版本识别字段含义

### Requirement: 模型权重加载与校验 (Model Weight Loading)

框架 SHALL 在启用推理前加载训练产生的模型权重文件，并校验其自描述头：模型格式版本、特征 schema 版本、校验和。校验失败（文件缺失、损坏、版本不匹配）SHALL 显式拒绝该权重（可记录日志）并退回静态默认路径，MUST NOT 静默使用不兼容权重。权重文件 MUST 支持运行期重载（新训练产出后无需重启框架）。

#### Scenario: 兼容权重被加载

- **WHEN** 权重文件存在且格式版本与特征 schema 版本均匹配
- **THEN** 权重被加载，后续派发决策使用该模型

#### Scenario: 不兼容权重显式拒绝

- **WHEN** 权重文件缺失、校验和不符或版本不匹配
- **THEN** 该权重不被使用，框架记录拒绝原因并退回静态默认路径
- **AND** 不出现「部分采用不兼容权重」的状态

#### Scenario: 运行期重载

- **WHEN** 新权重文件落盘且重载被触发（手动或周期检查）
- **THEN** 后续决策使用新权重，重载失败（如新文件损坏）时保持旧权重或退回静态默认，不中断派发

### Requirement: 在线推理决策 (Online Inference Decision)

框架 SHALL 在任务派发前使用已加载权重推理该任务类的执行路径选择（native 或普通）。推理 MUST 为纯 stdlib 实现（线性 softmax：特征向量与权重一次点积），单次开销 MUST NOT 超过 10 µs（本机参考形态）。特征向量维度 SHALL 与权重文件的特征 schema 版本一致。native 臂 SHALL 仅在原生执行已启用时可选，否则二元决策退化。

#### Scenario: 模型指向 native 时派往 native

- **WHEN** 某任务类的特征经推理得到 native 路径更优，且原生执行已启用
- **THEN** 该任务类被派往 native 路径

#### Scenario: 原生执行未启用时 native 臂退化

- **WHEN** 推理给出 native 选择但原生执行未启用
- **THEN** 该任务类按普通路径派发（不报错、不等待）

#### Scenario: 无模型时冷启动退化

- **WHEN** adaptive 启用但尚无兼容权重文件
- **THEN** 所有任务类按静态默认路径派发，与关闭状态行为一致

### Requirement: 异常退路 (Failure Fallback)

自适应决策层 SHALL fail-open：特征提取、日志采集、权重加载、推理中任何环节的错误 MUST NOT 传导为任务失败；发生时 MUST 回退静态默认路径继续派发。决策层 MUST NOT 静默吞掉任务本身的成功/失败结果。

#### Scenario: 决策器异常不影响任务

- **WHEN** 决策器在派发前抛出异常
- **THEN** 任务仍按静态默认路径派发并正常完成
- **AND** 任务结果（成功/失败/错误族）不受决策器异常影响

### Requirement: 关闭时零影响 (Disabled Zero Impact)

当 `adaptive:enabled` 为假（含缺省）时，框架 MUST 与本变更合入前的行为完全一致：不提取特征、不写日志、不加载权重、不推理、不产生额外锁竞争。配置解析 SHALL 遵守既有 `ParamsPath` 三段语义（首路径 → aliases → default，falsy 值被尊重）。

#### Scenario: 关闭时调度路径与合入前一致

- **WHEN** `adaptive:enabled=false`（或缺省）且框架按 `adaptive-scheduling` 合入后运行
- **THEN** worker 派发、结算、投递行为与合入前逐字节等价（不进入任何 adaptive 代码分支）
- **AND** 无新锁被获取

### Requirement: 配置键族 (Configuration Keys)

框架 SHALL 提供 `adaptive:*` 配置键族，经 lazy import 在 `ParamsFactory` 读取 config.json 之后解析（纪律同 `native:*`）。至少包含：`adaptive:enabled`（总开关，默认 false）、特征日志文件路径、模型权重文件路径、日志缓冲阈值。所有键 MUST 有保守默认值。

#### Scenario: 键族可配置且默认保守

- **WHEN** config.json 不含任何 `adaptive:*` 键
- **THEN** 框架以 adaptive:enabled=false 等默认值运行，行为与静态调度一致
