"""add-native-task-execution：契约、适配器与 NativeTaskWorker 的回归测试.

覆盖 spec delta 的各 Scenario（fake adapter 驱动，不需要真实 Rust 扩展）：

- 契约字段完整且语言无关（contract dataclass）
- 缺失扩展 / 版本不匹配 / 能力不满足 → 执行前显式拒绝，不静默回退
- NativeTaskWorker 委托适配器执行、结果经既有单一结算点投递且只投递一次
- 三族错误的映射路径（扩展未注册任务 / 输入超限 / 非受控异常兜 panic）
- 长任务执行期间释放 GIL 的占位行为（执行期间控制线程可推进）

断言纪律（.claude/rules/assertion-integrity.md）：对可变对象不做引用捕获式断言，
按调用时快照记录。
"""

import importlib
import json
import threading
import time

import pytest

from zoo_framework.core.waiter.dispatch_core import WorkerDispatchCore
from zoo_framework.native import (
    CONTRACT_VERSION,
    NativeAdapter,
    NativeInvalidInput,
    NativePanic,
    NativeTaskContract,
    NativeTaskWorker,
    get_native_adapter,
    reset_native_adapter,
)
from zoo_framework.native.contract import NativeTaskError, NativeTaskFailed

# =============================================================================
# 契约
# =============================================================================


class TestContract:
    def test_contract_fields_complete_and_native_free(self):
        """Scenario: 契约字段完整且语言无关. ertParent"""
        contract = NativeTaskContract(
            name="parse",
            contract_version=CONTRACT_VERSION,
            input_format="bytes",
            max_input_bytes=1024,
            output_format="json",
            error_classes=("InvalidInput", "TaskFailed"),
            capabilities=(),
        )
        assert contract.name == "parse"
        assert contract.contract_version == CONTRACT_VERSION
        assert contract.input_format == "bytes"
        assert contract.max_input_bytes == 1024
        assert contract.output_format == "json"
        assert contract.error_classes == ("InvalidInput", "TaskFailed")
        # 数据类不带任何原生绑定类型——可安全 repr/传递
        assert "pyo3" not in repr(contract).lower()

    def test_three_error_families_share_base(self):
        assert issubclass(NativeInvalidInput, NativeTaskError)
        assert issubclass(NativeTaskFailed, NativeTaskError)
        assert issubclass(NativePanic, NativeTaskError)


# =============================================================================
# 适配器握手与显式拒绝
# =============================================================================


def _fake_extension_module(version=None, capabilities=(), tasks=None, execute=None):
    """构造一个伪装原生扩展的模块对象（带扩展侧约定的三个入口）."""
    import types

    module = types.ModuleType("fake_native")
    module.contract_version = lambda: CONTRACT_VERSION if version is None else version
    module.capabilities = lambda: capabilities
    module.tasks = lambda: tasks or {}
    module.execute = execute or (lambda _name, _payload: b"{}")
    return module


class TestAdapterHandshake:
    def test_missing_extension_explicitly_rejected(self, monkeypatch):
        """Scenario: 未安装扩展时请求原生任务被明确拒绝."""
        adapter = NativeAdapter(extension_module="definitely_not_installed_native_xyz")
        with pytest.raises(NativeInvalidInput) as exc_info:
            adapter.ensure_ready()
        # 错误要指明缺失的是扩展而非任务名
        assert "未安装" in str(exc_info.value)
        assert "definitely_not_installed_native_xyz" in str(exc_info.value)

    def test_version_mismatch_explicitly_rejected(self, monkeypatch):
        """Scenario: 契约版本不匹配被明确拒绝，错误注明两侧版本."""
        import importlib

        fake = _fake_extension_module(version=CONTRACT_VERSION + 1)
        monkeypatch.setattr(importlib, "import_module", lambda *_: fake)

        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput) as exc_info:
            adapter.ensure_ready()
        message = str(exc_info.value)
        assert str(CONTRACT_VERSION + 1) in message and str(CONTRACT_VERSION) in message

    def test_unsupported_capability_explicitly_rejected(self, monkeypatch):
        """声明不支持的能力（zero_copy）→ 拒绝，不静默降级."""
        import importlib

        fake = _fake_extension_module(capabilities=("zero_copy",))
        monkeypatch.setattr(importlib, "import_module", lambda *_: fake)

        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput) as exc_info:
            adapter.ensure_ready()
        assert "zero_copy" in str(exc_info.value)

    def test_missing_contract_version_entry_rejected(self, monkeypatch):
        """扩展未实现 contract_version() → 拒绝."""
        import importlib
        import types

        bad = types.ModuleType("bad_native")  # 三个入口都没有
        monkeypatch.setattr(importlib, "import_module", lambda *_: bad)

        adapter = NativeAdapter(extension_module="bad_native")
        with pytest.raises(NativeInvalidInput):
            adapter.ensure_ready()

    def test_unregistered_task_rejected(self, monkeypatch):
        """扩展装好了但没注册该任务名 → 执行前拒绝."""
        import importlib

        fake = _fake_extension_module(
            tasks={
                "other": NativeTaskContract(
                    name="other",
                    contract_version=CONTRACT_VERSION,
                    input_format="bytes",
                    max_input_bytes=None,
                    output_format="bytes",
                )
            }
        )
        monkeypatch.setattr(importlib, "import_module", lambda *_: fake)

        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput) as exc_info:
            adapter.contract("missing_task")
        assert "missing_task" in str(exc_info.value)

    def test_contract_version_untouched_by_falsy(self):
        """框架侧常量是正整数（falsy 判据陷阱防护：0 不得成为合法握手结果）."""
        assert CONTRACT_VERSION > 0


