"""阶段 0 第一组测量：任务体加速比 + 多线程伸缩（受控形态探针）.

注意：不是任务选定的剖析（那是 tasks 1.1/1.2 确认后的事），而是回答两个机制问题：
1. 单任务加速比: 同一 CPU 密集形态，纯 Python vs Rust（PyO3 扩展，执行期间释放 GIL）
2. 多线程伸缩: N=1..8 个并发 CPU 任务，两种形态的墙钟伸缩率对比
   —— 验证「原生执行期间松 GIL → 真多核」是否在本机成立

读数纪律（bench/README 三条硬约束）：预热分离、多轮取中位与离散度、
本次全套数据来自同一次运行（不能跨运行做减法）。
"""

import statistics
import sys
import threading
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
WARMUP_ROUNDS = 3
MEASURE_ROUNDS = 7


def load_probe():
    """导入探针扩展（与 bench/measure_boundary.load_probe 相同的回退逻辑）.

    命名空间包抢占防御：源码目录 bench/pyo3_probe/ 会先于扩展被 Python 识别，
    故导入后必须校验函数存在，不存在则回退到解包 wheel。
    """

    def _is_probe(module) -> bool:
        return all(hasattr(module, name) for name in ("noop", "call_python", "coarse_grained"))

    probe = None
    try:
        import pyo3_probe

        if _is_probe(pyo3_probe):
            probe = pyo3_probe
    except ImportError:
        pass

    if probe is None:
        unpacked = REPO / "bench" / "pyo3_probe" / "target" / "unpacked"
        if unpacked.exists():
            sys.path.insert(0, str(unpacked))
            sys.modules.pop("pyo3_probe", None)
            import pyo3_probe

            if _is_probe(pyo3_probe):
                probe = pyo3_probe

    if probe is None:
        raise RuntimeError(
            "探针扩展未构建/未解包：请在 bench/pyo3_probe 下 maturin build，"
            "或把 wheel 解包到 target/unpacked"
        )
    return probe


def python_cpu_body(n: int) -> int:
    """CPU 密集核心（与 probe coarse_grained 同形态）."""
    acc = 0
    for i in range(n):
        term = (i * (i + 1)) & 0xFFFFFFFF
        acc = (acc + term) & 0xFFFFFFFF
    return acc


def time_median(fn, *args):
    """预热分离后的中位与离散度."""
    for _ in range(WARMUP_ROUNDS):
        fn(*args)
    samples = sorted(
        (lambda t0: (fn(*args), time.perf_counter() - t0)[1])(time.perf_counter())
        for _ in range(MEASURE_ROUNDS)
    )
    return statistics.median(samples), samples


def measure_single_task(probe, n):
    py_med, py_all = time_median(python_cpu_body, n)
    call = lambda: None  # noqa: E731
    rs_med, rs_all = time_median(probe.coarse_grained, n, call)
    ratio = py_med / rs_med if rs_med > 0 else float("inf")
    print(f"[single] n={n}")
    print(
        f"  python median={py_med * 1000:.2f}ms  min={py_all[0] * 1000:.2f}  max={py_all[-1] * 1000:.2f}"
    )
    print(
        f"  rust   median={rs_med * 1000:.3f}ms  min={rs_all[0] * 1000:.3f}  max={rs_all[-1] * 1000:.3f}"
    )
    print(f"  单任务加速比 N = {ratio:.1f}x")
    return py_med, rs_med


def measure_scaling(py_single_med, rs_single_med, n, workers_counts=(1, 2, 4, 8)):
    call = lambda: None  # noqa: E731
    # 伸缩测量里每个线程连做 per_thread 处任务，摊薄线程启动开销——
    # 单任务体 0.13ms 时启动开销（约 50-100µs/线程）会主导墙钟，掩盖真实伸缩。
    per_thread = 20
    probes = {"python": python_cpu_body, "rust": (lambda nn: probe.coarse_grained(nn, call))}
    for label, fn in probes.items():
        row = []
        for workers in workers_counts:
            times = []
            for _ in range(MEASURE_ROUNDS):
                barrier = threading.Barrier(workers)

                def run_one(barrier=barrier, fn=fn):
                    barrier.wait()
                    for _ in range(per_thread):
                        fn(n)

                threads = [threading.Thread(target=run_one) for _ in range(workers)]
                t0 = time.perf_counter()
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                times.append(time.perf_counter() - t0)
            med = statistics.median(sorted(times))
            row.append((workers, med))
        line = "  ".join(f"{w}thr:{t * 1000:.0f}ms" for w, t in row)
        t1 = row[0][1]
        scale = "  ".join(f"{w}thr:{t1 / t:.2f}x" for w, t in row)
        ideal = "  ".join(f"{w}thr:{w}x" for w, _ in row)
        print(f"[scaling] {label} (每线程连做{per_thread}任务): {line}")
        print(f"          伸缩率(vs 自身单线程): {scale}   理想: {ideal}")
        throughput = [
            (workers * per_thread * n / wallclock / 1e6, workers) for workers, wallclock in row
        ]
        print("          吞吐: " + "  ".join(f"{w}thr:{tp:.0f} Miter/s" for tp, w in throughput))
        print()


if __name__ == "__main__":
    probe = load_probe()
    n = 200_000
    print(f"平台: {sys.platform}  轮次: 预热{WARMUP_ROUNDS}+测量{MEASURE_ROUNDS}")
    py_med, rs_med = measure_single_task(probe, n)
    print()
    measure_scaling(py_med, rs_med, n)
