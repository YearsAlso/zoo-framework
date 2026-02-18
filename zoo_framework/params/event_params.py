"""event_params - 事件参数配置模块

作者: XiangMeng
版本: 0.5.2-beta
"""


from zoo_framework.core import ParamsPath
from zoo_framework.core.aop import params


@params
class EventParams:

    def __init__(self):
        self.event_timeout = ParamsPath("event.timeout", 30)
        self.event_retry_count = ParamsPath("event.retry_count", 3)
        self.event_retry_delay = ParamsPath("event.retry_delay", 1.0)
        self.event_queue_size = ParamsPath("event.queue_size", 1000)
        self.event_worker_count = ParamsPath("event.worker_count", 4)

        # 事件优先级配置
        self.priority_high = ParamsPath("event.priority.high", 10)
        self.priority_medium = ParamsPath("event.priority.medium", 5)
        self.priority_low = ParamsPath("event.priority.low", 1)

        # 事件日志配置
        self.log_level = ParamsPath("event.log.level", "info")
        self.log_format = ParamsPath("event.log.format", "json")
        self.log_enabled = ParamsPath("event.log.enabled", True)

        # 事件处理配置
        self.process_async = ParamsPath("event.process.async", True)
        self.process_timeout = ParamsPath("event.process.timeout", 60)
        self.process_retry = ParamsPath("event.process.retry", True)

        # 事件监控配置
        self.monitor_enabled = ParamsPath("event.monitor.enabled", True)
        self.monitor_interval = ParamsPath("event.monitor.interval", 30)
        self.monitor_metrics = ParamsPath("event.monitor.metrics", True)