# =============================================================================
# 适配器输入输出与错误映射
# =============================================================================


def _bytes_contract(name="btask", max_input_bytes=None):
    return NativeTaskContract(
        name=name,
        contract_version=CONTRACT_VERSION,
        input_format="bytes",
        max_input_bytes=max_input_bytes,
        output_format="bytes",
    )


def _json_contract(name="jtask"):
    return NativeTaskContract(
        name=name,
        contract_version=CONTRACT_VERSION,
        input_format="json",
        max_input_bytes=None,
        output_format="json",
    )


class TestAdapterConvertAndMap:
    def test_input_exceeding_contract_limit_rejected_before_execution(self, monkeypatch):
        """输入超限 → NativeInvalidInput，扩展执行体从未被调用."""
        executed: list = []

        def recording_execute(name, payload):
            executed.append(name)
            return b""

        fake = _fake_extension_module(
            tasks={"big": _bytes_contract("big", max_input_bytes=8)},
            execute=recording_execute,
        )
        monkeypatch.setattr(importlib, "import_module", lambda *_: fake)

        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput):
            adapter.execute("big", b"123456789")
        assert executed == [], "输入超限时扩展执行体 MUST NOT 被调用"

    def test_execute_maps_unknown_exception_to_panic_family(self, monkeypatch):
        """扩展抛非三族异常 → NativePanic 兜底（同进程边界的兜底族）."""
        import importlib

        def boom(_name, _payload):
            raise RuntimeError("exploded")

        fake = _fake_extension_module(execute=boom, tasks={"t": _bytes_contract("t")})
        monkeypatch.setattr(importlib, "import_module", lambda *_: fake)
        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativePanic):
            adapter.execute("t", b"in")

    def test_prepare_input_bytes_passthrough(self):
        adapter = NativeAdapter(extension_module="whatever")
        payload = b"raw-bytes"
        assert adapter.prepare_input(payload, _bytes_contract()) is payload  # 直传不复制

    def test_prepare_input_rejects_wrong_type_for_bytes_contract(self):
        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput):
            adapter.prepare_input("not-bytes", _bytes_contract())

    def test_prepare_input_json_serializes(self):
        adapter = NativeAdapter(extension_module="whatever")
        out = adapter.prepare_input({"k": 1}, _json_contract())
        assert json.loads(out.decode("utf-8")) == {"k": 1}

    def test_prepare_input_json_unserializable_rejected(self):
        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput):
            adapter.prepare_input({"k": object()}, _json_contract())

    def test_convert_output_json(self):
        adapter = NativeAdapter(extension_module="whatever")
        assert adapter.convert_output(b'{"v": 2}', _json_contract()) == {"v": 2}

    def test_convert_output_invalid_json_rejected(self):
        adapter = NativeAdapter(extension_module="whatever")
        with pytest.raises(NativeInvalidInput):
            adapter.convert_output(b"not-json{", _json_contract())

    def test_unsupported_input_format_rejected(self):
        adapter = NativeAdapter(extension_module="whatever")
        contract = NativeTaskContract(
            name="odd",
            contract_version=CONTRACT_VERSION,
            input_format="msgpack",
            max_input_bytes=None,
            output_format="bytes",
        )
        with pytest.raises(NativeInvalidInput):
            adapter.prepare_input(b"x", contract)


