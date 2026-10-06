from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class EventParams:
    EVENT_JOIN_TIMEOUT = param(value="event:timeout", default=5)
    EVENT_SLEEP_TIME = param(value="event:sleep", default=0.2)
    # 事件投递线程池的工作线程数（align-execution-primitives D1）：实例级
    # ThreadPoolExecutor 在 __init__ 建一次，MUST NOT 在消费循环里 per-round 建池。
    EVENT_EXECUTOR_WORKERS = param(value="event:executor:workers", default=8)
