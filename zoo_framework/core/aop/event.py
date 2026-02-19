import time

from zoo_framework.event.event_channel_manager import EventChannelManager
from zoo_framework.reactor import EventReactor
from zoo_framework.reactor.event_retry_strategy import EventRetryStrategy


# 自定义事件装饰器，用于注册事件
# 参数说明：
#   topic: 事件的主题，用于标识事件类型
#   channel: 事件通道名称，默认为"default"
#   timeout: 事件超时时间，默认为当前时间加1000秒
#   retry_time: 重试次数，默认为1次
#   retry_strategy: 重试策略，默认为RetryOnce（仅重试一次）
#   done_callback: 事件完成后的回调函数，默认为None
#   error_callback: 事件出错时的回调函数，默认为None
#   success_callback: 事件成功时的回调函数，默认为None
# 返回值：返回一个装饰器函数，用于包装目标函数
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
    # 内部装饰器函数，接收被装饰的目标函数
    def _event(func: callable):
        # 创建一个事件反应器实例，并设置相关属性
        reactor = EventReactor(func.__name__)
        reactor.set_event_callback(func)  # 设置事件回调函数为目标函数
        reactor.set_event_timeout(timeout)  # 设置事件超时时间
        reactor.set_retry_strategy(retry_strategy, retry_time)  # 设置重试策略和重试次数
        reactor.set_error_callback(error_callback)  # 设置错误回调函数
        reactor.set_success_callback(success_callback)  # 设置成功回调函数
        reactor.set_done_callback(done_callback)  # 设置完成回调函数

        # 检查并刷新事件通道，将当前反应器与指定主题和通道关联
        EventChannelManager().refresh_channel(channel, topic, reactor)
        return func  # 返回原始函数，保持装饰器透明性

    return _event  # 返回内部装饰器函数
