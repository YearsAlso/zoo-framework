## Why

issue #73（真实消费者 zoo-code-agent 实测发现）：`EventWorker.__init__` 把 `delay_time` 钉死为 5——排空一次通道后要睡满 5 秒才结算，期间一直算在飞不会被再次派发，**每一次事件派发都要等下一个节拍且无法调节**；时间敏感场景（agent 工具循环、事件驱动短任务）的单步延迟被钉死在秒级。同族问题：`StateMachineWorker` 同款硬编码（落盘周期，issue 认可其为通用小改动，经维护者裁定一并参数化）。另有死键 `event:sleep`（`EVENT_SLEEP_TIME`，默认 0.2）：gevent 消费循环删除后**全库零消费**，用户合法填写不会有任何效果——配置表"看起来可调"而实际不可调。

顺带结案 #74：`dispatch_core.retain_looping` 的"恰好执行一次"注释与 `EventReactor` 的失败重放（至少一次）并存造成语义歧义——按维护者裁定**修注释、不内置幂等**：措辞改为如实的"调度簿记语义"，投递层面标注至少一次、需恰好一次的消费者自带幂等（zoo-code-agent 的 `IdempotencyLedger` 正因此在调用方）。

## What Changes

- `EventParams` 新增 `event:delay`（默认 5）；`StateMachineParams` 新增 `stateMachine:delay`（默认 5）——**行为向后兼容**
- `EventWorker` / `StateMachineWorker` 的 props 组装取各自参数（惰性导入前置于 `BaseWorker.__init__`，#51 的顺序约束成立：两类均由 `WorkerRegistry` 运行期构造）
- `EVENT_SLEEP_TIME` / `event:sleep` 死键删除（全库零引用，已核实含模板与示例配置）
- `retain_looping` docstring 改写（#74）："恰好执行一次"限定为调度簿记语义，投递层面如实标注至少一次 + EventReactor 重试重放

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `event-dispatch`：新增「循环 Worker 的运行节拍 MUST 可配置」——事件管道与持久化周期经配置入口调节、默认值保持历史行为；声明了的配置键 MUST 有真实消费点，MUST NOT 存在"填写无效果"的死键

## Impact

- **代码**：`params/event_params.py`、`params/state_machine_params.py`、`workers/event_worker.py`、`workers/state_machine_work.py`、`core/waiter/dispatch_core.py`（仅 docstring）
- **配置**：新增 `event:delay` / `stateMachine:delay`；移除 `event:sleep`（无消费点，删除不改变任何行为）
- **测试**：`tests/test_delay_params.py` 4 条（默认值兼容、两 worker 配置生效、死键不再存在）；全量 709 绿
- **issue**：#73 关闭、#74 结案（留档转注释）
