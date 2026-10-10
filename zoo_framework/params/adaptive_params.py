"""自适应调度配置（独立键族 ``adaptive:*``）.

纪律：本模块经 lazy import 使用（``Master._create_waiter`` 等处已有先例），
在 ``ParamsFactory`` 读完 config.json 之前被 import 会冻结在默认值——与既有
参数类一致，不新增例外。
"""

from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class AdaptiveParams:
    # 自适应决策总开关；默认关闭——关闭时框架一切如旧（零回归路径）
    ADAPTIVE_ENABLED = param(value="adaptive:enabled", default=False)
    # ε-greedy 的探索率；默认 5% 决策用于随机探索非优势臂
    EXPLORATION = param(value="adaptive:exploration", default=0.05)
    # 双臂统计的持久化路径；默认空 = 不持久化（统计仅存于进程内存）
    STATS_PATH = param(value="adaptive:statsPath", default="")
    # 按 Worker 类名覆盖探索率的路径前缀，实际键为
    # ``adaptive:explorationOverride:<worker_class>:<exploration>``。
    # 这不是配置项本身，而是拼装路径用的前缀，故不声明为 ParamsPath。
    EXPLORATION_OVERRIDE_PREFIX = "adaptive:explorationOverride"
