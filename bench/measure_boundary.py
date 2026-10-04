"""PyO3 边界成本实测（adopt-rust-core 任务组 3）.

测量四件事：
  1. Python -> Rust 空调用往返
  2. Rust -> Python 回调（持有 GIL）
  3. Python::allow_threads 释放并重新获取 GIL
  4. 粗粒度与细粒度调用形态的比值（design D2 的数据依据）

结果写入 bench/results/boundary_<platform>.json。
"""

import json
import platform
import statistics
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


def load_probe():
    """导入已构建的探针扩展.

    注意：`bench/pyo3_probe/` 是一个源码目录，会被 Python 当成命名空间包而抢先于
    真正的扩展模块，因此必须校验导入到的模块确实带有预期函数。
    """
    def _is_probe(module) -> bool:
        return all(hasattr(module, name) for name in ("noop", "call_python", "coarse_grained"))

    try:
        import pyo3_probe

        if _is_probe(pyo3_probe):
            return pyo3_probe
    except ImportError:
        pass

    wheels = sorted((REPO / "bench" / "pyo3_probe" / "target" / "wheels").glob("*.whl"))
    if wheels:
        import zipfile

        unpacked = REPO / "bench" / "pyo3_probe" / "target" / "unpacked"
        unpacked.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(wheels[-1]) as archive:
            archive.extractall(unpacked)

        sys.path.insert(0, str(unpacked))
        sys.modules.pop("pyo3_probe", None)

        import pyo3_probe

        if _is_probe(pyo3_probe):
            return pyo3_probe

    # 没有 wheel 时回退到 cargo 的直接产物（Linux 上用 `cargo build --release` 构建）
    import shutil

    built = sorted((REPO / "bench" / "pyo3_probe" / "target" / "release").glob("libpyo3_probe.*"))
    if built:
        staging = REPO / "bench" / "pyo3_probe" / "target" / "unpacked"
        staging.mkdir(parents=True, exist_ok=True)
        target = staging / "pyo3_probe.so"
        shutil.copyfile(built[0], target)

        sys.path.insert(0, str(staging))
        sys.modules.pop("pyo3_probe", None)

        import pyo3_probe

        if _is_probe(pyo3_probe):
            return pyo3_probe

    raise SystemExit(
        "未找到可用的探针扩展。请先构建：\n"
        '  cd bench/pyo3_probe && maturin build --release -i "<python 可执行文件>"\n'
        "或：\n"
        "  cd bench/pyo3_probe && cargo build --release"
    )


def sample(fn, n: int, repeats: int = 7):
    """返回 (每次调用的最优值, 中位值)，单位纳秒."""
    samples = []
    for _ in range(repeats):
        start = time.perf_counter()
        fn(n)
        samples.append((time.perf_counter() - start) / n * 1e9)
    return min(samples), statistics.median(samples)


def main() -> int:
    probe = load_probe()
    N = 100_000

    def t_noop(n):
        for _ in range(n):
            probe.noop()

    def t_callback(n):
        fn = probe.call_python
        cb = _noop_python
        for _ in range(n):
            fn(cb)

    def t_allow_threads(n):
        for _ in range(n):
            probe.allow_threads_roundtrip()

    def t_python_call(n):
        for _ in range(n):
            _noop_python()

    results = {}
    results["python_to_rust_noop"] = dict(zip(("best_ns", "median_ns"), sample(t_noop, N)))
    results["rust_to_python_callback"] = dict(
        zip(("best_ns", "median_ns"), sample(t_callback, N))
    )
    results["allow_threads_roundtrip"] = dict(
        zip(("best_ns", "median_ns"), sample(t_allow_threads, N))
    )
    results["python_only_call"] = dict(zip(("best_ns", "median_ns"), sample(t_python_call, N)))

    # 粗粒度 vs 细粒度：同样做 N 件事，前者只穿越一次边界
    work = 1000
    def t_fine(n):
        for _ in range(n):
            probe.fine_grained(work, _noop_python)

    def t_coarse(n):
        for _ in range(n):
            probe.coarse_grained(work, _noop_python)

    fine = sample(t_fine, 200, repeats=5)[0]
    coarse = sample(t_coarse, 200, repeats=5)[0]
    results["fine_grained_per_call"] = {"best_ns": fine}
    results["coarse_grained_per_call"] = {"best_ns": coarse}
    results["granularity_ratio"] = {"ratio": fine / coarse, "work_per_call": work}

    payload = {
        "platform": f"{platform.system()}-{platform.machine()}",
        "python": platform.python_version(),
        "results": results,
    }

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / f"boundary_{payload['platform']}.json"
    out_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"平台: {payload['platform']}  Python {payload['python']}")
    print(f"  Python→Rust 空往返      : {results['python_to_rust_noop']['best_ns']:8.1f} ns")
    print(f"  Rust→Python 回调        : {results['rust_to_python_callback']['best_ns']:8.1f} ns")
    print(f"  allow_threads 往返      : {results['allow_threads_roundtrip']['best_ns']:8.1f} ns")
    print(f"  纯 Python 空调用（参照）: {results['python_only_call']['best_ns']:8.1f} ns")
    print(
        f"  细粒度({work} 件事逐次跨界): {fine:8.1f} ns/次"
        f"  |  粗粒度(一次跨界): {coarse:8.1f} ns/次"
        f"  |  比值 {fine / coarse:.2f}x"
    )
    print(f"\n已写入 {out_file.relative_to(REPO)}")
    return 0


def _noop_python():
    """被 Rust 回调的 Python 函数."""


if __name__ == "__main__":
    raise SystemExit(main())
