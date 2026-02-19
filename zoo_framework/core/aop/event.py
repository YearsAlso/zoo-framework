import time

from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.reactor import EventReactor
from zoo_framework.reactor.event_retry_strategy import EventRetryStrategy


# 自定义事件装饰器，用于注册事件
def event(
    topic: str,
    channel: str = "default",
    timeout: int = time.time() + 1000,
    retry_time: int = 1,
    retry_strategy=EventRetryStrategy.RetryOnce,
    done_callback=None,
    error_callback=None,
    success_callback=None,
):
    def _event(func: callable):
        # 创建一个reactor
        reactor = EventReactor(func.__name__)
        reactor.set_event_callback(func)
        reactor.set_event_timeout(timeout)
        reactor.set_retry_strategy(retry_strategy, retry_time)
        reactor.set_error_callback(error_callback)
        reactor.set_success_callback(success_callback)
        reactor.set_done_callback(done_callback)

        # 判断是否有channel，如果没有，则创建一个channel
        EventChannelManager().refresh_channel(channel, topic, reactor)
        return func

    return _event
