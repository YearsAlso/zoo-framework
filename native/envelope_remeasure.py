"""收益包络重测：把四链路对照扩到小帧区间，并现场重估回归与门槛（issue #130）.

为什么不是 issue 里写的「10 / 12 / 16 字节」：Modbus RTU 响应帧长恒为 **5 + 2N**
（1 地址 + 1 功能码 + 1 字节数 + 2N 数据 + 2 CRC，N 为寄存器数），即 **恒为奇数**。
10 / 12 / 16 构造不出结构自洽的合法帧（`parse_response` 会按"帧结构不一致"拒绝）。
故取最近的合法点：**9B(2reg) / 11B(3reg) / 13B(4reg) / 15B(5reg)**——它们横跨模型
外推出的门槛（≈10.3B），足以回答"门槛是否低于 21 字节"。

四条链路与 ``bench/stage0_phase2_four_paths.py`` 逐字同义（同一方法的延续，不是新方法）：

- P1 纯 Python 参考实现（``native/reference/modbus_rtu.py``）
- P2 现有原生库形态：C 原语 + 查表 CRC
- P3 Rust 直调：``zoo_framework_native.execute`` + ``json.loads``
- P4 Zoo+Rust 适配链路：``NativeAdapter.execute`` + ``convert_output``（部署形态）

同时在**同一次运行**内复测原有三个点（7B / 21B / 255B），使回归重估建立在单次运行的
数据上（遵守 bench/README 的读数纪律③：不做跨运行的减法/拼接）。

结果落盘：native/results/envelope_remeasure.json
"""

import importlib.util
import json
import platform
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    ext = __import__("zoo_framework_native")
except ImportError:
    ext = None

WARMUP_ITERATIONS = 300
MEASURE_ITERATIONS = 3000
TASK_NAME = "modbus_rtu.parse_response"
GO_THRESHOLD_SPEEDUP = 1.5


def _load_reference():
    path = REPO_ROOT / "native" / "reference" / "modbus_rtu.py"
    spec = importlib.util.spec_from_file_location("modbus_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_c_primitive_parser():
    """P2：C 原语 + 查表 CRC 的典型既有实现形态."""
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        table.append(crc)

    def parse(frame):
        data = frame[:-2]
        expected = frame[-2] | (frame[-1] << 8)
        crc = 0xFFFF
        for byte in data:
            crc = (crc >> 8) ^ table[(crc ^ byte) & 0xFF]
        if crc != expected:
            raise ValueError("CRC 校验失败")
        slave, function = data[0], data[1]
        if function & 0x80:
            return {"slave": slave, "function": function, "exception": data[2]}
        byte_count = data[2]
        registers = [int.from_bytes(data[i : i + 2], "big") for i in range(3, 3 + byte_count, 2)]
        return {
            "slave": slave,
            "function": function,
            "byte_count": byte_count,
            "registers": registers,
        }

    return parse


def _percentile(sorted_samples, pct):
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (len(sorted_samples) - 1) * pct / 100.0
    low = int(rank)
    high = min(low + 1, len(sorted_samples) - 1)
    frac = rank - low
    return sorted_samples[low] * (1 - frac) + sorted_samples[high] * frac


def _measure(fn, frame):
    """同一运行内：预热分离后连测 N 轮，返回逐轮成本（µs）的 p50/p95/p99/mean."""
    for _ in range(WARMUP_ITERATIONS):
        fn(frame)
    samples = []
    perf = time.perf_counter_ns
    for _ in range(MEASURE_ITERATIONS):
        start = perf()
        fn(frame)
        samples.append((perf() - start) / 1000.0)
    samples.sort()
    return {
        "p50": round(_percentile(samples, 50), 3),
        "p95": round(_percentile(samples, 95), 3),
        "p99": round(_percentile(samples, 99), 3),
        "mean": round(sum(samples) / len(samples), 3),
    }


def _fit_line(xs, ys):
    """最小二乘拟合 y = a + b x，返回 (a, b, r2)."""
    n = len(xs)
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    sxx = sum((x - mean_x) ** 2 for x in xs)
    sxy = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    b = sxy / sxx
    a = mean_y - b * mean_x
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys, strict=True))
    r2 = 1 - ss_res / ss_tot if ss_tot else 1.0
    return a, b, r2


def _threshold(a1, b1, a4, b4, ratio):
    """解 P1(F) / P4(F) = ratio 的 F；无解（斜率不足）时返回 None."""
    # a1 + b1 F = ratio (a4 + b4 F)
    denom = b1 - ratio * b4
    if abs(denom) < 1e-12:
        return None
    return (ratio * a4 - a1) / denom


def _meta():
    meta = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "warmup_iterations": WARMUP_ITERATIONS,
        "measure_iterations": MEASURE_ITERATIONS,
        "extension_installed": ext is not None,
    }
    if ext is not None:
        meta["extension_file"] = str(ext.__file__)
    return meta


