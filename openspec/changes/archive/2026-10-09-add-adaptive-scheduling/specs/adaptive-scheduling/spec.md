# Delta Spec: adaptive-scheduling

> **状态：已重开——bandit 方案（维护者 2026-10-09 指示「用 bandit 替代 ML，ML 不再推进」）。**
> 原本 RECORD ML / 特征日志 / 权重档案的 REQUIREMENTS 已整体替换为本文件内容；ML 版标题历史见 git。

## ADDED Requirements

### Requirement: DualArmWorker MUST 在自身生命周期内闭环路由决策

系统 SHALL 提供 `DualArmWorker` 基类：子类声明 python 执行体与原生任务名两条语义等价的臂。基类在每次执行前按逐类统计决策走哪条臂，执行后以**实测时长**为奖励增量更新对应臂的统计。决策与更新 MUST 全部发生在 Worker 自身生命周期内（构造/执行/hooks），MUST NOT 修改 `WorkerDispatchCore` / 调度模型 / waiter 的语义与热路径；结果 MUST 照既有 `WorkerResult` → 单一结算收口投递，MUST NOT 新增投递点。

#### Scenario: 双臂切换决策在 worker 内完成

- **WHEN** 一个 `DualArmWorker` 子类被派发执行
- **THEN** 决策（哪条臂）在 `_execute()` 入口完成，调度内核与调度器完全无感知
- **AND** 结果经既有 `BaseWorker.run()` → `WorkerResult` → `settle` 投递，恰好一次

#### Scenario: 奖励来自实测时长

- **WHEN** 某次执行完成（无论走哪条臂）
- **THEN** 该臂的统计按本次实测执行时长增量更新（均值），不存储单次样本

### Requirement: 探索策略 SHALL 为 ε-greedy 且决策 O(1)

决策 SHALL 按 ε-greedy：以 1−ε 概率选当前均值更优的臂，以 ε 概率随机探索（`adaptive:exploration` 可配，默认 0.05）。单次决策 MUST 为 O(1) 字典查询 + 常数次浮点比较，MUST NOT 引入特征向量、权重文件或训练依赖。探索参数 MUST 有保守默认值。

#### Scenario: 均值更优的臂被多数选择

- **WHEN** 某任务类的历史统计显示原生臂平均更快，且 ε=0
- **THEN** 该类的后续决策稳定选原生臂

#### Scenario: 探索概率按配置生效

- **WHEN** ε=0.05 且进行大量决策
- **THEN** 约 5% 的决策随机探索非优势臂（统计断言，固定随机种子）

### Requirement: 原生臂不可用时 MUST 显式拒绝而非静默回退

子类声明了原生臂但 `native:enabled` 为假、或原生扩展缺失/握手失败时，系统 MUST NOT 静默回退到 python 臂执行（否则配置错误被伪装成自适应决策），MUST 显式报错拒绝（复用 `native-task-execution` 的明确拒绝语义与错误族）。

#### Scenario: native 未启用时显式拒绝

- **WHEN** `DualArmWorker` 子类声明了原生任务，但配置 `native:enabled=false`
- **THEN** 构造或首轮执行时收到显式错误，错误指明原生执行未启用，不产生任何一次静默的 python 臂执行

#### Scenario: 扩展缺失时显式拒绝

- **WHEN** 原生扩展未安装但子类声明了原生臂
- **THEN** 错误指明缺失的是扩展（复用 adapter 的拒绝信息），不静默回退

### Requirement: 异常退路 (Failure Fallback)

自适应决策层 SHALL fail-open：决策、统计更新、（若启用）统计持久化中任何环节的错误 MUST NOT 传导为任务失败。双臂执行体自身的异常照既有 `BaseWorker` 契约（`_on_error` hook → 向上传播 → 结算收口 error 分支），MUST NOT 被决策层吞掉或改写。

#### Scenario: 决策器异常不影响任务

- **WHEN** 决策层在执行前抛出异常
- **THEN** 任务按 python 臂（静态默认）执行并正常完成，结果/错误族不受决策层异常影响

#### Scenario: 双臂执行体异常照既有契约

- **WHEN** 某条臂的执行体抛出异常
- **THEN** 异常经 `_on_error` 原样向上传播，结算收口按 error 分支处理，与普通 Worker 无差异

### Requirement: 关闭时零影响 (Disabled Zero Impact)

当 `adaptive:enabled` 为假（含缺省）时，框架 MUST 与本变更合入前的行为完全一致：不决策、不取锁、不更新统计、不写任何文件；继承 `DualArmWorker` 的子类也 MUST 按纯 python 臂执行（native 臂声明在关闭时即按上一条的显式拒绝处理）。配置解析 SHALL 遵守既有 `ParamsPath` 三段语义（falsy 值被尊重）。

#### Scenario: 关闭时调度路径与合入前一致

- **WHEN** `adaptive:enabled=false`（或缺省）且存在继承 `DualArmWorker` 的 worker
- **THEN** 该 worker 按 python 臂执行，不进入任何 bandit 代码分支、不获取锁
- **AND** 派发/结算/投递与合入前行为一致

### Requirement: 配置键族 (Configuration Keys)

框架 SHALL 提供 `adaptive:*` 配置键族，经 lazy import 在 `ParamsFactory` 读取 config.json 之后解析（纪律同 `native:*`）：`adaptive:enabled`（总开关，默认 false）、`adaptive:exploration`（探索率，默认 0.05）、`adaptive:statsPath`（统计持久化路径，**默认空 = 不持久化**）。所有键 MUST 有保守默认值；MUST NOT 声明无消费者的死键。

#### Scenario: 键族可配置且默认保守

- **WHEN** config.json 不含任何 `adaptive:*` 键
- **THEN** 框架以 adaptive:enabled=false 等默认值运行，行为与静态调度一致

#### Scenario: 统计持久化默认关闭

- **WHEN** `adaptive:statsPath` 未配置（默认空）且 adaptive 已启用
- **THEN** 统计仅存于进程内存，不产生任何文件写入
