"""Performance readings for async-resident-event-loop (design ⑥).

Reproduces the four measurement criteria of design ⑥. Run from the change
directory with the worktree interpreter:

    F:/Python/zoo/.venv/Scripts/python.exe perf_readings.py

Readings are printed as ``KEY=value`` lines and mirrored into
``perf-readings.md`` by hand (kept as the reproducible artifact).
"""

from __future__ import annotations

import asyncio
import statistics
import threading
import time

from zoo_framework.constant import WaiterConstant
from zoo_framework.core.waiter.base_waiter import BaseWaiter
from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.core.waiter.scheduler_model import EventLoopModel, ThreadPerTaskModel
from zoo_framework.workers.async_worker import AsyncWorker


class _SleepWorker(AsyncWorker):
    """等待型异步 Worker：await 自定义时长后返回."""

    def __init__(self, name: str, sleep: float = 0.2):
        super().__init__(name)
        self._props["delay_time"] = 0
        self._props["is_loop"] = False
        self._sleep = sleep
        self.finished = 0

    async def async_execute(self, *args, **kwargs):
        await asyncio.sleep(self._sleep)
        self.finished += 1
        return "ok"


def _new_waiter(mode: str) -> BaseWaiter:
    return BaseWaiter(model_name=mode)


# --------------------------------------------------------------------- Ⅰ 循环创建次数
def reading_loop_creation(n: int = 8) -> None:
    """⑥-1：整段运行期创建循环次数（阈值 = 1，对 asyncio.new_event_loop 注入计数器）."""
    created = {"count": 0}
    real_new_loop = asyncio.new_event_loop

    def counting_new_loop(*args, **kwargs):
        created["count"] += 1
        return real_new_loop(*args, **kwargs)

    asyncio.new_event_loop = counting_new_loop
    try:
        waiter = _new_waiter(WaiterConstant.WORKER_MODE_EVENT_LOOP)
        workers = [_SleepWorker(f"w{i}", sleep=0.05) for i in range(n)]
        waiter.call_workers(workers)
        time.sleep(0.6)
        model_loops = created["count"]
        waiter.shutdown(wait=True, timeout=5)
    finally:
        asyncio.new_event_loop = real_new_loop

    print(f"loop_create_count_model_only={model_loops}")
    print("loop_create_threshold=1")


# --------------------------------------------------------------------- Ⅱ/Ⅲ 并发
def _run_dose(mode: str, n: int) -> None:
    base_threads = threading.active_count()
    waiter = _new_waiter(mode)
    workers = [_SleepWorker(f"c{i}", sleep=0.2) for i in range(n)]
    waiter.call_workers(workers)
    start = time.monotonic()
    peak = base_threads
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and sum(w.finished for w in workers) < n:
        waiter.execute_service()  # 驱动排期轮次（等价 Master.run 的节拍，此处加密）
        peak = max(peak, threading.active_count())
        time.sleep(0.005)
    elapsed = time.monotonic() - start
    pending = n - sum(w.finished for w in workers)
    waiter.shutdown(wait=True, timeout=5)
    print(
        f"mode={mode} n={n} elapsed_s={elapsed:.3f} "
        f"thread_delta={peak - base_threads} pending={pending}"
    )


def reading_concurrency(doses: tuple[int, ...] = (8, 32)) -> None:
    """⑥-2/3：线程占用不随 N 增长；N 个等待型调用总耗时落在 0.2s 量级."""
    for n in doses:
        _run_dose(WaiterConstant.WORKER_MODE_EVENT_LOOP, n)
        _run_dose(WaiterConstant.WORKER_MODE_THREAD, n)


# --------------------------------------------------------------------- Ⅳ 记账开销
def _measure_once(model_factory) -> float:
    """测一次"派出到结算落地"的耗时（秒）."""
    core = WorkerDispatchCore(default_run_timeout=5)
    model = model_factory()
    worker = _SleepWorker("acct", sleep=0.0)
    core.set_workers([worker])
    model.prepare_workers(core.workers)
    model.start(core)

    settle_done = {"done": False}
    original_settle = core.settle

    def wrapped_settle(*args, **kwargs):
        result = original_settle(*args, **kwargs)
        settle_done["done"] = True
        return result

    core.settle = wrapped_settle
    t0 = time.perf_counter()
    handle = core.begin(worker, 5)
    model.submit(core, worker)
    deadline = time.monotonic() + 5
    while not settle_done["done"] and time.monotonic() < deadline:
        time.sleep(0.0002)
    elapsed = time.perf_counter() - t0
    if handle is not None:
        model.teardown(core, wait=True, timeout=5)
    return elapsed


def _measure_submit_cost(model_factory, rounds: int = 200) -> float:
    """单次派出+结算的记账开销（中位数，剔除预热）."""
    samples = [_measure_once(model_factory) for _ in range(rounds + 20)]
    return statistics.median(samples[20:])


def reading_accounting(rounds: int = 200) -> None:
    """⑥-4：对比 event_loop 与 thread 模型的单次派出记账开销（倍率阈值建议 ≤2×）."""
    ev = _measure_submit_cost(lambda: EventLoopModel(), rounds)
    th = _measure_submit_cost(lambda: ThreadPerTaskModel(), rounds)
    ratio = ev / th if th > 0 else float("inf")
    print(f"accounting_event_loop_us={ev * 1e6:.1f}")
    print(f"accounting_thread_us={th * 1e6:.1f}")
    print(f"accounting_ratio={ratio:.2f}")
    print("accounting_ratio_threshold_suggested=2.0 (pending maintainer confirmation)")


if __name__ == "__main__":
    import platform
    import sys

    print(f"python={sys.version.split()[0]} platform={platform.platform()}")
    reading_loop_creation(8)
    reading_concurrency((8, 32))
    reading_accounting(200)
