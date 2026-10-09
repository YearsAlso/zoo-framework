# 已判废（变更 cleanup-aop-public-surface / issue #49）：本模块不再从 `core` / `core.aop`
# 包面导出；模块路径保留一个 minor 周期供迁移，下个 minor 连同 `workers.WorkerRegister`
# 一起删除。历史问题：它写入的 legacy 表不被 `Master` 的调度链（`WorkerRegistry`）读取，
# 故注册后从不被派发；键仍是裸类名；导入期即实例化。接通路径只有一条：
# `Master.register_worker(name, worker_class)`。
import warnings

from zoo_framework.workers import WorkerRegister

worker_register: WorkerRegister = WorkerRegister()

_DEPRECATION_TEXT = (
    "@worker does not hook into dispatch: it registers into the legacy WorkerRegister, "
    "which Master never reads, so registered instances are never dispatched. "
    "Use Master.register_worker(name, worker_class) instead; this module will be removed in the next minor version."
)


def worker(count: int = 1):
    """装饰器函数，用于注册指定数量的 worker 实例。

    .. deprecated:: 已判废（#49）；使用时发 ``DeprecationWarning``，见模块顶部说明。

    参数:
        count (int): 需要注册的 worker 实例数量，默认为 1。

    返回:
        function: 返回一个内部装饰器函数，用于处理被装饰的类。
    """

    def inner(cls):
        """内部装饰器函数，负责实际的 worker 注册逻辑。

        参数:
            cls (class): 被装饰的类，表示 worker 的类型。

        返回:
            class: 返回原始类，保持装饰器的透明性。
        """
        # 弃用信号在被装饰类定义的现场发出（stacklevel 穿透装饰器应用点）。
        warnings.warn(_DEPRECATION_TEXT, DeprecationWarning, stacklevel=3)
        # 如果只需要注册一个实例，则直接注册该类的实例
        if count == 1:
            worker_register.register(cls.__name__, cls())
            return cls

        # 如果需要注册多个实例，则为每个实例分配编号并分别注册
        for i in range(1, count + 1):
            instance = cls()
            instance.num = i
            worker_register.register(f"{cls.__name__}_{i}", instance)
        return cls

    return inner
