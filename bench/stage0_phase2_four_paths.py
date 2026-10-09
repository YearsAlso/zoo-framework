"""stage-0 phase-2：Modbus RTU 帧解析的四链路对照测量（add-native-task-execution tasks 1.3）.

四条链路（同一次运行内完成全部测量，遵守 bench/README 读数纪律）：

- P1 纯 Python 参考实现：``native/reference/modbus_rtu.py``（位移 CRC + 手工切片）
- P2 现有原生库形态：C 原语（``int.from_bytes``）+ 查表 CRC 循环——pymodbus 类
  既有实现的典型形状（stdlib 没有 Modbus CRC 的 C 实现，此路径如实代表可达形态）
- P3 Rust 直调：``zoo_framework_native.execute`` + ``json.loads``（交付等价产物）
- P4 Zoo+Rust 适配链路：``NativeAdapter.execute`` + ``convert_output``（部署形态，
  握手为进程内一次性成本，不进稳态测量）

附带记录 rust_raw（不含 json.loads 的裸 execute）用于读出输出转换占比，不参与判定。

判定门槛（维护者 2026-10-09 确认，写入 native/DECISION.md）：
端到端 P50 加速 >= 1.5x 且 P99 劣化 <= 5%（对照 P1）。

结果落盘：native/results/stage0_phase2_four_paths.json
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
GO_THRESHOLD_SPEEDUP = 1.5
GO_THRESHOLD_P99_REGRESSION = 0.05
TASK_NAME = "modbus_rtu.parse_response"


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
    """线性插值百分位（样本已升序）."""
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    rank = (len(sorted_samples) - 1) * pct / 100.0
    low = int(rank)
    high = min(low + 1, len(sorted_samples) - 1)
    frac = rank - low
    return sorted_samples[low] * (1 - frac) + sorted_samples[high] * frac


def _measure(fn, frame):
    """同一运行内：预热分离后连测 N 轮，返回逐轮成本（µs）."""
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


def main():
    reference = _load_reference()
    parse_c = _make_c_primitive_parser()

    # 样本帧（与等价性测试同一构造方式）
    frames = {
        "1reg(7B)": reference.build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34])),
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

        adapter = NativeAdapter()  # 握手在测量前完成（进程内一次性成本）

    # 等价性前置检查：各链路对同帧必须产出相同 dict，测量才有效
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
        # 契约查询留在链内：NativeTaskWorker._execute 每次执行都查一次，这是部署形态成本
        paths["P4_zoo_adapter"] = lambda frame: adapter.convert_output(
            adapter.execute(TASK_NAME, frame), adapter.contract(TASK_NAME)
        )
        paths["supp_rust_raw"] = lambda frame: ext.execute(TASK_NAME, frame)

    results = {"meta": _meta(), "frames": {}, "verdict": {}}
    for label, frame in frames.items():
        row = {}
        for path_name, fn in paths.items():
            row[path_name] = _measure(fn, frame)
        results["frames"][label] = row

        # 判定：P4（部署形态）对照 P1（纯 Python）
        if ext is not None:
            p1, p4 = row["P1_python_reference"], row["P4_zoo_adapter"]
            speedup = round(p1["p50"] / p4["p50"], 2)
            p99_regression = round((p4["p99"] / p1["p99"]) - 1.0, 4)
            go = speedup >= GO_THRESHOLD_SPEEDUP and p99_regression <= GO_THRESHOLD_P99_REGRESSION
            results["verdict"][label] = {
                "speedup_p50": speedup,
                "p99_regression": p99_regression,
                "go": go,
            }

    out_path = REPO_ROOT / "native" / "results" / "stage0_phase2_four_paths.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    _print_table(results)


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
    print("\n结果已写入 native/results/stage0_phase2_four_paths.json")


if __name__ == "__main__":
    main()
