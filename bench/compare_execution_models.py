"""执行模型对照：Python 调度路径 vs Rust 调度路径（adopt-rust-core 任务组 5）.

对照的是**同一条链路**：把一段 Python 执行体派发出去、执行、收到完成信号。

- Python 侧：框架当前的调度路径（`BaseWaiter` 资源池模式 + 结果经事件管道投递）
- Rust 侧：最小 Tokio 调度器（`pyo3_probe.RustDispatcher`），每个任务两次边界穿越
  （执行体一次、完成回调一次）

**对照的公平性**（任务 5.4）：两侧使用同一份执行体（`bench/workload.py`）与同一份
输入；两侧的完成信号都通过 `threading.Event.set()` 唤醒 Python 主线程，唤醒成本相同。
Rust 侧**不**实现完整调度语义（无超时熔断、无在飞表、无结果聚合）——它测的是这条
链路的下界，不是可用替代品的完整成本。

**单次请求的边界穿越次数**（任务 5.3）：Rust 侧恒为 2，脚本内断言。

结果写入 bench/results/execution_model_<platform>.json。
"""

import json
import logging
import platform
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "bench"))

from measure_boundary import load_probe  # noqa: E402
from workload import representative_body  # noqa: E402

from zoo_framework.constant import WaiterConstant  # noqa: E402
from zoo_framework.core.waiter.base_waiter import BaseWaiter  # noqa: E402
from zoo_framework.reactor.event_reactor_manager import EventReactorManager  # noqa: E402
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor  # noqa: E402
from zoo_framework.workers import BaseWorker  # noqa: E402

TIERS = (
    ("cpu-1x", 1, 0.0),
    ("cpu-10x", 10, 0.0),
    ("io-10ms", 1, 0.010),
)
ROUNDS = 60
WORKERS = 2

#: Rust 侧每个任务的边界穿越次数上界：执行体 1 次 + 完成回调 1 次
RUST_CROSSINGS_PER_TASK = 2


class _ProbeWorker(BaseWorker):
    def __init__(self, name: str, scale: int, io_wait: float):
        super().__init__({"name": name, "is_loop": False, "delay_time": 0})
        self.scale = scale
        self.io_wait = io_wait
        self.body_duration = 0.0

    def _execute(self):
        start = time.perf_counter()
        result = representative_body(self.io_wait, self.scale)
        self.body_duration = time.perf_counter() - start
        return result


def _measure_python_framework(scale: int, io_wait: float) -> dict:
    received = threading.Event()
    reactor = WaiterResultReactor()
    reactor.worker_names = None
    reactor.on_result = lambda _r: received.set()
    EventReactorManager().bind_topic_reactor(WaiterConstant.WORKER_RESULT_TOPIC, reactor)

    waiter = BaseWaiter()
    waiter.worker_mode = WaiterConstant.WORKER_MODE_THREAD_POOL
    waiter.pool_enable = True
    waiter.pool_size = WORKERS
    waiter.resource_pool = ThreadPoolExecutor(max_workers=WORKERS)

    e2e, body = [], []
    try:
        for index in range(ROUNDS):
            received.clear()
            worker = _ProbeWorker(f"P{index}", scale, io_wait)
            waiter.workers = [worker]
            waiter.worker_props.clear()

            start = time.perf_counter()
            waiter.execute_service()
            if not received.wait(10.0):
                raise SystemExit("Python 侧结果未在超时内送达")
            e2e.append(time.perf_counter() - start)
            body.append(worker.body_duration)
    finally:
        waiter.shutdown()
        reactor.on_result = None

    return _summarise(e2e, body, crossings=0)


def _measure_rust_dispatcher(probe, scale: int, io_wait: float) -> dict:
    received = threading.Event()
    crossings = {"count": 0}

    def _body():
        crossings["count"] += 1
        representative_body(io_wait, scale)

    def _on_complete():
        crossings["count"] += 1
        received.set()

    dispatcher = probe.RustDispatcher(WORKERS, _on_complete)
    e2e = []
    body_times = []

    def _timed_body():
        start = time.perf_counter()
        _body()
        body_times.append(time.perf_counter() - start)

    try:
        for _ in range(ROUNDS):
            received.clear()
            crossings["count"] = 0
            start = time.perf_counter()
            dispatcher.submit(_timed_body)
            if not received.wait(10.0):
                raise SystemExit("Rust 侧完成信号未在超时内送达")
            e2e.append(time.perf_counter() - start)
            assert crossings["count"] == RUST_CROSSINGS_PER_TASK, (
                f"单次请求的边界穿越次数为 {crossings['count']}，"
                f"超出上界 {RUST_CROSSINGS_PER_TASK}"
            )
    finally:
        dispatcher.shutdown()

    return _summarise(e2e, body_times, crossings=RUST_CROSSINGS_PER_TASK)


def _summarise(e2e: list, body: list, crossings: int) -> dict:
    e2e.sort()
    body.sort()
    median_e2e = e2e[len(e2e) // 2]
    median_body = body[len(body) // 2]
    return {
        "end_to_end_median_ms": median_e2e * 1000,
        "body_median_ms": median_body * 1000,
        "framework_overhead_median_ms": (median_e2e - median_body) * 1000,
        "crossings_per_task": crossings,
        "samples": len(e2e),
    }


def main() -> int:
    logging.disable(logging.CRITICAL)
    probe = load_probe()

    print(f"平台: {platform.system()}-{platform.machine()}  Python {platform.python_version()}")
    print(f"对照: Python 框架调度路径 vs Rust(Tokio) 调度路径，{ROUNDS} 轮/档位")
    print("      两侧使用同一份执行体与同一份唤醒机制；Rust 侧不实现完整调度语义")
    print()

    results = {}
    header = f"{'档位':>9} | {'Python 端到端':>14} | {'Rust 端到端':>13} | {'加速比':>7}"
    print(header)
    print("-" * len(header))

    for name, scale, io_wait in TIERS:
        py_row = _measure_python_framework(scale, io_wait)
        rs_row = _measure_rust_dispatcher(probe, scale, io_wait)
        speedup = py_row["end_to_end_median_ms"] / rs_row["end_to_end_median_ms"]
        results[name] = {"python": py_row, "rust": rs_row, "speedup": speedup}
        print(
            f"{name:>9} | {py_row['end_to_end_median_ms']:12.4f}ms | "
            f"{rs_row['end_to_end_median_ms']:11.4f}ms | {speedup:6.2f}x"
        )

    print()
    print("框架开销对照（端到端 - 执行体）：")
    for name, row in results.items():
        print(
            f"  {name:>9}: Python {row['python']['framework_overhead_median_ms']:8.4f}ms"
            f"  →  Rust {row['rust']['framework_overhead_median_ms']:8.4f}ms"
        )

    payload = {
        "platform": f"{platform.system()}-{platform.machine()}",
        "python": platform.python_version(),
        "rounds": ROUNDS,
        "workers": WORKERS,
        "note": "Rust 侧为最小对照实现，不含超时熔断/在飞表/结果聚合",
        "rust_crossings_per_task_upper_bound": RUST_CROSSINGS_PER_TASK,
        "results": results,
    }

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"execution_model_{payload['platform']}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {out_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
