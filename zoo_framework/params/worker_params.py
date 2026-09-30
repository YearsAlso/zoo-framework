from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class WorkerParams:
    # worker 资源池的尺寸
    WORKER_POOL_SIZE = ParamsPath(value="worker:pool:size", default=5)
    # worker 是否使用资源池
    # 别名 worker:pool:enabled 兼容脚手架（zfc --create）产出的键名，
    # 该键名历史上与读取路径不一致，导致配置被静默忽略。
    WORKER_POOL_ENABLE = ParamsPath(
        value="worker:pool:enable", default=False, aliases=["worker:pool:enabled"]
    )
    # worker 运行策略，simple：直接运行；stable：稳定运行；safe：安全运行；
    WORKER_RUN_POLICY = ParamsPath(value="worker:runPolicy", default="simple")
    # 调度的执行模式：thread / thread_pool。
    # 留空表示由 worker:pool:enable 推导；显式配置时以本项为准，
    # 未实现的模式（如 process）会被明确拒绝而非静默降级。
    WORKER_MODE = ParamsPath(value="worker:mode", default="")

    # ---- 以下为调度层新增的配置入口 ----
    # Worker 执行的默认超时秒数；<=0 或未声明表示不启用超时判定
    WORKER_RUN_TIMEOUT = ParamsPath(value="worker:runTimeout", default=0)
    # Worker 的默认循环标志，供未自行声明 is_loop 的 Worker 使用
    WORKER_DEFAULT_IS_LOOP = ParamsPath(value="worker:default:isLoop", default=False)
    # Worker 的默认延迟秒数，供未自行声明 delay_time 的 Worker 使用
    WORKER_DEFAULT_DELAY_TIME = ParamsPath(value="worker:default:delayTime", default=0)

    # Worker 执行周期与相位的**全局默认**（秒）；未声明表示不启用周期语义
    # （即按事件驱动处理）。周期与相位由 Worker 逐个声明，此处只是兜底默认值。
    WORKER_PERIOD = ParamsPath(value="worker:period", default=None)
    WORKER_PHASE = ParamsPath(value="worker:phase", default=None)

    # 按 Worker 名覆盖超时的配置路径前缀，实际键为
    # ``worker:override:<worker_name>:runTimeout``。
    # 同样用于 ``:period`` / ``:phase`` / ``:runTimeout``。
    # 这不是配置项本身，而是拼装路径用的前缀，故不声明为 ParamsPath。
    WORKER_OVERRIDE_PREFIX = "worker:override"
