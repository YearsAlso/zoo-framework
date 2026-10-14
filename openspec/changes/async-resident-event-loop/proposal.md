# 提案：async-resident-event-loop —— 常驻事件循环执行模型（issue #235）

> **本变更当前只交付提案与设计。** 设计与既有契约的一致处已逐条对齐，但存在两处**必须维护者拍板**的分歧（结果契约的缝合点、公开模式登记面的归属），以及一处**超出本次授权文件范围**的必需改动（`zoo_framework/constant/waiter_constant.py`）。按纪律不擅自实现；分歧与授权需求见 `design.md` 的 Open Questions 与本文档的「阻塞项」，实现项在 `tasks.md` 中保持未勾选状态。

## Why

issue #235 的现象：框架里有"异步"的**写法**，没有异步的**调度模型**。

- `AsyncWorker._execute` 每次派发都 `asyncio.run(...)`——一次执行等于建一个 loop、关一个 loop；
- 于是"执行期间只跑一条协程"，`asyncio.Semaphore(self._max_concurrent)` 形同虚设（同一时刻只有一条协程在跑），真正的并发只能由**线程数**提供：10 条会话等 LLM 响应就是 10 条线程各自阻塞；
- `AsyncWorkerPool` 的 `submit`/`map` 只能在"已处于运行中 loop"处调用（`asyncio.get_running_loop()`），而调度路径恰恰是**没有 loop 的普通线程**，全仓没有任何调度侧代码使用它；
- `CONCURRENCY_EVENT_LOOP` 全包只有一行声明（`core/waiter/scheduler_model.py:44`），没有任何 `SchedulerModel` 声明它，`IMPLEMENTED_WORKER_MODES` 只有 thread / thread_pool。

对 I/O 密集消费者（典型是 LLM agent：绝大多数时间在等 HTTP），"一条线程阻塞等一个调用"是最贵的形态：线程栈与上下文切换随并发线性增长，且无法表达"同一个 Worker 同时推进 N 个在飞请求"。而框架的**编排语义**（注册、周期、在飞、超时熔断、结果投递、停机）在两种形态下是同一套，不需要重写——缺的只是一条 `SchedulerModel`。

## What Changes（设计结论，待裁决后实施）

- 新增 `EventLoopModel(SchedulerModel)`：`concurrency_primitive = CONCURRENCY_EVENT_LOOP`，在**独立守护线程**上常驻一个事件循环，派发时把协程投给该循环；容器生命周期归模型（`start` 建、`teardown` 收），与 `ThreadPoolModel` 同形。
- `AsyncWorker` 的驱动路径改为**由执行模型决定**：常驻循环模型下 MUST NOT 自建循环；thread / thread_pool 模型下保留既有 `asyncio.run` 行为（向后兼容）。
- **同步/CPU 密集执行体 MUST NOT 进入循环线程**：模型只接纳协程能力 Worker（`AsyncWorker` 子类），其余**显式拒绝**并提示改用 thread / thread_pool，MUST NOT 静默降级或自动搬去线程池。
- 超时与取消沿用既有诚实性：`reap_timeout` 只观测、熔断、停止派发，MUST NOT 声称终止了仍在执行的协程；停机时只丢弃**尚未开始**的协程（`stop_semantics = stop_dispatch_cancel_queued`）。
- `CONCURRENCY_EVENT_LOOP` 原语按"**实现**"处置（新增声明它的模型），不从公开面移除；理由见 `design.md` 的 ③。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `async-worker-runtime`：新增两条 Requirement——「异步 Worker 的驱动路径 MUST 由执行模型决定」（常驻循环下不得自建循环）与「常驻事件循环的生命周期 MUST 由执行模型持有且停机 MUST 幂等」。
- `scheduler-model`：新增一条 Requirement——「`event_loop` 模型 MUST 只接纳协程 Worker 且 MUST NOT 声称终止仍在执行的协程」。

## 阻塞项（本次未落地的直接原因）

1. **授权**：新增公开调度模式需要在 `zoo_framework/constant/waiter_constant.py` 登记 `WORKER_MODE_EVENT_LOOP` 并把它加入 `IMPLEMENTED_WORKER_MODES`；该文件**不在**本次允许改动的文件清单内（允许清单为 `workers/async_worker.py`、`core/waiter/` 中的执行模型相关文件、对应 tests/、本变更目录）。不改它，`BaseWaiter.validate_worker_mode` 与 `WaiterFactory.get_waiter` 都会明确拒绝该模式，功能无法被选中。
2. **设计分歧（需拍板）**：协程 Worker 的**结果契约缝合点**——见 `design.md` 的 D2/P1–P3。模型托管协程后不再有线程调用 `BaseWorker.run()`，而结果契约（含 #228 的失败语义、运行标识盖章）目前只在 `run()` 与 `WorkerDispatchCore.settle` 里；要么模型侧重塑一份（两份契约漂移风险），要么在 `workers/base_worker.py` 开一条"由已得值产出结果"的缝（该文件本次明确禁止改动）。

## Impact（裁决通过后的预期）

- **代码**：`zoo_framework/core/waiter/scheduler_model.py`（`EventLoopModel`）、`zoo_framework/core/waiter/base_waiter.py`（`_build_model` 分支）、`zoo_framework/workers/async_worker.py`（驱动路径）、`zoo_framework/constant/waiter_constant.py`（模式常量，**待授权**）；分歧裁定为 P3 时另需 `zoo_framework/workers/base_worker.py`（**待授权**）。
- **测试**：新增常驻循环回归用例（循环复用：整段运行期只建一次循环；停机后不再接收新任务；同步 Worker 被显式拒绝；超时只观测不声称终止）。
- **文档**：`async_execute` 的硬约束（阻塞调用 MUST NOT 直接写在协程里）、循环线程与 `Master.run()` 主线程循环的关系。
