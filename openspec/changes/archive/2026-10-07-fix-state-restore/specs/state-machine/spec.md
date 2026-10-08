## Purpose（本变更新增条款）

状态机持久化的恢复侧契约：读回必须真正生效，"已加载"必须诚实。

## ADDED Requirements

### Requirement: 状态机持久化恢复 MUST 真正生效

`StateMachineManager.load_state_machines` MUST 能恢复框架自身落盘的形态（`get_state_machines()` 返回并经 pickle 写出的 `ThreadSafeDict`）——读回后按作用域查询 MUST 取回落盘时的状态值。为兼容旧文件与手工注入，普通 `dict` 入参 MUST 被接受并包装为 `ThreadSafeDict`；无法识别的入参 MUST 明确失败（`TypeError`）而非静默空操作。`have_loaded()` MUST 只在恢复流程真正完成后为真——MUST NOT 出现"声称已加载但状态从未恢复"的形态，该假象会同时误导日志与短路后续重试。恢复语义为**整表替换**：进程首次解析后从盘载入时当前实例必为空表（替换与合并等价）；在非空状态上显式重载是使用者的有意动作。

#### Scenario: 自家落盘形态读回即恢复
- **WHEN** 状态经落盘（deepcopy + pickle）后在新进程语境读回并调用 `load_state_machines`
- **THEN** 按作用域与键查询取回落盘时的值；`have_loaded()` 为真

#### Scenario: 备份恢复路径同样真正生效
- **WHEN** 主文件损坏，管理器经备份文件恢复
- **THEN** 备份中的状态被真实恢复，而非仅置"已加载"标志

#### Scenario: 无法识别的入参明确失败
- **WHEN** 以既非 None、也非 dict/ThreadSafeDict 的对象调用 `load_state_machines`
- **THEN** 抛出 `TypeError` 且"已加载"标志保持为假，由调用方的异常路径决定后续行为
