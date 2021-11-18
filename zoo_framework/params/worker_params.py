from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class WorkerParams:
    # worker 运行模式
    WORKER_RUN_MODE = ParamsPath(value="worker:mode", default="thread")
    # worker 资源池的尺寸
    WORKER_POOL_SIZE = ParamsPath(value="worker:poolSize", default=5)
