## 1. 实现

- [x] 1.1 `ThreadPoolModel` 容器替换：start 建 `queue.Queue` + `effective_pool_size` 个 daemon 线程（`zoo-worker-{i}`）；submit 入队 `(carry_context(core.run_and_settle), worker)` 并 attach 观测句柄；teardown 先 `_discard_queued` 再投 None 哨兵、`_join_threads` 保持总预算语义
- [x] 1.2 非法尺寸守卫：`effective_pool_size <= 0` 时 start 抛 `ValueError`（对齐旧 ThreadPoolExecutor 行为）
- [x] 1.3 逃逸异常观测迁移：done_callback → 工作线程循环内就地捕获记录（线程存活）

## 2. 语义保持（#47 P2 验收红线）

- [x] 2.1 背压三策略不动：`prepare_workers` 的 expand/queue/reject 未触碰；既有参数化用例（test_expand_policy_widens_effective_size_only 等）全绿
- [x] 2.2 单一结算收口不动：执行单元仍是 `core.run_and_settle → settle`；`test_run_identity.py` 的 thread_pool 参数化盖章用例全绿
- [x] 2.3 模型契约六项 `describe()` 输出逐项不变（含 stop_semantics=stop_dispatch_cancel_queued 的新实现语义：丢弃未开始 + 不中断已开始，由新用例锁定）

## 3. 测试与度量

- [x] 3.1 新增 `TestQueueBackedPool` 5 条：固定线程/命名/daemon、FIFO 提交序、停机弃排队、逃逸异常留痕线程存活、非法尺寸拒绝
- [x] 3.2 `tests/test_worker_scheduling.py` 内部观察点迁移（`model._pool._threads` → `model._threads`）
- [x] 3.3 全量门禁：pytest 705（700+5）只增不减、mypy 0 error、ruff/bandit 绿
- [x] 3.4 微基准（饱和池纯提交记账，本机）：ThreadPoolExecutor.submit 4.07 µs → queue.put 0.61 µs（6.7x）
- [x] 3.5 权威数字：（合并后收尾：#67 已进 dev，数字由 zoo-bench 例行跑分承接，转 zoo-bench#4 常驻形态 workload 一并出数，不再挂本变更）合并后 zoo-bench `drill_down.dispatch` / 提交侧总账重测（#47 验收口径；与 P1 同列在跑分中出数）

## 4. 联动

- [x] 4.1 CHANGELOG 记 Changed（无 BREAKING）
- [x] 4.2 已完成（#47 留言见 issuecomment-6028708270）：PR 合并后：#47 留言——P2 达成（红线两项：背压三策略、单一结算收口，逐项对账）；drill_down 数字随 zoo-bench 例行跑分回填
