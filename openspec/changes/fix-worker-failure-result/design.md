# Design: fix-worker-failure-result

## Context

见 proposal.md。现状链路：`BaseWorker.run()` → 成功返回 `WorkerResult`；失败则
`_on_error()` + 错误日志 + `raise`。上层 `WorkerDispatchCore.run_and_settle` 捕获异常后
调 `settle(worker, error=e)`，而 `settle` 在 `error is not None` 时只写日志就 return。
全仓库 `worker.run()` 的唯一调用点即该收口；结果的唯一投递点也是 `settle`
（`EventReactorManager().dispatch(result.topic, result)`）。

## Goals / Non-Goals

**Goals**
- 失败在统一结果主题上留下**恰好一条**可区分的结果，消费者能把"失败"与"还在跑"分开
- 失败 MUST NOT 以成功空结果的形态出现
- 失败路径的生命周期语义（`_on_error` / `_on_done` / 错误日志）零变化
- 不触碰其它 worker 所有的三个文件

**Non-Goals**
- 不改 `WorkerDispatchCore.settle` 的 `error` 分支（保留为防御性路径）
- 不做失败重试 / 死信 / 失败专用主题（重试是 `EventReactor` 的职责，与 Worker 失败无关）
- 不把异常对象本身广播出去（只带可读的 `类型名: 消息`）

## Decisions

### D1: 失败结果由 `run()` 返回，而非继续向上抛

结果的**唯一投递点**是结算收口 `settle`，而它只在拿到 `result`（非 `error`）时投递。
`settle` 属并行 worker 的所有权范围，本变更不得修改。因此把失败做成"`run()` 返回一条
失败结果"是唯一能让失败走既有单一收口、且不越界的形态——异常仍被 `run()` 捕获、仍被
记录、仍触发 `_on_error`，只是不再交给调用方去"决定报不报"（`settle` 此前的决定就是
不报，这正是缺陷）。
**代价**：`run()` 的契约从"异常向上抛"改为"返回带 `error` 的结果"，属**显式契约变更**，
已写入 docstring 与本变更 proposal 的 Impact。`settle` 的 `error` 分支保留不变，仍是
`run_worker` 抛异常时的防御路径（例如子类自行覆写 `run()`）。

### D2: 同一结果主题 + `error` 字段，不新开失败主题

issue 的期望行为同时接受"带 error 字段的 WorkerResult"与"明确的失败主题"。选前者：
消费者的诉求是**知道这次执行结束了**，若失败改投另一主题，守在结果主题上的消费者仍然
饿死（症状原地不动）。因此失败与成功同主题，靠 `error` 区分；`success` 属性作为唯一
判别口径，避免调用方误用 `content` 判空。

### D3: `error` 为 `类型名: 消息` 的字符串

`f"{type(error).__name__}: {error}"`：保留异常类型（消费者能区分
`TimeoutError` / `ValueError`），又不广播异常对象本身（不含 traceback、不会被误 re-raise）。
`content` 在失败时为 `None`——执行体没有产出可投递的值，MUST NOT 用 `{}` 冒充产出。

### D4: 失败路径不调用 `_destroy_result`、不做 `delay_time` 等待

`_destroy_result` 的语义是"销毁执行产出"，失败没有产出，调用它等于编造产出；
`delay_time` 等待在失败时同样跳过——与修复前"异常跳过等待"的实际行为一致，
不改变循环 Worker 的调度节拍（循环 Worker 每轮由调度器重新派发）。

## Risks / Trade-offs

- [`run()` 不再抛异常] → 下游若有"捕获 `run()` 异常"的写法会失效。缓解：docstring 写明
  新契约，proposal 标注为 BREAKING 级别的契约变更；框架内唯一调用点已同构（`settle`
  拿到失败结果照样清登记、盖章、投递）。
- [失败结果被误读为业务产出] → `content=None` + `error` 非空 + `success=False` 三重标记，
  并有回归用例锁死"失败 MUST NOT 是成功空结果"。
- [错误信息进事件管道可能被广泛消费] → 只带类型名与消息文本，不带 traceback 与异常对象。

## Migration Plan

1. 合入即生效（无开关）：失败开始产生结果，消费者按 `error` / `success` 判别
2. 需要"失败即中断整批"的调用方改为读 `WorkerResult.success`
3. 回滚 = revert 单个变更提交

## Open Questions

无。
