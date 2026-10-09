"""zoo_framework.core.adaptive — 逐任务类的在线自学路由决策（ε-greedy bandit）.

公共面（变更 add-adaptive-scheduling）：

- :class:`EpsilonGreedy`: 两臂增量统计与 ε-greedy 决策（O(1)）
- :class:`BanditPolicy`: 逐 Worker 类的决策入口（进程级单例）
- :func:`get_bandit_policy` / :func:`reset_bandit_policy`: 单例访问与复位

纪律：逻辑全部在 Worker 自身生命周期内闭环（``DualArmWorker``），本包不挂
调度内核的任何路径；关闭（``adaptive:enabled=false``，默认）时零分支零锁。
"""

from .bandit import ARM_NATIVE, ARM_PYTHON, EpsilonGreedy
from .policy import BanditPolicy, get_bandit_policy, reset_bandit_policy
from .stats_store import StatsStore, get_stats_store

__all__ = [
    "ARM_NATIVE",
    "ARM_PYTHON",
    "BanditPolicy",
    "EpsilonGreedy",
    "StatsStore",
    "get_bandit_policy",
    "get_stats_store",
    "reset_bandit_policy",
]
