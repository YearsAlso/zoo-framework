"""真实 Rust 扩展（zoo_framework_native）的加载路径与等价性测试（tasks 3.4 / 3.3）.

门控：扩展未安装时整文件显式 skip（``pytest.importorskip``）——
CI / 干净环境没有原生扩展时这些用例不伪装通过也不误报失败。

覆盖：

- 加载路径：import → 契约握手（版本 / 能力 / 任务注册表）经真实适配器全链路
- 契约字段：扩展侧构造的 NativeTaskContract 与 spec 声明逐字段一致
- 等价性判据（tasks 3.3）：Rust 输出与纯 Python 参考实现在同批样本帧上逐值一致
- 三族错误：受控业务失败 / 输入拒绝经适配器映射进对应异常族

断言纪律：解析输出是构造后不再改写的新鲜 dict，按值比较即可（assertion-integrity
例外条款）。
"""

import importlib.util
import json
from pathlib import Path

import pytest

# 未安装扩展 → 本文件全部用例显式 skip
ext = pytest.importorskip("zoo_framework_native")

from zoo_framework.native import (  # noqa: E402
    CONTRACT_VERSION,
    NativeAdapter,
    NativeInvalidInput,
    NativeTaskFailed,
)

# 参考实现不在任何包内——按文件路径加载（等价性判据的另一侧）
_REFERENCE_PATH = Path(__file__).resolve().parents[1] / "native" / "reference" / "modbus_rtu.py"
_spec = importlib.util.spec_from_file_location("modbus_reference", _REFERENCE_PATH)
reference = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(reference)

TASK_NAME = "modbus_rtu.parse_response"


def _sample_frames():
    """确定性样本帧组：正常响应（1/8/125 寄存器）+ 异常帧."""
    frames = []
    frames.append(reference.build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34])))
    eight = bytes([0x11, 0x04, 0x10]) + bytes(
        b for i in range(8) for b in ((0xB0 + i) & 0xFF, 0x2E + i)
    )
    frames.append(reference.build_frame(eight))
    big = bytes([0x21, 0x03, 0xFA]) + bytes(i & 0xFF for i in range(250))
    frames.append(reference.build_frame(big))
    frames.append(reference.build_frame(bytes([0x01, 0x83, 0x02])))
    frames.append(reference.build_frame(bytes([0x02, 0x84, 0x03])))
    return frames


class TestExtensionHandshake:
    def test_raw_module_constants(self):
        """扩展三入口的原始返回值：版本 / 空能力清单 / 任务注册表."""
        assert ext.contract_version() == CONTRACT_VERSION
        assert tuple(ext.capabilities()) == ()
        registry = ext.tasks()
        assert set(registry) == {TASK_NAME}

    def test_task_contract_fields_match_spec(self):
        """扩展侧构造的契约是框架数据类实例且字段完整."""
        contract = ext.tasks()[TASK_NAME]
        assert type(contract).__name__ == "NativeTaskContract"
        assert contract.name == TASK_NAME
        assert contract.contract_version == CONTRACT_VERSION
        assert contract.input_format == "bytes"
        assert contract.max_input_bytes == 256
        assert contract.output_format == "json"
        assert contract.error_classes == ("NativeInvalidInput", "NativeTaskFailed")
        assert contract.capabilities == ()

    def test_adapter_full_handshake(self):
        """真实适配器对真扩展握手：版本一致、能力为空、任务已注册."""
        adapter = NativeAdapter()  # 默认模块名即本扩展
        adapter.ensure_ready()
        descriptor = adapter._descriptor
        assert descriptor.contract_version == CONTRACT_VERSION
        assert descriptor.capabilities == ()
        assert set(descriptor.tasks) == {TASK_NAME}
        assert adapter.contract(TASK_NAME).name == TASK_NAME


