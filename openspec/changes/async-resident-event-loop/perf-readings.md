# 性能读数（design ⑥ 口径）：async-resident-event-loop

复现：`PYTHONPATH=<worktree 根> F:/Python/zoo/.venv/Scripts/python.exe openspec/changes/async-resident-event-loop/perf_readings.py`

- 解释器：Python 3.13.14；平台：Windows-11-10.0.26200-SP0
- 读数 ⑥-4 取 200 次样本的中位数并剔除前 20 次预热；⑥-1/2/3 为单次采样（判据本身是计数/量级，非分布）

## ⑥-1 循环创建次数（最小判据，阈值 = 1）

对 `asyncio.new_event_loop` 注入计数器，`event_loop` 模型 **仅由模型自身**创建的循环数：

```
loop_create_count_model_only=1
loop_create_threshold=1
```

结论：整段运行期恰好 **1 次**创建（满足阈值）。修复前 thread 模型下每次派发 1 次建 + 1 次关。

## ⑥-2/3 线程占用与并发推进

`mode=event_loop`（常驻循环）与 `mode=thread` 对照；工作线程增量 = 峰值活跃线程 − 基线：

```
mode=event_loop n=8  elapsed_s=0.213 thread_delta=1  pending=0
mode=thread     n=8  elapsed_s=0.555 thread_delta=8  pending=0
mode=event_loop n=32 elapsed_s=0.213 thread_delta=0  pending=0
mode=thread     n=32 elapsed_s=1.429 thread_delta=32 pending=0
```

- ⑥-2：`event_loop` 工作线程增量 **不随 N 增长**（≤1，即那条常驻循环线程；n=32 的 0 是基线噪声——上一轮的循环线程尚未回收即被计入基线），thread 模型则为 8 / 32。
- ⑥-3：`event_loop` N=8 与 N=32 总耗时均 ≈ **0.213s**（落在 0.2s 量级，优于 0.6s 阈值），证明 `asyncio.Semaphore(max_concurrent)` 真正生效、同一 Worker 的 N 个等待被并发推进；thread 模型 N=32 为 1.429s。

## ⑥-4 单次派出的记账开销（阈值建议 ≤ 2×，**待维护者确认**）

`event_loop` 与 thread 模型各测"一次派出到结算落地"的耗时中位数：

```
accounting_event_loop_us=663.4
accounting_thread_us=42569.8
accounting_ratio=0.02
accounting_ratio_threshold_suggested=2.0 (pending maintainer confirmation)
```

口径说明：thread 模型的单次读数**包含**每派发一次 `AsyncWorker._execute` 的 `asyncio.run`（建 + 关一个事件循环），这正是本变更要消除的成本；`event_loop` 侧无建循环、无线程创建。倍率 0.02 远低于 ≤2× 建议阈值。

**待确认项（不按已确认事实对待）**：⑥-4 的倍率阈值 2× 与基准机由维护者最终确认；本条读数仅供裁决参考。
