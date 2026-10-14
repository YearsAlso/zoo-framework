## ADDED Requirements

### Requirement: 状态 effect 调度器 MUST 能把 effect 登记到索引且二者一致

`StateEffectScheduler` 向索引登记 / 移除状态 effect 时，被调用的索引方法 MUST 真实存在，MUST NOT
在运行期以 `AttributeError` 失败。登记后，索引 MUST 能按状态（分组）与全集两处查到该 effect；
移除后 MUST 在两处都不再包含它。移除 MUST 幂等：目标不存在时 MUST NOT 抛错。本补齐 MUST NOT 改变
调度器既有的查询（`get_state_effect`）与执行（`execute_state_effect`）语义。

#### Scenario: 登记 effect 后索引可查

- **WHEN** 经 `StateEffectScheduler.add_state_effect` 登记一个 effect
- **THEN** 索引的按状态分组与全集都能查到它，且调用不抛 `AttributeError`

#### Scenario: 移除 effect 后索引不再包含

- **WHEN** 登记一个 effect 后再经 `StateEffectScheduler.remove_state_effect` 移除它
- **THEN** 索引的按状态分组与全集都不再包含该 effect

#### Scenario: 查询与执行语义不变

- **WHEN** 登记一个 effect 后按状态查询并执行
- **THEN** 查询返回该 effect，执行调用到该 effect 的回调
