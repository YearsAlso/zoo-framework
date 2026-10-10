"""原生适配器：加载扩展、握手校验、转换输入输出、映射错误.

边界职责（design D2/D3）：

- **加载**：按模块名 import 扩展（首版默认 ``zoo_framework_native``），缺失 /
  版本不匹配 / 能力不满足 MUST 在执行**前**显式拒绝，MUST NOT 静默回退。
- **握手**：读扩展上报的 ``contract_version()`` 与 ``capabilities()``，与框架
  支持的契约版本和扩展声明比对。
- **转换**：边界处一次性把输入转成扩展约定的形态、完成后一次性转回；
  执行体内保持原生数据。
- **错误映射**：扩展的三族错误结构 → Python 侧三族异常（contract.py）。

适配器 MUST NOT 自行生成或丢弃 run_id/session_id——运行标识由结算点
（``WorkerDispatchCore.settle``）按登记项盖章，适配器不碰身份字段。
"""

import importlib
import json
import threading

from .contract import (
    CAPABILITY_INTERNAL_PARALLEL,
    CAPABILITY_ZERO_COPY,
    CONTRACT_VERSION,
    NativeContractDescriptor,
    NativeInvalidInput,
    NativePanic,
    NativeTaskContract,
    NativeTaskError,
)

#: 首版默认的扩展模块名（native/ 子目录构建出的 Python 扩展包）
_DEFAULT_EXTENSION_MODULE = "zoo_framework_native"

#: 首版显式声明不支持的能力：请求即拒绝，不给「可能行」的假象
_UNSUPPORTED_CAPABILITIES = frozenset({CAPABILITY_INTERNAL_PARALLEL, CAPABILITY_ZERO_COPY})

# 适配器进程级单例（get_native_adapter / reset_native_adapter）。
# 首版与既有注册表同形态：模块级全局 + 显式 reset；收编进容器由
# process_state 的登记扫描负责（不登记会被 tests/test_process_state_registry.py 拦下）。
_adapter_singleton: "NativeAdapter | None" = None
_adapter_lock = threading.RLock()


