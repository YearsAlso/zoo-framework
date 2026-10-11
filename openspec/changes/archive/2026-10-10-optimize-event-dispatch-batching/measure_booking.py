"""optimize-event-dispatch-batching 任务 4.1 —— 摊簿记测量（同一进程内对照）.

**测什么**：`ThreadPoolExecutor.submit` 的**簿记成本**。同一批事件分别按

- 逐事件提交（`k=1`，既有路径：每个事件一次 submit）
- 按批提交（本变更路径：同目标 K 个事件一次 submit，批内逐事件执行）

投递，读数是「投递段挂在执行器上的成本」，除以事件数即**每事件摊到的簿记**。
事件体取空实现（`execute` 立即返回），且排空侧的出队/过期/查找不在计时范围内
——所以这是投递段的下界对照，不是端到端吞吐；端到端还含反应器体本身。

**读数约束**（沿用 bench/README 的三条硬约束）：对照取数在同一进程同一次运行内
完成、体成本在同一次运行内测得、不跨次运行做减法。事件体为空 ⇒ 本测量只回答
「簿记摊薄了多少」，不回答「事件管道快了多少」。

跑法（仓库根目录，用开发解释器；不要用 `uv run`，它会换掉被测版本）：

    python openspec/changes/optimize-event-dispatch-batching/measure_booking.py
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, wait
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from zoo_framework.params import EventParams
from zoo_framework.workers.event_worker import EventWorker

EVENTS = 4096
BATCH_SIZES = (1, 8, 64)
REPEATS = 7
WARMUPS = 1


class _NoopReactor:
    """空事件体：计时只反映簿记，不混入响应器自身耗时."""

    def execute(self, topic, content) -> None:
        return None


def _items() -> list[tuple[str, str, None]]:
    return [("t", f"c{i}", None) for i in range(EVENTS)]


def _submit_per_event(pool: ThreadPoolExecutor, reactor: _NoopReactor, items) -> None:
    futures = [pool.submit(reactor.execute, topic, content) for topic, content, _ in items]
    wait(futures, timeout=60)


def _submit_batched(
    pool: ThreadPoolExecutor, reactor: _NoopReactor, items, batch_size: int
) -> None:
    futures = []
    for start in range(0, len(items), batch_size):
        chunk = items[start : start + batch_size]
        futures.append(pool.submit(EventWorker._run_batch, reactor, chunk))
    wait(futures, timeout=60)


def _measure(pool: ThreadPoolExecutor, reactor: _NoopReactor, items, batch_size: int) -> float:
    samples = []
    for index in range(WARMUPS + REPEATS):
        started = time.perf_counter_ns()
        if batch_size == 1:
            _submit_per_event(pool, reactor, items)
        else:
            _submit_batched(pool, reactor, items, batch_size)
        elapsed = time.perf_counter_ns() - started
        if index >= WARMUPS:  # 丢弃预热轮
            samples.append(elapsed / 1e9)
    return statistics.median(samples)


def main() -> int:
    pool = ThreadPoolExecutor(
        max_workers=EventParams.EVENT_EXECUTOR_WORKERS, thread_name_prefix="measure-book"
    )
    reactor = _NoopReactor()
    items = _items()
    try:
        readings = {}
        for batch_size in BATCH_SIZES:
            seconds = _measure(pool, reactor, items, batch_size)
            readings[batch_size] = {
                "batch_size": batch_size,
                "submits_per_round": -(-EVENTS // batch_size),
                "median_seconds": round(seconds, 6),
                "micros_per_event": round(seconds / EVENTS * 1e6, 3),
            }
            print(
                f"K={batch_size:>3}  提交 {readings[batch_size]['submits_per_round']:>5} 次/轮  "
                f"中位 {seconds * 1e3:8.3f} ms/轮  "
                f"{readings[batch_size]['micros_per_event']:8.3f} µs/事件"
            )
    finally:
        pool.shutdown(wait=False)

    baseline = readings[1]["micros_per_event"]
    for entry in readings.values():
        entry["speedup_vs_per_event"] = round(baseline / entry["micros_per_event"], 2)

    payload = {
        "measurement": "executor booking amortized per event (noop reactor body)",
        "change": "optimize-event-dispatch-batching",
        "task": "4.1",
        "events_per_round": EVENTS,
        "repeats": REPEATS,
        "warmups": WARMUPS,
        "statistic": "median",
        "executor_workers": EventParams.EVENT_EXECUTOR_WORKERS,
        "batch_max_size_default": EventParams.BATCH_MAX_SIZE,
        "readings": [readings[k] for k in BATCH_SIZES],
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "processor": platform.processor(),
            "cpu_count": __import__("os").cpu_count(),
        },
        "caveats": [
            "只测投递段簿记：排空侧出队/过期/响应器查找与反应器体成本都不在计时内",
            "同一次运行内对照（bench/README 约束②③），不跨次运行做减法",
            "Windows 定时器粒度约 15.6 ms（Python 3.11/3.12）——单轮中位数取 7 次重复的中位数以压住粒度噪声",
        ],
    }
    out = Path(__file__).with_name("booking_measurement.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\n读数已写入 {out.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
