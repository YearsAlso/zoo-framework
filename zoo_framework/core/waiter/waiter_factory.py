from zoo_framework.constant import WorkerConstant

from .base_waiter import BaseWaiter
from .safe_waiter import SafeWaiter
from .simple_waiter import SimpleWaiter
from .stable_waiter import StableWaiter


class WaiterFactory:
    """调度器工厂：按运行策略名构造对应的调度器。"""

    _WAITERS: dict = {
        WorkerConstant.RUN_POLICY_SIMPLE: SimpleWaiter,
        WorkerConstant.RUN_POLICY_STABLE: StableWaiter,
        WorkerConstant.RUN_POLICY_SAFE: SafeWaiter,
    }

    @staticmethod
    def get_waiter(name=WorkerConstant.RUN_POLICY_SIMPLE) -> BaseWaiter:
        """按运行策略名构造调度器。

        无法识别的策略名会被明确拒绝，MUST NOT 静默返回默认策略——静默降级会让
        配置写错时表现出的行为与配置完全无关，且调用方无从察觉。

        Args:
            name: 运行策略名

        Returns:
            对应的调度器实例

        Raises:
            ValueError: 策略名无法识别
        """
        waiter_class = WaiterFactory._WAITERS.get(name)
        if waiter_class is None:
            raise ValueError(
                f"无法识别的运行策略 {name!r}；支持的策略为 {list(WaiterFactory._WAITERS)}"
            )
        return waiter_class()
