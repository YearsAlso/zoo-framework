# Proposal: fix-persistence-failure-signal

## Why

issue #231：`stateMachine.picklePath` 的父目录不存在时，持久化每次落盘都失败，但
`PersistenceScheduler.save` 只记一条 ERROR 日志、把 `False` 返回给（多半忽略它的）调用方——
持续失败被静默吞掉，使用者无法感知状态从未落盘。这是"静默降级"家族里最难排查的一类：进程看着
一切正常，数据其实一直在丢，且脏标记永远为真、每次 tick 反复失败。

同一条失败链上，`PicklePersistenceStrategy.save` 更早一步把底层 `OSError`（父目录缺失即
`FileNotFoundError`）吞成一条日志 + `False`。

## What Changes

- 新增显式异常 `PersistenceError(RuntimeError)`：持久化无法完成时抛出，调用方**无法忽略**。
- 新增 `PersistenceScheduler.ensure_storage_ready()`：目标目录不存在 / 不可写时明确报错，
  错误信息给出目录、配置键 `stateMachine:picklePath` 的定位与下一步。
- `PersistenceScheduler.start()` 启动即校验目标目录（fail-fast），而非进入每拍静默失败。
- `PersistenceScheduler.save()` 失败时抛 `PersistenceError`（不再只是返回 `False` + 一条日志）；
  失败时脏标记保持为真，调用方可重试。
- `load()` 的优雅语义不变（文件缺失仍返回空值）；成功落盘仍返回成功信号。
- 导出面新增 `PersistenceError`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `state-machine`：新增「持久化失败 MUST 显式可感知」——落盘不可完成时 MUST 明确报错、MUST NOT
  只记日志；启动时 MUST 校验目标目录。

## Impact

- **代码**：`zoo_framework/core/persistence_scheduler.py`。
- **测试**：`tests/test_persistence_scheduler.py` 新增 `TestExplicitFailureNotification`（3 例）。
- **规格**：`openspec/changes/fix-persistence-failure-signal/specs/state-machine/spec.md`。
- **无新增依赖**。
- **相邻现象（不在本变更范围）**：`StateMachineWorker`（`zoo_framework/workers/`，由并行工作流
  负责）自身的落盘实现，以及本组件的后台自动保存线程 `_scheduler_loop` 的"记录后继续"策略——
  后者现由 `start()` 的前置校验兜底，运行中目录被删仍逐拍记录日志（见 design 的待裁决项）。
