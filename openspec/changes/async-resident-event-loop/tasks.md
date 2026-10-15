# Tasks: async-resident-event-loop（issue #235）

> 状态：**实现完成，待审查**。§4 的五处待裁决已由维护者拍板（见下），代码与文档已同步落地。

## 1. 判定与证据收集（已完成）

- [x] 1.1 核对现状：`AsyncWorker._execute` 每次 `asyncio.run`；`CONCURRENCY_EVENT_LOOP` 全仓仅 1 处声明（`scheduler_model.py:44`）；`IMPLEMENTED_WORKER_MODES` 仅 thread / thread_pool；`AsyncWorkerPool` 无任何调度侧调用点
- [x] 1.2 核对既有契约：`scheduler-model` 规格六项声明 + 五类共享逻辑"新模型 MUST NOT 重新实现"（本变更正是契约内的扩展）；模式选择显式且不做降级；超时只观测不声称终止
- [x] 1.3 定位结果契约唯一构造点：`BaseWorker.run()`（#228 后失败也由它构造）→ `WorkerDispatchCore.settle`（唯一投递点）
- [x] 1.4 判定：需要**新执行模型**（非 Worker 级行为），理由见 design ②

## 2. 规格（spec-first，已完成）

- [x] 2.1 `specs/async-worker-runtime/spec.md`：ADDED「异步 Worker 的驱动路径 MUST 由执行模型决定」+「常驻事件循环的生命周期 MUST 由执行模型持有且停机 MUST 幂等」
- [x] 2.2 `specs/scheduler-model/spec.md`：ADDED「`event_loop` 模型 MUST 只接纳协程 Worker 且 MUST NOT 声称终止仍在执行的协程」
- [x] 2.3 `openspec validate async-resident-event-loop --strict` 通过

## 3. 设计（已完成，逐条回答 ①–⑥）

- [x] 3.1 ① 生命周期：创建/复用/关闭、与 Master 启停的次序约束、两层幂等停机
- [x] 3.2 ② 共存形态：新 `SchedulerModel`（非 Worker 级行为）+ D2 的 P1/P2/P3 取舍
- [x] 3.3 ③ `event_loop` 原语：选择「实现」，并说明为何不选「移除」
- [x] 3.4 ④ 同步/CPU 工作：准入显式拒绝 + Worker 级硬约束 + 措辞纪律
- [x] 3.5 ⑤ 取消/超时：只用既有 observe-only 语义，`stop_dispatch_cancel_queued`
- [x] 3.6 ⑥ 性能验收：4 条可复现口径与阈值主张

## 4. 裁决（维护者已拍板，实现依据）

- [x] 4.1 **结果契约缝合点**：裁定 **P3**——`workers/base_worker.py` 抽共用缝，`run()` 行为逐字节不变（原"禁止改动"约束解除）
- [x] 4.2 **授权**：授权改 `zoo_framework/constant/waiter_constant.py` 登记 `WORKER_MODE_EVENT_LOOP` 并加入 `IMPLEMENTED_WORKER_MODES`
- [x] 4.3 **停机取消已开始协程**：不做——`stop_semantics = STOP_CANCEL_QUEUED`
- [ ] 4.4 **性能阈值**：读数已采集落盘；第 4 条倍率阈值仍**待维护者确认**（不按已确认事实对待）
- [x] 4.5 **背压档位**：不引入自有档位，复用 `unbounded`；与 #233 对齐列为待观察项

## 5. 实现（已完成）

- [x] 5.1 `core/waiter/scheduler_model.py`：`EventLoopModel`（常驻循环 + 独立守护线程 `zoo-event-loop` + 六项 `describe()` 声明 + `prepare_workers` 拒绝非协程 Worker + 幂等 teardown）
- [x] 5.2 `core/waiter/base_waiter.py`：`_build_model` 增加 `event_loop` 分支
- [x] 5.3 `constant/waiter_constant.py`：`WORKER_MODE_EVENT_LOOP` + 加入 `IMPLEMENTED_WORKER_MODES`
- [x] 5.4 `workers/async_worker.py`：驱动路径改为由模型决定（常驻循环下不自建循环）；thread / thread_pool 下行为不变（无行为变更，仅文档说明）
- [x] 5.5 `workers/base_worker.py`：抽出 `build_result` 共用缝，`run()` 与模型托管路径共用同一份结果契约（行为逐字节不变）
- [x] 5.6 回归用例（`tests/test_async_resident_event_loop.py`，25 条）：**循环复用**（对 `asyncio.new_event_loop` 注入计数器，整段运行期只创建 1 次）；**停机后不再接收新任务**（在飞结果仍被投递、未开始被丢弃）；非协程 Worker 在 `event_loop` 模式下被显式拒绝且不静默切换；超时只观测不声称终止；`Semaphore` 真正生效（N 个等待型调用总耗时落在 0.2s 量级）；另加"`worker:mode` 缺省行为零变化"用例
  - 断言注入（assertion-integrity，串行执行、带 `VIOLATION` 标记）：V1 `submit` 每次派发新建循环 → `TestResidentLoopReuse::test_loop_created_exactly_once_across_many_dispatches` 变红（记到 9 次循环）；V2 `teardown` 不再标记丢弃 → `TestShutdownDiscardsNotStarted::test_started_not_interrupted_and_not_started_discarded` 变红（未开始协程被执行）；V3 `prepare_workers` 不再拒绝非协程 Worker → `TestAdmissionRejectsNonCoroutine` 两条变红（DID NOT RAISE）；V4 `_on_complete` 不结算 → 4 条结果投递用例变红（停机在飞结果、丢弃语义、两种成功/失败路径）；V5 `build_result` 丢弃失败标记 → 新增 `TestResultContractSeam` 两条 **加既有 #228 用例** `TestResultReporting::test_failed_worker_reports_a_distinguishable_result` 同时变红（证明 `run()` 确实改走共用缝）。逐次按 md5 逐字节还原（`scheduler_model.py` 077ea0b3…、`base_worker.py` a5147225… 与注入前一致），`git grep "VIOLATION" -- zoo_framework tests` 无残留
- [x] 5.7 性能读数按 ⑥ 口径采集并写入变更目录（`perf-readings.md`，含命令）

## 6. 验收

- [x] 6.1 全量 pytest 绿（本机 `F:/Python/zoo/.venv/Scripts/python.exe -m pytest -q` → 1283 passed，含 25 条新增）
- [x] 6.2 `ruff check zoo_framework` / `ruff check tests` / `ruff check example` 与 `mypy zoo_framework` 零错误（mypy 108 源文件）
- [x] 6.3 `openspec validate async-resident-event-loop --strict` 通过（实现落地后已复跑）