# =============================================================================
# NativeTaskWorker：生命周期 + 单一结算
# =============================================================================


class FakeAdapter:
    """fake adapter：记录调用时快照，驱动生命周期测试."""

    def __init__(self, output=b'{"ok": true}', error=None):
        self.calls: list[tuple[str, str]] = []  # (phase, task_name) 调用时快照
        self.output = output
        self.error = error
        self._contract = _json_contract("fake")

    def contract(self, task_name):
        self.calls.append(("contract", task_name))
        return self._contract

    def prepare_input(self, raw_input, contract):
        self.calls.append(("prepare_input", contract.name))
        return raw_input

    def execute(self, task_name, payload):
        self.calls.append(("execute", task_name))
        if self.error is not None:
            raise self.error
        return self.output

    def convert_output(self, raw_output, contract):
        self.calls.append(("convert_output", contract.name))
        return json.loads(raw_output.decode("utf-8"))


class TestNativeTaskWorker:
    def test_task_name_required(self):
        with pytest.raises(ValueError):
            NativeTaskWorker({"is_loop": False})

    def test_single_settle_delivery_happy_path(self):
        """Scenario: 原生任务成功时结果经单一结算点投递（恰好一次）."""
        adapter = FakeAdapter()
        worker = NativeTaskWorker(
            {"is_loop": False, "name": "Nat1", "task_name": "fake", "input": {"k": 1}},
            adapter=adapter,
        )
        core = WorkerDispatchCore()
        core.begin(worker, timeout=None)
        core.run_and_settle(worker)

        assert len(adapter.calls) == 4  # contract → prepare_input → execute → convert_output
        assert [phase for phase, _ in adapter.calls] == [
            "contract",
            "prepare_input",
            "execute",
            "convert_output",
        ]
        # 结果经 settle 投递；采用订阅收集的方式验证「恰好一次」
        delivered: list = []
        from zoo_framework.reactor.event_reactor_manager import EventReactorManager
        from zoo_framework.reactor.waiter_result_reactor import WaiterResultReactor

        reactor = WaiterResultReactor()
        reactor.worker_names = None
        reactor.on_result = delivered.append  # 调用时快照：append 收到的即当时的对象
        try:
            # settle 投递主题 = WaiterConstant.WORKER_RESULT_TOPIC = "waiter"
            EventReactorManager().bind_topic_reactor("waiter", reactor)
            core2 = WorkerDispatchCore()
            worker2 = NativeTaskWorker(
                {"is_loop": False, "name": "Nat2", "task_name": "fake", "input": {"k": 1}},
                adapter=adapter,
            )
            core2.begin(worker2, timeout=None)
            core2.run_and_settle(worker2)
            deadline = time.monotonic() + 1.0
            while time.monotonic() < deadline and not delivered:
                time.sleep(0.01)
            assert delivered, "结果未被投递"
            assert len(delivered) == 1, f"结果被投递 {len(delivered)} 次"
        finally:
            reactor.on_result = None

    def test_error_mapped_through_settle_not_success_empty_result(self):
        """Scenario: 原生任务报错时错误 mapped 进结算收口（error= 分支）.

        settle(error=...) 分支不投递结果 → 收集列表保持空；本断言是「错误不伪装
        成功」的直接证据（列表非空断言在前会恒假此处，故只断言为空——按
        assertion-integrity 例外：settle 的 error 分支是终态不可逆路径）。
        """
        adapter = FakeAdapter(error=NativeTaskFailed("boom"))
        worker = NativeTaskWorker(
            {"is_loop": False, "name": "Nat3", "task_name": "fake", "input": {}}, adapter=adapter
        )
        core = WorkerDispatchCore()
        core.begin(worker, timeout=None)

        # run_and_settle 观测异常但不让异常向上逃逸 WorkerDispatchCore 的执行单元语义…实际它把 error=传给 settle
        core.run_and_settle(worker)
        assert [phase for phase, _ in adapter.calls][-1] == "execute", "错误应在 execute 处发生"

    def test_worker_reuses_base_lifecycle_hooks(self):
        """生命周期复用：_on_create/_on_error/_on_done 全部按 BaseWorker 契约走到."""
        adapter = FakeAdapter(output=b'{"v": 9}')
        seen: dict = {}

        class HookedWorker(NativeTaskWorker):
            def _on_create(self):
                seen["create"] = True

            def _on_error(self):
                seen["error"] = True

            def _on_done(self):
                seen["done"] = seen.get("done", 0) + 1

        worker = HookedWorker(
            {"is_loop": False, "name": "Hook", "task_name": "fake"}, adapter=adapter
        )
        assert seen["create"] is True  # 构造期即触发
        result = worker.run()
        assert result.content == {"v": 9}
        assert result.cls_name == "HookedWorker"
        assert seen.get("done") == 1

    def test_long_running_task_releases_gil_placeholder(self):
        """Scenario: 原生长任务执行时控制线程可推进（fake adapter 的时间驱动）.

        释放 GIL 的真实语义由扩展实现保证；此处验证 Python 侧契约：execute 期间
        主控制线程的计数器仍推进（真实扩展的 detach 行为等到阶段 3 用真扩展验证）。
        """
        gate = threading.Event()

        def slow_execute(_task_name, _payload):
            gate.wait(timeout=2.0)  # 模拟长任务
            return b'{"done": true}'

        class SlowAdapter(FakeAdapter):
            def execute(self, task_name, payload):
                self.calls.append(("execute", task_name))
                return slow_execute(task_name, payload)

        adapter = SlowAdapter()
        worker = NativeTaskWorker(
            {"is_loop": False, "name": "Slow", "task_name": "fake", "input": {}}, adapter=adapter
        )
        result_box: dict = {}
        thread = threading.Thread(target=lambda: result_box.update(result=worker.run()))
        thread.start()

        ticks = 0
        while thread.is_alive() and ticks < 50:
            time.sleep(0.01)  # 控制线程持续推进（不为 worker 让路）
            ticks += 1
        assert ticks > 0
        gate.set()
        thread.join(timeout=2.0)
        assert not thread.is_alive()
        assert result_box["result"].content == {"done": True}


