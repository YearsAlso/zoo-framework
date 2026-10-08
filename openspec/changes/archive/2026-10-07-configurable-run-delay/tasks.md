## 1. 参数化（#73）

- [x] 1.1 `EventParams.EVENT_DELAY_TIME`（`event:delay`，默认 5）；`StateMachineParams.STATE_MACHINE_DELAY_TIME`（`stateMachine:delay`，默认 5）
- [x] 1.2 `EventWorker` / `StateMachineWorker` props 组装取参数，惰性导入前置到 `BaseWorker.__init__` 之前（#51 顺序约束：两类由 WorkerRegistry 运行期构造）
- [x] 1.3 死键 `EVENT_SLEEP_TIME` / `event:sleep` 删除（全库零引用核实：含模板与示例配置）

## 2. 语义歧义终结（#74，裁定：修注释、不内置幂等）

- [x] 2.1 `dispatch_core.retain_looping` docstring："恰好执行一次"限定为调度簿记语义；如实标注投递层面至少一次 + EventReactor 失败重放；需恰好一次的消费者自带幂等

## 3. 验证

- [x] 3.1 `tests/test_delay_params.py` 4 条：默认值兼容、两 worker 配置生效、死键不存在；全量 709 绿、mypy 0 error、ruff/bandit 绿
- [x] 3.2 已完成（#73 关闭 completed、#74 结案 not planned，留言均已发；#32 同步随归档 PR chore/archive-round3）：PR 合并后：#73、#74 关闭留言；#32 在办表同步
