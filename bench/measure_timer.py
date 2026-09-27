"""定时器分辨率实测（adopt-rust-core 任务 3.6）.

测两件事在目标时长上的实际超时：`time.sleep` 与 `threading.Event.wait`。
Windows 的默认定时器 tick 约为 15.6 ms，会体现在后者上。

结果写入 bench/results/timer_resolution_<platform>.json。
"""

import json
import platform
import statistics
import threading
import time
from pathlib import Path

TARGETS = (0.0005, 0.001, 0.005)
REPEATS = 30


def _overshoot_ms(action, target: float, repeats: int = REPEATS) -> tuple[float, float]:
    """返回 (中位超时毫秒, 最大超时毫秒)."""
    overs = []
    for _ in range(repeats):
        start = time.perf_counter()
        action(target)
        overs.append((time.perf_counter() - start - target) * 1000)
    return statistics.median(overs), max(overs)


def main() -> int:
    event = threading.Event()

    results = {}
    print(f"平台: {platform.system()}-{platform.machine()}  Python {platform.python_version()}")
    print(f"{'目标':>9} | {'time.sleep 中位':>16} {'最大':>9} | {'Event.wait 中位':>16} {'最大':>9}")

    for target in TARGETS:
        sleep_median, sleep_max = _overshoot_ms(time.sleep, target)
        wait_median, wait_max = _overshoot_ms(event.wait, target)

        results[f"{target * 1000:g}ms"] = {
            "sleep_median_ms": round(sleep_median, 4),
            "sleep_max_ms": round(sleep_max, 4),
            "event_wait_median_ms": round(wait_median, 4),
            "event_wait_max_ms": round(wait_max, 4),
        }
        print(
            f"{target * 1000:7.1f}ms | {sleep_median:14.3f}ms {sleep_max:7.2f}ms | "
            f"{wait_median:14.3f}ms {wait_max:7.2f}ms"
        )

    payload = {
        "platform": f"{platform.system()}-{platform.machine()}",
        "python": platform.python_version(),
        "repeats": REPEATS,
        "results": results,
    }

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"timer_resolution_{payload['platform']}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n已写入 {out_file.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
