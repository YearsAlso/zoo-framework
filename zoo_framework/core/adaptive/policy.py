"""逐 Worker 类的决策入口（进程级单例）.

形状（design D2）：key = **Worker 类名**——同名 ``DualArmWorker`` 的多实例
共享统计，这正是「逐类学习」的语义；``BaseWorker.name`` 的 ``_1``/``_2``
实例后缀只进日志名，不进统计 key。

fail-open（spec「异常退路」）：本类自身不抛错给调用方——决策层任何异常由
调用方（``DualArmWorker._execute``）按静态默认臂兜底；本模块提供的入口
方法的异常语义留给调用方包装。

关闭语义（spec「关闭时零影响」）：开关判定在调用方；本单例只在已启用时被
触达，自身不读配置不取全局锁。
"""

import threading

from zoo_framework.core import process_state
from zoo_framework.core.params_factory import ParamsFactory

from .bandit import ARM_NATIVE, ARM_PYTHON, EpsilonGreedy

# 进程级单例（get_bandit_policy / reset_bandit_policy）——与 native adapter 同形态
_policy_singleton: "BanditPolicy | None" = None
_policy_lock = threading.RLock()

#: CPU 臂的合法集（供调用方确认决策结果属于本决策空间）
KNOWN_ARMS = (ARM_NATIVE, ARM_PYTHON)


class BanditPolicy:
    """逐 Worker 类的 ε-greedy 决策入口.

    Attributes:
        epsilon: 全局探索率（构造时读 ``adaptive:exploration``；同名 Worker 类
            可经 ``adaptive:explorationOverride`` 键族覆盖）
    """

    def __init__(self, epsilon: float | None = None):
        """Args:
        epsilon: 显式探索率（测试注入用）；None 读配置
        """
        # lazy import（同 dual_arm_worker 文件头的原因）：params 包不能在
        # core 引导链上被模块级导入
        from zoo_framework.params import AdaptiveParams

        self.epsilon = AdaptiveParams.EXPLORATION if epsilon is None else epsilon
        self._lock = threading.Lock()
        self._classes: dict[str, EpsilonGreedy] = {}

    # ---------------------------------------------------------------- 决策

    def decide(self, worker_class_name: str) -> str:
        """按 Worker 类名决策走哪条臂.

        未知类目惰性建档（初始两臂皆无样本 → 首 N 次靠 ε 探索双臂摸值）。

        Args:
            worker_class_name: Worker 类名（统计 key；非实例名）

        Returns:
            臂名（ARM_NATIVE / ARM_PYTHON）
        """
        return self._greedy_for(worker_class_name).decide()

    def record(self, worker_class_name: str, arm: str, duration: float) -> None:
        """把一次实测时长记入对应类目的对应臂.

        Args:
            worker_class_name: Worker 类名（统计 key）
            arm: 本次实际执行所走的臂（决策臂 ≠ 实际臂时记实际臂——训练标签要贴脸）
            duration: 本次实测执行时长（秒）
        """
        self._greedy_for(worker_class_name).record(arm, duration)

    def _greedy_for(self, worker_class_name: str) -> EpsilonGreedy:
        """取（或惰性建档）某类目的两臂统计."""
        with self._lock:
            greedy = self._classes.get(worker_class_name)
            if greedy is None:
                greedy = EpsilonGreedy(epsilon=self._resolve_epsilon(worker_class_name))
                self._classes[worker_class_name] = greedy
            return greedy

    @staticmethod
    def _resolve_epsilon(worker_class_name: str) -> float:
        """解析类目探索率：``adaptive:explorationOverride`` 键族 → 全局默认."""
        from zoo_framework.params import AdaptiveParams

        value = ParamsFactory().get_params(
            f"{AdaptiveParams.EXPLORATION_OVERRIDE_PREFIX}:{worker_class_name}",
            default_value=AdaptiveParams.EXPLORATION,
        )
        return float(value)

    # ---------------------------------------------------------------- 视图

    def snapshot(self) -> dict[str, dict[str, dict[str, float]]]:
        """全部类目统计快照（持久化与测试断言用）."""
        with self._lock:
            return {name: greedy.snapshot() for name, greedy in self._classes.items()}


def get_bandit_policy() -> BanditPolicy:
    """进程级决策单例的访问入口（首次访问时创建）."""
    global _policy_singleton
    with _policy_lock:
        if _policy_singleton is None:
            _policy_singleton = BanditPolicy()
        return _policy_singleton


def reset_bandit_policy() -> None:
    """复位进程级决策单例（供测试使用）."""
    global _policy_singleton
    with _policy_lock:
        _policy_singleton = None


# CARRIERS 登记（spec/design「未登记被测试拦截」）：供 tests/test_process_state_registry.py
# 扫描的规范名指向本模块真源。复位入口引用 policy 模块函数（导入环安全：函数体内解析）。
def _register_carrier() -> None:
    process_state.CARRIERS["core.adaptive.policy:BanditPolicy"] = process_state.Carrier(
        canonical="core.adaptive.policy:BanditPolicy",
        category="执行设施",
        reason=(
            "bandit 决策的进程级单例（逐 Worker 类两臂统计）。与 native adapter 同形态："
            "模块级全局 + 显式 reset；复位=置空单例（测试从干净统计开始）。"
        ),
        watch=_policy_singleton,
        reset=reset_bandit_policy,
    )


_register_carrier()
