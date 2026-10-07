## Purpose（本变更新增条款）

循环 Worker 的运行节拍契约：可配置、默认兼容、声明必有消费。

## ADDED Requirements

### Requirement: 循环 Worker 的运行节拍 MUST 可配置

声明循环的框架内置 Worker（事件管道、状态机持久化）的 `delay_time` MUST 经配置入口取值，MUST NOT 硬编码在构造路径；缺省值 MUST 保持历史行为（向后兼容）。配置表 MUST NOT 保留零消费的死键——声明了的配置键 MUST 有真实消费点，否则"看起来可调而实际不可调"的误导 MUST 以删除键的方式终结，而非放任。

#### Scenario: 配置入口调节事件节拍
- **WHEN** 用户配置 `event:delay` 后构造 `EventWorker`
- **THEN** 该 Worker 的 `delay_time` 取配置值；未配置时保持历史默认 5

#### Scenario: 死键不存在
- **WHEN** 检查事件参数类的声明键集合
- **THEN** 不存在无消费点的键（如历史的 `event:sleep`）
