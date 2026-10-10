"""stage-2 验收：部署形态（适配链路）的负载形状对照测量（add-native-task-execution 5.1）.

四种负载形状（同一次运行内完成全部测量，遵守 bench/README 读数纪律；
**冻结真实输入**——固定帧组 + 事前固定的迭代数，不「循环到达标」）：

- single：单帧逐次端到端（125 寄存器大帧——工作包络内的形状）
- batch_small：每操作 8 帧（1 寄存器小帧）——边界转换成本占主导的形状
- batch_large：每操作 64 帧（125 寄存器大帧）——原生执行体收益占主导的形状
- saturate：12 线程并发压测（吞吐口径，对照纯 Python 参考实现同并发）

每形状记录：端到端 P50/P95/P99、吞吐（ops/s，每操作 = 处理 K 帧）、
转换/编排成本占比（适配链路相对裸 ``ext.execute`` 的增量）。

对照基线：P1 纯 Python 参考实现（``native/reference/modbus_rtu.py``）。
等价性前置检查不通过则中止测量（同 stage-0 phase-2 惯例）。

结果落盘：native/results/stage2_acceptance.json
"""

import json
import os
import platform
import sys
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

WARMUP_OPS = 300
SINGLE_OPS = 3000
BATCH_SMALL_OPS = 600  # 8 帧/操作
BATCH_LARGE_OPS = 300  # 64 帧/操作
SATURATE_THREADS = 12
SATURATE_OPS_PER_THREAD = 2000
TASK_NAME = "modbus_rtu.parse_response"


