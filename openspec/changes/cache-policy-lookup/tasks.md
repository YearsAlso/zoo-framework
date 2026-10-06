## 1. 实施

- [x] 1.1 `WorkerDispatchCore` 增 `_policy_cache`（(worker 名, 属性) -> 值）与 `_POLICY_MISS` 哨兵；`resolve_period/phase/run_timeout` 改为查缓存 + `_compute_*` 惰性求值；读写在既有 RLock 内
- [x] 1.2 失效三入口：`set_workers` 全清、`add_worker` 同名清该 Worker、`clear` 全清

## 2. 验证

- [x] 2.1 新增 `tests/test_policy_cache.py`：命中只查一次 / falsy 值有效（phase=0）/ 自报短路 / 三个失效入口，共 6 条
- [x] 2.2 既有调度用例（scheduler-model / worker-scheduling / execution-time）全绿——三段语义与排期行为未变
- [x] 2.3 全量门禁：pytest 只增不减、mypy 0 error、ruff/bandit 绿；CHANGELOG 记 Changed
- [ ] 2.4 权威数字：合并后 zoo-bench 重测 `attribution.drill_down.policy_lookup_seconds` 显著下降（#47 验收项，跨机器读数只认 zoo-bench 口径）