class NativeAdapter:
    """原生扩展适配器.

    Attributes:
        extension_module: 扩展模块名
        _descriptor: 握手成功后的契约描述；None 表示尚未成功握手
    """

    def __init__(self, extension_module: str = _DEFAULT_EXTENSION_MODULE):
        self.extension_module = extension_module
        self._descriptor: NativeContractDescriptor | None = None

    # ---------------------------------------------------------------- 握手

    def ensure_ready(self) -> None:
        """确保扩展已加载且握手通过.

        幂等：成功握手后重复调用是空操作（扩展 import 本身有模块缓存）。

        Raises:
            NativeInvalidInput: 扩展缺失、契约版本不匹配或能力不满足
        """
        with _adapter_lock:
            if self._descriptor is not None:
                return
            try:
                module = importlib.import_module(self.extension_module)
            except ImportError as e:
                raise NativeInvalidInput(
                    f"原生扩展模块 {self.extension_module!r} 未安装；"
                    "原生任务不可用。请显式选择安装原生扩展或使用普通 Worker"
                ) from e
            self._descriptor = self._handshake(module)

    def _handshake(self, module) -> NativeContractDescriptor:
        """与扩展模块握手：版本比对 + 能力比对 + 任务契约描述读取.

        Raises:
            NativeInvalidInput: 契约版本不匹配或声明了不支持的能力
        """
        try:
            version = int(module.contract_version())
        except Exception as e:
            raise NativeInvalidInput(
                f"原生扩展 {self.extension_module!r} 未实现 contract_version()；不兼容"
            ) from e

        if version != CONTRACT_VERSION:
            raise NativeInvalidInput(
                f"契约版本不匹配：扩展上报 {version}，框架支持 {CONTRACT_VERSION}"
            )

        try:
            raw_capabilities = tuple(module.capabilities())
        except Exception as e:
            raise NativeInvalidInput(
                f"原生扩展 {self.extension_module!r} 未实现 capabilities()；不兼容"
            ) from e

        unsupported = sorted(set(raw_capabilities) & _UNSUPPORTED_CAPABILITIES)
        if unsupported:
            raise NativeInvalidInput(
                f"原生扩展声明了本版不支持的能力: {unsupported}；明确拒绝，不静默降级"
            )

        tasks: dict[str, NativeTaskContract] = dict(module.tasks().items())

        return NativeContractDescriptor(
            contract_version=version,
            capabilities=tuple(raw_capabilities),
            tasks=tasks,
        )

    def contract(self, task_name: str) -> NativeTaskContract:
        """读取某个任务的契约描述.

        Raises:
            NativeInvalidInput: 扩展未就绪、或未注册该任务名
        """
        self.ensure_ready()
        assert self._descriptor is not None  # ensure_ready 后必非 None
        contract = self._descriptor.tasks.get(task_name)
        if contract is None:
            raise NativeInvalidInput(
                f"原生扩展未注册任务 {task_name!r}；已注册: {sorted(self._descriptor.tasks)}"
            )
        return contract

    # ---------------------------------------------------------------- 执行

    def execute(self, task_name: str, payload: bytes) -> bytes:
        """执行一个原生任务：边界转换 → 委托扩展 → 输出转换.

        Args:
            task_name: 任务名；MUST 已在扩展侧注册
            payload: 输入字节串；扩展执行期间释放 GIL / 脱离解释器

        Returns:
            原生输出转换回 Python 侧的字节串

        Raises:
            NativeInvalidInput: 任务未注册 / 输入超出契约声明
            NativeTaskFailed: 扩展上报的受控业务失败
            NativePanic: 扩展执行体 unwind panic（注意并非进程隔离）
        """
        contract = self.contract(task_name)
        if contract.max_input_bytes is not None and len(payload) > contract.max_input_bytes:
            raise NativeInvalidInput(
                f"输入 {len(payload)} 字节超出任务 {task_name!r} 契约上限 "
                f"{contract.max_input_bytes}"
            )

        self.ensure_ready()
        assert self._descriptor is not None
        module = importlib.import_module(self.extension_module)

        try:
            output = module.execute(task_name, payload)
        except NativeTaskError:
            # 扩展侧已映射好的三族错误直接透传，MUST NOT 再包一层 panic
            raise
        except Exception as e:
            # 扩展层抛的非三族异常视为 panic 兜底（同进程边界，design D3）
            raise NativePanic(f"原生扩展执行异常: {e}") from e

        # 扩展侧类型是动态的（Any）：输出转回字节形态是适配器边界承诺
        return bytes(output)

    # ---------------------------------------------------------------- 输入转换

    def prepare_input(self, raw_input, contract: NativeTaskContract) -> bytes:
        """把 Python 侧输入转换为契约约定的字节形态.

        首版支持 bytes（直传不复制）与 JSON 可序列化对象（经 json.dumps）。
        边界处一次性转换，执行体内保持原生数据（design D2）。

        Raises:
            NativeInvalidInput: 输入格式不是契约声明支持的形态
        """
        if contract.input_format == "bytes":
            if isinstance(raw_input, bytes):
                return raw_input
            raise NativeInvalidInput(
                f"任务 {contract.name!r} 要求 bytes 输入，实际 {type(raw_input)}"
            )
        if contract.input_format == "json":
            try:
                return json.dumps(raw_input).encode("utf-8")
            except (TypeError, ValueError) as e:
                raise NativeInvalidInput(f"输入无法 JSON 序列化: {e}") from e
        raise NativeInvalidInput(
            f"契约 {contract.name!r} 声明了不支持的输入格式 {contract.input_format!r}"
        )

    # ---------------------------------------------------------------- 输出转换

    def convert_output(self, raw_output: bytes, contract: NativeTaskContract):
        """把原生输出（字节）按契约格式转换回 Python 侧值.

        Raises:
            NativeInvalidInput: 输出无法按契约格式解码
        """
        if contract.output_format == "bytes":
            return raw_output
        if contract.output_format == "json":
            try:
                return json.loads(raw_output.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as e:
                raise NativeInvalidInput(f"输出无法按 JSON 解码: {e}") from e
        raise NativeInvalidInput(
            f"契约 {contract.name!r} 声明了不支持的输出格式 {contract.output_format!r}"
        )


def get_native_adapter() -> NativeAdapter:
    """进程级适配器单例的访问入口.

    Returns:
        已有的单例或新实例（首次访问时创建）
    """
    global _adapter_singleton
    with _adapter_lock:
        if _adapter_singleton is None:
            _adapter_singleton = NativeAdapter()
        return _adapter_singleton


def reset_native_adapter() -> None:
    """复位进程级适配器单例（供测试与新扩展热加载使用）."""
    global _adapter_singleton
    with _adapter_lock:
        _adapter_singleton = None
