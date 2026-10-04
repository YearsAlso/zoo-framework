"""框架自身开销占比的实测（adopt-rust-core 任务 6.1 / 6.2）.

测两个数：

1. **Worker 体执行时间中位数**——本框架里一次代表性的业务执行要多久
2. **框架自身开销占端到端延迟的比例**——从派发到结果投递完成的时间里，有多少是框架的账

定义：`端到端 = Worker 体耗时 + 框架开销`，其中框架开销涵盖派发、在飞状态维护、
线程/池调度、结果构造、经事件管道投递到响应器。

**方法学要点**：执行体耗时由探针 Worker 在**同一次运行内**埋点测量，而不是用另一
次单独测量的结果去减。单独测量与端到端运行中的耗时不在同一状态下（缓存、线程迁
移、GC 时机都不同），相减会引入系统性偏差——本脚本的第一版就因此把开销高估了一倍。

之所以按 Worker 体时长分层测量，是因为**框架开销的占比完全由被除数决定**：
同样的框架开销，在 30 µs 的执行体上占 70%+，在 10 ms 的执行体上只占百分之几。
单一数字没有意义，决策要看的正是"目标负载落在哪一档"。

结果写入 bench/results/framework_overhead_<platform>.json。
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

from workload import representative_body  # noqa: E402

from zoo_framework.constant import WaiterConstant  # noqa: E402
from zoo_framework.core.waiter.base_waiter import BaseWaiter  # noqa: E402
from zoo_framework.reactor.event_reactor_manager import EventReactorManager  # noqa: E402
from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor  # noqa: E402
from zoo_framework.workers import BaseWorker  # noqa: E402

# 档位：CPU 密集为主的三档 + 一档 I/O 密集
TIERS = (
    ("cpu-1x", 1, 0.0),
    ("cpu-10x", 10, 0.0),
    ("cpu-100x", 100, 0.0),
    ("io-10ms", 1, 0.010),
)

ROUNDS = 60


class _ProbeWorker(BaseWorker):
    """执行代表性负载、并在同一次运行内记录执行体起止时刻的探针 Worker."""

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


def _measure_tier(scale: int, io_wait: float) -> dict:
    """测量一个档位的端到端延迟与框架开销."""
    received = threading.Event()

    reactor = WaiterResultReactor()
    reactor.worker_names = None
    reactor.on_result = lambda _result: received.set()
    EventReactorManager().bind_topic_reactor(WaiterConstant.WORKER_RESULT_TOPIC, reactor)

    waiter = BaseWaiter()
    waiter.worker_mode = WaiterConstant.WORKER_MODE_THREAD_POOL
    waiter.pool_enable = True
    waiter.pool_size = 2
    waiter.resource_pool = ThreadPoolExecutor(max_workers=2)

    e2e_samples = []
    body_samples = []
    try:
        for index in range(ROUNDS):
            received.clear()
            worker = _ProbeWorker(f"Probe{index}", scale, io_wait)
            waiter.workers = [worker]
            waiter.worker_props.clear()

            start = time.perf_counter()
            waiter.execute_service()
            if not received.wait(10.0):
                raise SystemExit("结果未在超时内投递，测量无效")
            e2e_samples.append(time.perf_counter() - start)
            body_samples.append(worker.body_duration)
    finally:
        waiter.shutdown()
        reactor.on_result = None

    e2e_samples.sort()
    body_samples.sort()
    median_e2e = e2e_samples[len(e2e_samples) // 2]
    median_body = body_samples[len(body_samples) // 2]
    overhead = median_e2e - median_body

    return {
        "scale": scale,
        "io_wait_ms": io_wait * 1000,
        "body_median_ms": median_body * 1000,
        "end_to_end_median_ms": median_e2e * 1000,
        "framework_overhead_median_ms": overhead * 1000,
        "framework_overhead_ratio": overhead / median_e2e if median_e2e else 0.0,
        "samples": len(e2e_samples),
    }


def main() -> int:
    logging.disable(logging.CRITICAL)

    print(f"平台: {platform.system()}-{platform.machine()}  Python {platform.python_version()}")
    print("负载: 代表性 Worker 体（JSON 编解码 + 字符串处理 [+ 短 I/O]）")
    print("      ★ 这是真实业务 trace 的替身，适用边界见 bench/workload.py")
    print("      执行体耗时在同一次运行内埋点测得，不用单独测量的值做减法")
    print()

    results = {}
    header = (
        f"{'档位':>9} | {'Worker 体':>11} | {'端到端':>11} | {'框架开销':>10} | {'占比':>8}"
    )
    print(header)
    print("-" * len(header))

    for name, scale, io_wait in TIERS:
        row = _measure_tier(scale, io_wait)
        results[name] = row
        print(
            f"{name:>9} | {row['body_median_ms']:9.4f}ms | "
            f"{row['end_to_end_median_ms']:9.4f}ms | "
            f"{row['framework_overhead_median_ms']:8.4f}ms | "
            f"{row['framework_overhead_ratio'] * 100:7.2f}%"
        )

    payload = {
        "platform": f"{platform.system()}-{platform.machine()}",
        "python": platform.python_version(),
        "rounds": ROUNDS,
        "note": "代表性负载替身，非真实业务 trace；执行体耗时在同一次运行内埋点测得",
        "results": results,
    }

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"framework_overhead_{payload['platform']}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {out_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