def main():
    reference = _load_reference()
    parse_c = _make_c_primitive_parser()

    frames = {
        "1reg(7B)": reference.build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34])),
        "2reg(9B)": reference.build_frame(bytes([0x01, 0x03, 0x04, 0x11, 0x22, 0x33, 0x44])),
        "3reg(11B)": reference.build_frame(
            bytes([0x01, 0x03, 0x06, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66])
        ),
        "4reg(13B)": reference.build_frame(
            bytes([0x01, 0x03, 0x08, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88])
        ),
        "5reg(15B)": reference.build_frame(
            bytes([0x01, 0x03, 0x0A, 0x11, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88, 0x99, 0xAA])
        ),
        "8reg(21B)": reference.build_frame(
            bytes([0x11, 0x04, 0x10]) + bytes(b for i in range(8) for b in (0xB0 + i, 0x2E + i))
        ),
        "125reg(255B)": reference.build_frame(
            bytes([0x21, 0x03, 0xFA]) + bytes(i & 0xFF for i in range(250))
        ),
    }

    adapter = None
    if ext is not None:
        from zoo_framework.native import NativeAdapter

        adapter = NativeAdapter()

    # 等价性前置检查：各链路对同帧必须产出相同 dict，否则测量无意义
    for label, frame in frames.items():
        expected = reference.parse_response(frame)
        assert parse_c(frame) == expected, f"P2 在 {label} 上与 P1 不一致"
        if ext is not None:
            assert json.loads(ext.execute(TASK_NAME, frame).decode()) == expected
            assert adapter.execute(TASK_NAME, frame) is not None

    paths = {
        "P1_python_reference": reference.parse_response,
        "P2_c_primitives": parse_c,
    }
    if ext is not None:
        paths["P3_rust_direct"] = lambda frame: json.loads(ext.execute(TASK_NAME, frame).decode())
        paths["P4_zoo_adapter"] = lambda frame: adapter.convert_output(
            adapter.execute(TASK_NAME, frame), adapter.contract(TASK_NAME)
        )
        paths["supp_rust_raw"] = lambda frame: ext.execute(TASK_NAME, frame)

    results = {"meta": _meta(), "frames": {}, "verdict": {}, "model": {}}
    for label, frame in frames.items():
        row = {}
        for path_name, fn in paths.items():
            row[path_name] = _measure(fn, frame)
        results["frames"][label] = row

        if ext is not None:
            p1, p4 = row["P1_python_reference"], row["P4_zoo_adapter"]
            speedup = round(p1["p50"] / p4["p50"], 2)
            p99_regression = round((p4["p99"] / p1["p99"]) - 1.0, 4)
            results["verdict"][label] = {
                "speedup_p50": speedup,
                "p99_regression": p99_regression,
                "go": speedup >= GO_THRESHOLD_SPEEDUP and p99_regression <= 0.05,
            }

    # 回归重估：F = 帧字节数，用本次运行的全部点
    sizes = [len(frame) for frame in frames.values()]
    p1_p50 = [results["frames"][label]["P1_python_reference"]["p50"] for label in frames]
    p4_p50 = [results["frames"][label]["P4_zoo_adapter"]["p50"] for label in frames]
    a1, b1, r1 = _fit_line(sizes, p1_p50)
    a4, b4, r4 = _fit_line(sizes, p4_p50)
    results["model"] = {
        "P1": {"intercept_us": round(a1, 4), "slope_us_per_byte": round(b1, 6), "r2": round(r1, 6)},
        "P4": {"intercept_us": round(a4, 4), "slope_us_per_byte": round(b4, 6), "r2": round(r4, 6)},
        "breakeven_bytes": _threshold(a1, b1, a4, b4, 1.0),
        "maintainer_threshold_bytes": _threshold(a1, b1, a4, b4, GO_THRESHOLD_SPEEDUP),
    }

    out_path = REPO_ROOT / "native" / "results" / "envelope_remeasure.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_table(results)


def _print_table(results):
    print(f"{'frame':<14}{'path':<22}{'P50':>10}{'P95':>10}{'P99':>10}  (us)")
    for label, row in results["frames"].items():
        for path_name, stats in row.items():
            print(
                f"{label:<14}{path_name:<22}{stats['p50']:>10.3f}{stats['p95']:>10.3f}"
                f"{stats['p99']:>10.3f}"
            )
        if label in results["verdict"]:
            verdict = results["verdict"][label]
            print(
                f"  -> P50 加速 {verdict['speedup_p50']}x，"
                f"P99 变化 {verdict['p99_regression']:+.1%}，"
                f"判定 {'go' if verdict['go'] else 'no-go'}"
            )
    model = results["model"]
    print(
        f"\nP1 = {model['P1']['intercept_us']} + {model['P1']['slope_us_per_byte']}·F  (R2={model['P1']['r2']})"
    )
    print(
        f"P4 = {model['P4']['intercept_us']} + {model['P4']['slope_us_per_byte']}·F  (R2={model['P4']['r2']})"
    )
    print(f"盈亏平衡 F = {model['breakeven_bytes']}")
    print(f"S>=1.5 门槛 F = {model['maintainer_threshold_bytes']}")
    print("\n结果已写入 native/results/envelope_remeasure.json")


if __name__ == "__main__":
    main()
