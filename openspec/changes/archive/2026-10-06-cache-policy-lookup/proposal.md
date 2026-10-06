## Why

zoo-bench 0.8.0 留档的提交侧分解（issue #47）：**每轮每个 Worker 三段策略解析实测 9.4 µs/任务，占提交侧 33%**——`resolve_period / resolve_phase / resolve_run_timeout` 每次现拼字符串键（`f"{WORKER_OVERRIDE_PREFIX}:{worker.name}:period"`）再查 `ParamsFactory`。而解析结果在 Worker 存续期内是静态的：配置没有运行期重载入口（全仓库仅 `WorkerDispatchCore.__init__` 与 `BaseWaiter` 构造时读取一次）。这是 `scheduler-model-seam` 那轮重构新引入的固定开销，被同轮 handoff 段的大幅改善掩盖了。

## What Changes

- `WorkerDispatchCore` 增加 `(worker 名, 属性) -> 已解析值` 的策略缓存；三个 `resolve_*` 变为"查缓存，未命中才走三段解析"
- 失效入口三处，与配置的静态性一致：`set_workers`（整体替换，全清）、`add_worker`（同名重注册清该 Worker 的条目）、`clear`（停机复位全清）
- **falsy 语义护栏**：未命中判据是哨兵 `object()` 的身份比较——缓存里的 `None / 0 / False / ""` 都是有效结果，MUST NOT 被当未命中重查或穿透到默认值（`ParamsPath._resolve` 用 `is not None` 判定，缓存不得比它更弱）
- 缓存读写统一在既有 `self._lock`（RLock，可重入）内进行，不新增锁

行为逐段保持：三段优先级、返回值域、`is_due` 排期语义均不变——这是纯性能改动，无 BREAKING。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `scheduler-model`：新增「策略解析结果 MUST 按 Worker 缓存且 MUST NOT 改变三段解析语义」——falsy 值缓存命中、重注册/换列表/停机三个失效入口的行为断言

## Impact

- **代码**：`zoo_framework/core/waiter/dispatch_core.py`（+约 40 行，含注释）
- **测试**：新增 `tests/test_policy_cache.py`（6 条：命中只查一次 / falsy 有效 / 自报短路 / 三个失效入口）
- **度量**：本机同码对照（resolve 层、空配置口径）三段解析合计 0.09 µs -> 0.005 µs（17.7x）；权威数字为 zoo-bench `attribution.drill_down.policy_lookup_seconds` 重测（#47 验收项，CI 合并后跑）
- **issue**：#47 的 P1 项完成后在 issue 标注；P2（派发路径 queue.Queue 替换）不受本变更影响、可独立启动
