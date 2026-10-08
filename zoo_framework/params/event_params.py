from zoo_framework.core import param
from zoo_framework.core.aop import params


@params
class EventParams:
    EVENT_JOIN_TIMEOUT = param(value="event:timeout", default=5)
    # 事件管道节拍（秒）：EventWorker 排空一次通道后的结算间隔，期间一直算在飞
    # 不会被再次派发（变更 configurable-run-delay / #73）。默认 5 与历史硬编码
    # 一致，行为向后兼容。旧键 event:sleep 随 gevent 消费循环删除后零消费，
    # 已移除（填写它不会有任何效果）。
    EVENT_DELAY_TIME = param(value="event:delay", default=5)
    # 事件投递线程池的工作线程数（align-execution-primitives D1）：实例级
    # ThreadPoolExecutor 在 __init__ 建一次，MUST NOT 在消费循环里 per-round 建池。
    EVENT_EXECUTOR_WORKERS = param(value="event:executor:workers", default=8)
