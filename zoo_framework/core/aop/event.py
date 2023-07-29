from zoo_framework.reactor import EventReactor
from zoo_framework.event.event_channel_register import EventChannelRegister

event_map = EventChannelRegister()


# 自定义事件装饰器，用于注册事件
def event(topic: str, channel: str = "default", timeout: int = 0, retry_time: int = 0, retry_strategy=None,
          done_callback=None,
          error_callback=None, success_callback=None):
    def _event(func: callable):
        # 创建一个reactor
        reactor = EventReactor(func.__name__)
        reactor.set_event_callback(func)
        reactor.set_event_timeout(timeout)
        reactor.set_retry_strategy(retry_strategy, retry_time)
        reactor.set_error_callback(error_callback)
        reactor.set_success_callback(success_callback)
        reactor.set_done_callback(done_callback)

        event_map.register(channel, reactor)
        return func

    return _event