class TestExecutionEquivalence:
    def test_rust_output_equals_reference_on_samples(self):
        """同批样本帧：Rust（经适配器全链路）与参考实现逐值一致."""
        adapter = NativeAdapter()
        contract = adapter.contract(TASK_NAME)
        for frame in _sample_frames():
            expected = reference.parse_response(frame)
            raw = adapter.execute(TASK_NAME, frame)
            assert adapter.convert_output(raw, contract) == expected, (
                f"帧 {frame.hex()} 上 Rust 与参考实现不一致"
            )

    def test_corrupted_crc_maps_to_task_failed(self):
        """CRC 损坏（线上字节干扰）：扩展 → NativeTaskFailed，分类与参考一致."""
        adapter = NativeAdapter()
        frame = bytearray(reference.build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34])))
        frame[-1] ^= 0xFF
        with pytest.raises(NativeTaskFailed, match="CRC"):
            adapter.execute(TASK_NAME, bytes(frame))
        with pytest.raises(reference.ReferenceTaskFailed):
            reference.parse_response(bytes(frame))

    def test_unknown_function_code_maps_to_task_failed(self):
        adapter = NativeAdapter()
        frame = reference.build_frame(bytes([0x01, 0x10, 0x00]))
        with pytest.raises(NativeTaskFailed, match="0x10"):
            adapter.execute(TASK_NAME, frame)

    def test_structural_short_frame_maps_to_invalid_input(self):
        """长度 < 4：扩展 → NativeInvalidInput（执行前拒绝族）."""
        adapter = NativeAdapter()
        with pytest.raises(NativeInvalidInput):
            adapter.execute(TASK_NAME, b"\x01\x03\x00")

    def test_oversized_input_rejected_before_extension(self):
        """超出契约上限（256）：适配器执行前拒绝——扩展体从未被调用."""
        adapter = NativeAdapter()
        with pytest.raises(NativeInvalidInput, match="上限"):
            adapter.execute(TASK_NAME, bytes(257))

    def test_unregistered_task_name_rejected(self):
        adapter = NativeAdapter()
        with pytest.raises(NativeInvalidInput, match="未注册"):
            adapter.execute("nonexistent.task", b"\x01\x03\x00\x00")


# =============================================================================
# add-adaptive-scheduling tasks 4.1：DualArmWorker 收敛集成场景（真实扩展）
# =============================================================================


