"""调度器工厂：按**调度模型名**构造调度器.

历史沿革：本工厂曾按"运行策略名"（simple / stable / safe）选择三个近乎相同的
调度器子类。那三个子类的唯一差异是"池尺寸不足时怎么办"（扩容 / 排队 / 拒绝），
与并发原语、时间语义都无关——因此差异已改由 ``ThreadPoolModel`` 的背压策略参数
承载，工厂改为按模型名键控，旧策略名 MUST 被明确拒绝。
"""

from zoo_framework.constant import WaiterConstant

from .base_waiter import BaseWaiter


class WaiterFactory:
    """调度器工厂：按调度模型名构造对应的调度器."""

    @staticmethod
    def get_waiter(name: str | None = None) -> BaseWaiter:
        """按调度模型名构造调度器.

        无法识别的模型名会被明确拒绝并列出可选模型，MUST NOT 静默返回默认模型——
        静默降级会让配置写错时表现出的行为与配置完全无关，且调用方无从察觉。

        Args:
            name: 调度模型名（``worker:mode`` 的取值）；None 表示由配置推导

        Returns:
            已装配对应模型的调度器实例

        Raises:
            ValueError: 模型名无法识别
        """
        if name is not None and name not in WaiterConstant.IMPLEMENTED_WORKER_MODES:
            raise ValueError(
                f"无法识别的调度模型 {name!r}；可选的模型为 "
                f"{list(WaiterConstant.IMPLEMENTED_WORKER_MODES)}"
            )
        return BaseWaiter(model_name=name)