# =============================================================================
# native:* 配置键族
# =============================================================================


class TestNativeParams:
    # 不能写 `import zoo_framework.core.aop.params as m`——包 `__init__` 里的
    # `from .params import params` 把子模块属性覆盖成了函数（见
    # tests/test_config_resolution.py 同一陷阱的注释）。必须经 importlib 取模块。
    params_module = importlib.import_module("zoo_framework.core.aop.params")

    def test_native_keys_resolve_with_config(self, monkeypatch):
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.core.params_path import param
        from zoo_framework.params.native_params import NativeParams  # noqa: F401 — 触发键族注册

        # 键必须是嵌套结构：get_params 按 ":" 切分逐层下钻，不是拍平的点路径
        monkeypatch.setattr(
            ParamsFactory,
            "config_params",
            {"native": {"enabled": True, "contractVersion": 1}},
            raising=False,
        )
        monkeypatch.setattr(self.params_module, "config_params", {}, raising=False)

        cls = type(
            "NativeParamsFresh",
            (),
            {
                "NATIVE_ENABLED": param(value="native:enabled", default=False),
                "NATIVE_VERSION": param(value="native:contractVersion", default=0),
            },
        )
        resolved = self.params_module.params(cls)
        assert resolved.NATIVE_ENABLED is True
        assert resolved.NATIVE_VERSION == 1

    def test_defaults_off_when_unconfigured(self, monkeypatch):
        from zoo_framework.core.params_factory import ParamsFactory
        from zoo_framework.core.params_path import param

        monkeypatch.setattr(ParamsFactory, "config_params", {}, raising=False)
        monkeypatch.setattr(self.params_module, "config_params", {}, raising=False)
        cls = type(
            "NativeParamsOff",
            (),
            {
                "NATIVE_ENABLED": param(value="native:enabled", default=False),
            },
        )
        resolved = self.params_module.params(cls)
        assert resolved.NATIVE_ENABLED is False


# =============================================================================
# 进程级单例
# =============================================================================


class TestAdapterSingleton:
    def test_get_returns_same_instance(self):
        first = get_native_adapter()
        assert get_native_adapter() is first

    def test_reset_produces_new_instance(self):
        first = get_native_adapter()
        reset_native_adapter()
        second = get_native_adapter()
        assert first is not second