class TestDualArmWorkerConvergence:
    """声明双臂的 worker 混合执行 → 统计收敛并稳定选实测更快的一侧.

    场景（tasks 4.1）：大帧（250 字节载荷）原生臂明显更快；小帧（5 字节）
    Python 参考实现更省（原生边界往返吞掉原生收益）。两类各跑固定次数后，
    bandit 统计必须与实测均值同侧，且 ε=0 决策稳定选更快臂。

    统计隔离：每个用例自持 BanditPolicy 实例（不取进程单例），跨用例零残留。
    """

    MIXED_RUNS = 20

    def setup_method(self, monkeypatch=None):
        """打桩 native:enabled=true（构造期现查 config）+ adaptive:enabled=true.

        adaptive 开关在 ``_execute`` 里读的是已被 @params 冻结为字面值的类属性，
        直接 monkeypatch 该属性才生效（经 @params 重新解析是空操作）。
        """
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.params import AdaptiveParams

        self._monkeypatch = pytest.MonkeyPatch()
        self._monkeypatch.setattr(
            ParamsFactory, "config_params", {"native": {"enabled": True}}, raising=False
        )
        self._monkeypatch.setattr(AdaptiveParams, "ADAPTIVE_ENABLED", True, raising=False)

    def teardown_method(self):
        self._monkeypatch.undo()

    @staticmethod
    def _big_frame() -> bytes:
        return reference.build_frame(bytes([0x21, 0x03, 0xFA]) + bytes(i % 256 for i in range(250)))

    @staticmethod
    def _small_frame() -> bytes:
        return reference.build_frame(bytes([0x01, 0x03, 0x02, 0x12, 0x34]))

    def _start_policy(self, epsilon: float = 0.5):
        from zoo_framework.core.adaptive import BanditPolicy

        return BanditPolicy(epsilon=epsilon)

    @staticmethod
    def _faster_arm(snap: dict) -> str:
        """按臂均值判快侧（均值小 = 快）；无样本侧视为慢."""
        import math

        native_mean = snap["native"]["mean"] if snap["native"]["n"] else math.inf
        python_mean = snap["python"]["mean"] if snap["python"]["n"] else math.inf
        return "native" if native_mean <= python_mean else "python"

    def _run_both_arms(self, frame: bytes, policy, runs: int):
        """用同一个 DualArmWorker 混合跑两类帧的各 10 次，喂出两类统计.

        key = 类名（同名类共享统计，这正是逐类学习语义）；大帧 / 小帧分属
        两个 worker 子类，各得独立类目。
        """
        from zoo_framework.core.adaptive import ARM_NATIVE
        from zoo_framework.workers import DualArmWorker

        class BigFrameWorker(DualArmWorker):
            def __init__(self):
                super().__init__(
                    {"native_task_name": TASK_NAME, "input": self._big_frame()}, policy=policy
                )

            @staticmethod
            def _big_frame():
                return TestDualArmWorkerConvergence._big_frame()

            def _execute_python(self):
                return reference.parse_response(self._props["input"])

        class SmallFrameWorker(DualArmWorker):
            def __init__(self):
                super().__init__(
                    {"native_task_name": TASK_NAME, "input": self._small_frame()}, policy=policy
                )

            @staticmethod
            def _small_frame():
                return TestDualArmWorkerConvergence._small_frame()

            def _execute_python(self):
                return reference.parse_response(self._props["input"])

        big, small = BigFrameWorker(), SmallFrameWorker()
        for _ in range(runs):
            big._execute()
            small._execute()
        big_snap = policy.snapshot()["BigFrameWorker"]
        small_snap = policy.snapshot()["SmallFrameWorker"]
        # 两类都被结构喂到了 python 臂之外（等价前置：双臂输出一致由本文件已有用例保证）
        assert big_snap[ARM_NATIVE]["n"] > 0
        assert small_snap["python"]["n"] > 0
        return big_snap, small_snap

    def test_convergence_matches_measured_faster_arm(self):
        """大帧类收敛到更快臂（ε=0 决策与实测均值同侧）."""
        adapter = NativeAdapter()
        adapter.ensure_ready()
        policy = self._start_policy()
        big_snap, small_snap = self._run_both_arms(self._big_frame(), policy, self.MIXED_RUNS)

        # 稳态断言：类目臂 ε=0（纯利用）——决策的探索概率记在逐类目
        # EpsilonGreedy.epsilon 上（policy 级只是建档默认值，事后改无效）
        policy._classes["BigFrameWorker"].epsilon = 0
        policy._classes["SmallFrameWorker"].epsilon = 0
        assert policy.decide("BigFrameWorker") == self._faster_arm(big_snap)
        assert policy.decide("SmallFrameWorker") == self._faster_arm(small_snap)

    def test_steady_state_decision_stable(self):
        """从收敛统计出发，大帧类连续 50 次决策不抖动.

        ε-greedy 的探索概率记在逐类目的 ``EpsilonGreedy.epsilon`` 上（policy 级
        只作默认值），稳态纯利用要改类目臂的 epsilon。
        """
        adapter = NativeAdapter()
        adapter.ensure_ready()
        policy = self._start_policy()
        big_snap, _ = self._run_both_arms(self._big_frame(), policy, self.MIXED_RUNS)
        # 稳态：类目臂 ε=0（纯利用）
        greedy = policy._classes["BigFrameWorker"]
        greedy.epsilon = 0
        faster = self._faster_arm(big_snap)
        decisions = {policy.decide("BigFrameWorker") for _ in range(50)}
        assert len(decisions) == 1, f"稳态决策抖动: {decisions}"
        assert next(iter(decisions)) == faster

    def test_worker_result_contract_untouched(self):
        """双臂执行返回值与参考实现逐值等价：决策不影响输出语义."""
        adapter = NativeAdapter()
        adapter.ensure_ready()
        policy = self._start_policy()
        frame = self._big_frame()
        from zoo_framework.workers import DualArmWorker

        class BigFrameWorker(DualArmWorker):
            def __init__(self):
                super().__init__({"native_task_name": TASK_NAME, "input": frame}, policy=policy)

            def _execute_python(self):
                return reference.parse_response(frame)

        worker = BigFrameWorker()
        expected = reference.parse_response(frame)
        results = {json.dumps(worker._execute(), sort_keys=True) for _ in range(self.MIXED_RUNS)}
        assert results == {json.dumps(expected, sort_keys=True)}