def _load_reference():
    path = REPO_ROOT / "native" / "reference" / "modbus_rtu.py"
    import importlib.util

    spec = importlib.util.spec_from_file_location("modbus_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _percentile(sorted_samples, pct):
    """线性插值百分位（样本已升序）."""
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (len(sorted_samples) - 1) * pct / 100.0
    low = int(rank)
    high = min(low + 1, len(sorted_samples) - 1)
    frac = rank - low
    return sorted_samples[low] * (1 - frac) + sorted_samples[high] * frac


def _stats(samples_us):
    samples_us.sort()
    return {
        "p50": round(_percentile(samples_us, 50), 3),
        "p95": round(_percentile(samples_us, 95), 3),
        "p99": round(_percentile(samples_us, 99), 3),
        "mean": round(sum(samples_us) / len(samples_us), 3),
    }


def _measure_op(fn, ops: int, frames_per_op: int):
    """逐操作计时（µs/操作），预热分离；返回 (统计, 吞吐 ops/s)."""
    for _ in range(WARMUP_OPS):
        fn()
    samples = []
    perf = time.perf_counter_ns
    for _ in range(ops):
        start = perf()
        fn()
        samples.append((perf() - start) / 1000.0)
    total_s = sum(samples) / 1e6
    return _stats(samples), round(ops * frames_per_op / total_s)


def _measure_saturate(fn, threads: int, ops_per_thread: int):
    """并发吞吐：barrier 对齐起跑，墙钟总时长口径（帧/秒）."""
    start_gate = threading.Barrier(threads + 1)
    done = threading.Barrier(threads + 1)
    errors: list[str] = []

    def worker():
        try:
            start_gate.wait()
            for _ in range(ops_per_thread):
                fn()
        except Exception as e:
            errors.append(repr(e))
        finally:
            done.wait()

    pool = [threading.Thread(target=worker) for _ in range(threads)]
    for t in pool:
        t.start()
    start_gate.wait()
    wall_start = time.perf_counter()
    done.wait()
    wall = time.perf_counter() - wall_start
    if errors:
        raise RuntimeError(f"饱和压测失败: {errors[:3]}")
    return round(threads * ops_per_thread / wall)


def main():
    reference = _load_reference()

    # 冻结帧组（与等价性测试同一构造方式，测量前一次性构建、全程复用）
    small1 = reference.build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34]))
    big125 = reference.build_frame(bytes([0x21, 0x03, 0xFA]) + bytes(i & 0xFF for i in range(250)))

    try:
        ext = __import__("zoo_framework_native")
    except ImportError:
        print("原生扩展未安装——stage-2 验收需要真实扩展，退出", file=sys.stderr)
        return 2

    from zoo_framework.native import NativeAdapter

    adapter = NativeAdapter()
    adapter.ensure_ready()  # 握手为进程内一次性成本，不进稳态测量
    contract = adapter.contract(TASK_NAME)

    def adapter_chain(frame):
        payload = adapter.prepare_input(frame, contract)
        return adapter.convert_output(adapter.execute(TASK_NAME, payload), contract)

    def reference_op(frames, count):
        parse = reference.parse_response
        for _ in range(count):
            parse(frames)

    def adapter_op(frames, count):
        for _ in range(count):
            adapter_chain(frames)

    # 等价性前置检查：链路与参考实现对同帧产出一致，测量才有效
    for frame in (small1, big125):
        expected = reference.parse_response(frame)
        assert json.loads(ext.execute(TASK_NAME, frame).decode()) == expected
        assert adapter_chain(frame) == expected

    shapes: dict = {}

    # 单帧（K=1）
    ref_stats, ref_tput = _measure_op(lambda: reference.parse_response(big125), SINGLE_OPS, 1)
    ad_stats, ad_tput = _measure_op(lambda: adapter_chain(big125), SINGLE_OPS, 1)
    bare_stats, _ = _measure_op(lambda: ext.execute(TASK_NAME, big125), SINGLE_OPS, 1)
    shapes["single"] = {
        "frames_per_op": 1,
        "frame": "125reg(255B)",
        "adapter": {**ad_stats, "ops_per_sec": ad_tput},
        "reference": {**ref_stats, "ops_per_sec": ref_tput},
        "bare_ext": bare_stats,
        "speedup_p50": round(ref_stats["p50"] / ad_stats["p50"], 2),
        "conversion_share": round((ad_stats["p50"] - bare_stats["p50"]) / ad_stats["p50"], 3),
    }

    # 小批（K=8，1 寄存器小帧）
    ref_stats, ref_tput = _measure_op(lambda: reference_op(small1, 8), BATCH_SMALL_OPS, 8)
    ad_stats, ad_tput = _measure_op(lambda: adapter_op(small1, 8), BATCH_SMALL_OPS, 8)
    shapes["batch_small"] = {
        "frames_per_op": 8,
        "frame": "1reg(7B)",
        "adapter": {**ad_stats, "ops_per_sec": ad_tput},
        "reference": {**ref_stats, "ops_per_sec": ref_tput},
        "speedup_p50": round(ref_stats["p50"] / ad_stats["p50"], 2),
    }

    # 大批（K=64，125 寄存器大帧）
    ref_stats, ref_tput = _measure_op(lambda: reference_op(big125, 64), BATCH_LARGE_OPS, 64)
    ad_stats, ad_tput = _measure_op(lambda: adapter_op(big125, 64), BATCH_LARGE_OPS, 64)
    shapes["batch_large"] = {
        "frames_per_op": 64,
        "frame": "125reg(255B)",
        "adapter": {**ad_stats, "ops_per_sec": ad_tput},
        "reference": {**ref_stats, "ops_per_sec": ref_tput},
        "speedup_p50": round(ref_stats["p50"] / ad_stats["p50"], 2),
    }

    # 饱和（12 线程，K=1，墙钟吞吐）
    ad_tput = _measure_saturate(
        lambda: adapter_chain(big125), SATURATE_THREADS, SATURATE_OPS_PER_THREAD
    )
    ref_tput = _measure_saturate(
        lambda: reference.parse_response(big125), SATURATE_THREADS, SATURATE_OPS_PER_THREAD
    )
    shapes["saturate"] = {
        "threads": SATURATE_THREADS,
        "ops_per_thread": SATURATE_OPS_PER_THREAD,
        "frame": "125reg(255B)",
        "adapter_frames_per_sec": ad_tput,
        "reference_frames_per_sec": ref_tput,
        "speedup_throughput": round(ad_tput / ref_tput, 2),
    }

    report = {
        "meta": {
            "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
            "platform": platform.platform(),
            "python": sys.version.split()[0],
            "cpus": os.cpu_count(),
            "discipline": "同一次运行内完成；冻结帧组与事前固定迭代数（非循环到达标）",
            "task": TASK_NAME,
            "warmup_ops": WARMUP_OPS,
        },
        "shapes": shapes,
    }

    out = REPO_ROOT / "native" / "results" / "stage2_acceptance.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"{'shape':<14}{'P50(µs/op)':>12}{'P95':>10}{'P99':>10}{'吞吐(帧/s)':>14}{'加速':>8}")
    for name, data in shapes.items():
        if name == "saturate":
            print(
                f"{name:<14}{'—':>12}{'—':>10}{'—':>10}"
                f"{data['adapter_frames_per_sec']:>14,}{data['speedup_throughput']:>7}x"
            )
            continue
        print(
            f"{name:<14}{data['adapter']['p50']:>12.3f}{data['adapter']['p95']:>10.3f}"
            f"{data['adapter']['p99']:>10.3f}{data['adapter']['ops_per_sec']:>14,}"
            f"{data['speedup_p50']:>7}x"
        )
    print(f"\n落盘: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
