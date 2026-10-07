## Why

issue #47 P2（"执行原语对齐"的最后一项，`align-execution-primitives` 归档时移交至此）：zoo-bench 与 `bench/DECISION.md` 实测 **`ThreadPoolExecutor.submit().result()` 31.9 µs vs 裸 `queue.Queue` 直连 1.86 µs——Future 记账占派发提交侧的绝大部分**；#47 留档的提交侧分解里 dispatch 段 14.2 µs 也指向同一处。本变更把 `ThreadPoolModel` 的容器从 `concurrent.futures.ThreadPoolExecutor` 换成「固定工作线程 + `queue.Queue`」，是纯 Python 改动、无新依赖。

合并后的 P1（策略缓存）与 #31（去 gevent）已落档，这是短任务派发开销的最后一块大头。

## What Changes

- `ThreadPoolModel` 内部实现替换：`start()` 建 `queue.Queue` + `effective_pool_size` 个 daemon 工作线程（`zoo-worker-{i}`）；`submit()` 把 `(carry_context 包裹的 run_and_settle, worker)` 入队；`teardown()` 先排空未开始任务（等价旧 `cancel_futures` 的"取消排队"停机语义）再投哨兵停线程
- **两个 MUST 语义逐项保持**（#47 P2 的验收红线）：
  - 背压三策略 `expand / queue / reject` 全部在 `prepare_workers` 层，未触碰——既有参数化用例即回归网
  - 单一结算收口不变：执行单元仍是 `core.run_and_settle → core.settle`
- 观测语义等价迁移：旧 `future.add_done_callback` 的逃逸异常观测改为工作线程循环内就地捕获记录（线程存活继续服务，新增用例锁定）；逃逸异常观测路径由 greenlet/Future 语义转为显式日志
- `start()` 对非法尺寸（`<= 0`）当场 `ValueError`——与旧 `ThreadPoolExecutor(max_workers=0)` 的报错行为对齐（旧实现靠标准库抛错，新实现显式守卫）
- 微基准（本机 Windows，饱和池纯提交记账）：`ThreadPoolExecutor.submit` 4.07 µs → `queue.put` 0.61 µs（**6.7x**）；权威数字待 zoo-bench `drill_down.dispatch` 重测（#47 验收口径）

无公共 API 变化、无 BREAKING：模型契约六项 `describe()` 输出逐项不变（`concurrency_primitive` 仍为 `thread_pool`——对外语义是"有界并发 + FIFO 排队"，容器实现不属契约）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `scheduler-model`：新增「线程池模型的排队与停机语义 MUST 与容器实现解耦」——FIFO 提交序、cancel_queued 只弃未开始、逃逸异常留痕且线程存活，三项实现无关的行为约束固化为条款

## Impact

- **代码**：`zoo_framework/core/waiter/scheduler_model.py`（仅 `ThreadPoolModel` 内部，`SchedulerModel` 基类与 `ThreadPerTaskModel` 不动）
- **测试**：`tests/test_scheduler_model.py` 新增 `TestQueueBackedPool` 5 条（固定线程/命名/daemon、FIFO 序、停机弃排队、逃逸异常留痕线程存活、非法尺寸拒绝）；`tests/test_worker_scheduling.py` 一处内部属性观察点 `model._pool._threads` → `model._threads`
- **文档**：`docs/structure.md` 若有 ThreadPoolExecutor 表述需同步（核实：现有文本描述背压吸收，未点名容器实现——不改）；CHANGELOG 记 Changed
- **issue**：#47 的 P2 项达成；P3/P4 在 zoo-bench#3/#4，P1 数字与本次合并后由 zoo-bench 例行跑分复现
