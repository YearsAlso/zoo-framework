# Delta Spec: event-dispatch-batching

## ADDED Requirements

### Requirement: 批量提交 (Batched Submission)

事件消费者 SHALL 把同一轮排空里同 (channel, reactor) 的待投递事件收集成批，SHALL 以一次提交（一次执行器簿记）投递整批；批内事件仍 MUST 逐个执行响应器（`execute(topic, content)` 语义不变）。批大小 SHALL 有上限（可配置，保守默认）以防大批独占执行器。

#### Scenario: 同目标事件成批投递

- **WHEN** 一轮排空里同一通道、同一响应器命中了多个事件
- **THEN** 这组事件以一次提交投递（执行器簿记次数等于批数而非事件数）
- **AND** 批内每个事件的响应器仍被逐个执行

#### Scenario: 批大小上限

- **WHEN** 同目标积压事件数超过批大小上限
- **THEN** 溢出事件留在队列中待下一轮消费（MUST NOT 因裁批而丢失或死信）

#### Scenario: 关闭或批大小为 1 时逐事件行为

- **WHEN** 批量投递关闭（或缺省批大小为 1）
- **THEN** 投递行为与本变更合入前完全一致（逐事件提交）

### Requirement: 批级可观测 (Batch-level Observability)

有界等待与超时/异常上报语义 SHALL 保留，观测键从事件级平移到批级：一批在等待超时后仍未完成的 MUST 可上报；批内已结束项抛出的异常 MUST NOT 被吞掉，上报 MUST 携带足以定位事件的信息（事件标识或批内索引）。

#### Scenario: 批内异常可定位

- **WHEN** 一批的执行中某个事件的处理抛出异常且该批已结束
- **THEN** 上报包含该异常与对应事件的可定位信息
- **AND** 其余事件的结果不受该异常掩盖

#### Scenario: 超时未完成可观测

- **WHEN** 等待超时后批内仍有未完成项
- **THEN** 未完成项数量被上报（事件级定位信息尽力提供）

### Requirement: 语义与顺序不变 (Semantics and Order Preserved)

批量投递 MUST NOT 改变：事件去向语义（投递/回队/死信恰好其一）、通道内处理顺序（仍按弹出顺序执行响应器）、重试语义、过期判定、优先级计算。执行器的实例级生命周期（对齐执行原语决策）保持不变。

#### Scenario: 去向与顺序语义不变

- **WHEN** 批量投递启用且一轮排空完成
- **THEN** 每个被取出事件的去向（投递/回队/死信恰好其一）与通道内处理顺序与关闭批量时一致
