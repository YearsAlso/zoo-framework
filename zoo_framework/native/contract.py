"""原生任务执行契约：语言无关的任务描述与受控错误分类.

内核（契约接口与 :class:`~zoo_framework.native.worker.NativeTaskWorker`）MUST NOT
直接依赖 PyO3 / Tokio / 具体业务任务——本模块只承载**数据**与**异常**，原生绑定的
类型与转换全部在外围适配器（``zoo_framework.native.adapter``）。

契约是数据而非多态：原生扩展侧回传的是常量（契约版本 + 能力清单），无子类派发
需求，故用数据类而非抽象基类承载。
"""

from dataclasses import dataclass, field

#: 当前框架支持的执行契约版本。扩展侧经 ``contract_version()`` 上报，
#: 主版本不匹配即拒绝执行——语义不兼容 MUST NOT 靠运气兼容。
CONTRACT_VERSION = 1

#: 能力名：原生任务在执行体内部自行并行。首版为 False——若后续确需，
#: 先统一 CPU 并发预算，避免「每个 Python 线程再起一组原生线程」。
CAPABILITY_INTERNAL_PARALLEL = "internal_parallel"

#: 能力名：输入输出走零拷贝/内存映射缓冲区。默认不承诺（proposal 明确），
#: 仅当复制成本被证明显著时再评估，且必须同时定义持有者与释放时机。
CAPABILITY_ZERO_COPY = "zero_copy"


@dataclass(frozen=True)
class NativeTaskContract:
    """一个原生任务的语言无关描述.

    Attributes:
        name: 任务名；扩展按任务名注册，不能把任意 Python callable 当作原生任务
        contract_version: 任务实现所依据的执行契约版本
        input_format: 输入格式标识（如 ``"bytes"`` / ``"json"``）
        max_input_bytes: 输入最大字节数；超出即执行前拒绝（None 表示不设上限）
        output_format: 输出格式标识
        error_classes: 任务实现声明的受控错误族（错误三族的子集）
        capabilities: 任务实现声明支持的能力名集合
    """

    name: str
    contract_version: int
    input_format: str
    max_input_bytes: int | None
    output_format: str
    error_classes: tuple[str, ...] = ()
    capabilities: tuple[str, ...] = ()


@dataclass(frozen=True)
class NativeContractDescriptor:
    """原生扩展的契约握手信息（由适配器从扩展模块读取）.

    Attributes:
        contract_version: 扩展实现所依据的执行契约版本
        capabilities: 扩展整体声明支持的能力名集合
        tasks: 扩展注册的任务名 -> 契约描述
    """

    contract_version: int
    capabilities: tuple[str, ...]
    tasks: dict[str, NativeTaskContract] = field(default_factory=dict)


class NativeTaskError(Exception):
    """原生任务错误的公共基类.

    三族错误从本基类派生，便于调用方按「是否原生侧错误」统一捕获；
    各族语义见对应子类 docstring。
    """


class NativeInvalidInput(NativeTaskError):
    """输入拒绝：输入格式/尺寸不满足契约，发生在执行开始**之前**.

    与 :class:`NativeTaskFailed` 的区别是失败阶段：本类意味着原生执行体
    根本没有开始跑，输入问题在边界检查即被拦截。
    """


class NativeTaskFailed(NativeTaskError):
    """任务失败：原生执行体开始运行后的受控业务失败.

    映射自扩展返回的受控错误结构；不是 panic，也不是输入拒绝。
    """


class NativePanic(NativeTaskError):
    """Rust 侧 panic（unwind 在任务边界被兜底）.

    明确边界：``catch_unwind`` **不是进程隔离**——abort / 段错误 / OOM
    仍然打穿进程。本类只覆盖可被边界兜住的 unwind panic。
    """
