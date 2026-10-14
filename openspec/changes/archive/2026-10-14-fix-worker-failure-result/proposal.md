# 提案：fix-worker-failure-result —— 执行失败 MUST 也产生一条可区分的结果事件

## Why

issue #228 实锤：`BaseWorker.run()` 在 `_execute` 抛异常时把异常向上抛（docstring 写的是
"让调度器观察失败"），而观察方 `WorkerDispatchCore.settle` 在 `error is not None` 时只
`LogUtils.error(...)` 然后**直接 return**——结果主题上什么都不投递。

于是所有"靠结果主题判断任务是否跑完"的消费者（框架自带的 `WaiterResultReactor`、调用方
自己的中继反应器）会把**已经失败**的 Worker 当成**仍在执行**：它已不在调度表里，却永远
等不到结果；调用方只能靠墙钟超时兜底，而超时报出来的是"超时"，不是"这个 Worker 崩了"
——真正的失败原因只留在日志里。在 zoo-code-agent 的批量任务派发场景里，一条任务抛错就
再也不会回结果，整批只能等墙钟超时。

## What Changes

- `BaseWorker.run()`：失败不再把异常留给上层，而是返回一条**可区分的结果**——
  `content=None`、`error` 携带 `类型名: 消息`、`success` 为假，投递到同一统一结果主题；
  `_on_error` / `_on_done` 与错误日志语义保持不变，`_destroy_result` 不在失败路径调用
  （失败没有可销毁的产出）。
- `WorkerResult`：新增 `error` 字段与 `success` 只读属性，作为**唯一的失败判别口径**；
  文档写明"失败 MUST NOT 以成功空结果的形态投递"。
- **不新增失败专用主题**：结果主题承载的是"这条任务结束了"这一信号，成功与失败都应出现
  在同一主题上、由 `error` 区分；把失败换到另一个主题，会让"等完成"的消费者继续饿死
  （这正是本 issue 的症状）。
- 同步改判把旧行为写死为断言的两条既有用例，并新增回归用例
  `tests/test_worker_error_result.py`。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-scheduling`：新增 Requirement「Worker 执行失败 MUST 产生可区分的结果事件」，
  覆盖失败结果投递、失败标记、不得冒充成功空结果、失败后不残留执行状态四项。

## Impact

- **代码**：`zoo_framework/workers/base_worker.py`（`run()` 失败分支、
  `registry_name` 拆分）、`zoo_framework/workers/worker_result.py`（`error` / `success`
  / `registry_name`）。
- **测试**：新增 `tests/test_worker_error_result.py`（8 条）；改判
  `tests/test_worker_scheduling.py::TestResultReporting::test_failed_worker_reports_a_distinguishable_result`
  与 `tests/test_native_task_execution.py::TestNativeTaskWorker::test_error_mapped_through_settle_not_success_empty_result`。
- **契约变更（向后兼容性）**：`run()` 不再向上抛执行体异常，改为返回失败结果。框架内
  `worker.run()` 的唯一调用点是结算收口（`WorkerDispatchCore.run_worker`），下游
  "捕获 `run()` 异常"的写法需改为检查 `WorkerResult.error` / `success`。
- **不在范围**：`WorkerDispatchCore.settle`（归并行 worker）。本变更**不需要**改它——
  让 `run()` 产出失败结果后，失败自然走既有的单一结算收口（登记项清理 + 运行标识盖章 +
  结果投递）。
