## Why

issue #72（真实消费者 zoo-code-agent 实测发现，dev 主干复核成立）：状态机**读盘是空操作**——`StateMachineWorker` 落盘的是 `get_state_machines()` 返回的 `ThreadSafeDict`，而它**不是** `dict` 的子类，`load_state_machines` 的守卫 `isinstance(state_machine, dict)` 对框架自己写出的文件恒假：赋值从不执行、`_local_store_loaded` 却被置真、成功日志照打。**任何依赖状态机持久化恢复的用法（写盘成功、读回为空）都会中招**，且"已加载"假象挡死重试；备份恢复路径同一条链，同样空操作。establish-type-gate 时已把该缺陷登记为【已知缺陷】"不猜修"——如今有了真实消费者，语义必须裁定。

## What Changes

- `StateMachineManager.load_state_machines` 守卫按真实类型分派：`ThreadSafeDict` 原样恢复；普通 `dict` 包成 `ThreadSafeDict`（旧文件/手工注入兼容）；其它非 None 入参 `TypeError` 明确拒绝（静默忽略是旧缺陷的同族形态，worker 侧既有异常路径会退回全新状态并留下错误日志）
- **恢复语义裁定为整表替换**并写入 docstring 与 spec：现行唯一消费路径是进程首次解析后从盘载入（当前实例必为空表），替换与合并等价；在非空状态上显式重载是使用者的有意动作
- 回归测试 `tests/test_state_restore.py` 6 条：issue 最小复现、dict 兼容、未知类型拒绝、None 语义、worker 真实读盘路径（tmp 文件 + pickle）、备份恢复路径——缺陷正因这条路径**零覆盖**而长期存活

无公共 API 变化；写盘路径本就正常（原子写 + 校验 + 滚动备份），未动。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `state-machine`：新增「状态机持久化恢复 MUST 真正生效」——读回框架自落盘形态必须恢复状态；`have_loaded()` MUST 只在恢复流程真正完成后为真；无法识别的入参 MUST 明确失败而非静默空操作

## Impact

- **代码**：`zoo_framework/statemachine/state_machine_manager.py`（仅 `load_state_machines`）
- **测试**：`tests/test_state_restore.py` 新增 6 条（全量 711 绿）
- **消费者**：zoo-code-agent 的"重启续跑"解除阻塞（其 issue 记录：相关 openspec 变更为此收窄并保留回链）
- **issue**：#72 关闭
