# Tasks: async-resident-event-loop（issue #235）

> 状态：**提案与设计已交付；实现项未开始**——存在两处必须维护者拍板的分歧（结果契约缝合点 P1/P3、模式登记面授权），按纪律不擅自实现。

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

## 4. 待裁决（阻塞实现，本变更不代为决定）

- [ ] 4.1 **结果契约缝合点**：P1（模型侧重塑，两份契约漂移风险）vs P3（`base_worker.py` 开共用缝，需授权）——design D2 / Open Question 1
- [ ] 4.2 **授权**：允许改 `zoo_framework/constant/waiter_constant.py` 登记 `WORKER_MODE_EVENT_LOOP` 并加入 `IMPLEMENTED_WORKER_MODES`——proposal 阻塞项 1
- [ ] 4.3 停机时是否允许取消"已开始"的协程（默认不做）——design ⑤
- [ ] 4.4 性能阈值确认（⑥ 第 4 条倍率与基准机）——design ⑥
- [ ] 4.5 与 #233 对齐的背压档位——design Risks / Open Question 5

## 5. 实现（待 4.1/4.2 裁决后开始；此处先固化验收口径）

- [ ] 5.1 `core/waiter/scheduler_model.py`：`EventLoopModel`（常驻循环 + 独立守护线程 + 六项 `describe()` 声明 + `prepare_workers` 拒绝非协程 Worker + 幂等 teardown）
- [ ] 5.2 `core/waiter/base_waiter.py`：`_build_model` 增加 `event_loop` 分支
- [ ] 5.3 `constant/waiter_constant.py`（**待授权**）：`WORKER_MODE_EVENT_LOOP` + 加入 `IMPLEMENTED_WORKER_MODES`
- [ ] 5.4 `workers/async_worker.py`：驱动路径改为由模型决定（常驻循环下不自建循环）；thread / thread_pool 下行为不变
- [ ] 5.5 （仅当 4.1 裁定 P3）`workers/base_worker.py`（**待授权**）：抽出"由已得值产出结果"的共用缝，使 `run()` 与模型托管路径共用同一份结果契约
- [ ] 5.6 回归用例：**循环复用**（整段运行期只创建 1 次循环，对 `asyncio.new_event_loop` 注入计数器验证）；**停机后不再接收新任务**（停机后再派发被拒绝、在飞结果仍被投递）；非协程 Worker 在 `event_loop` 模式下被显式拒绝；超时只观测不声称终止；`Semaphore` 真正生效（N 个等待型调用总耗时落在 0.2s 量级）
- [ ] 5.7 性能读数按 ⑥ 口径采集并写入变更目录（可复核）

## 6. 验收（待实现后）

- [ ] 6.1 全量 `uv run pytest` 绿（既有 WSL 用例除外）
- [ ] 6.2 `uv run ruff check zoo_framework` / `uv run mypy zoo_framework` 零错误
- [ ] 6.3 `openspec validate async-resident-event-loop --strict` 通过（实现落地后复跑）
