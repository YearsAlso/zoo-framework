from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class WorkerParams:
    # worker 资源池的尺寸
    WORKER_POOL_SIZE = ParamsPath(value="worker:pool:size", default=5)
    # worker 是否使用资源池
    WORKER_POOL_ENABLE = ParamsPath(value="worker:pool:enable", default=False)
    # worker 运行策略，simple：直接运行；stable：稳定运行；safe：安全运行；
    WORKER_RUN_POLICY = ParamsPath(value="worker:runPolicy", default="simple")
