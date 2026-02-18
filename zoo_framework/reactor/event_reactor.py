"""
event_reactor - zoo_framework/reactor/event_reactor.py

模块功能描述.

作者: XiangMeng
版本: 0.5.2-beta
"""

event_reactor - zoo_framework/reactor/event_reactor.py

模块功能描述:

作者: XiangMeng
版本: 0.5.1-beta

from .event_priorities import EventPriorities
from .event_reactor_req import EventReactorReq
from .event_retry_strategy import EventRetryStrategy


class EventReactor:
    """EventReactor - 类功能描述"""
    def __init__(self, reactor_name):
        self.error_callback = None

        # 设置事件处理方法,不应该叫callback,应该叫event_handler
        self.handle_callback = None
        # 设置响应器名称
        self.reactor_name = reactor_name

        self.event_timout = 1
        # 设置内核优先级
        self.sys_priority: EventPriorities = EventPriorities.NORMAL.value
        # 设置用户优先级
        self.user_priority: EventPriorities = EventPriorities.NORMAL.value
        # 事件处理策略, 默认为失败后重试一次, 失败重试,直到成功;失败后,不再重试;失败后,重试一定次数;
        self.retry_strategy: EventRetryStrategy = EventRetryStrategy.RetryOnce
        # 事件处理成功后的回调
        self.success_callback = None
        # 事件处理失败后的回调
        self.retry_times = 0
        # 完成后的回调
        self.done_callback = None

    def set_done_callback(self, callback: callable):
        self.done_callback = callback

    def set_success_callback(self, callback: callable):
        self.success_callback = callback

    def set_retry_strategy(self, retry_strategy: EventRetryStrategy, retry_times=0):
        """设置重试策略."""
        self.retry_times = retry_times
        self.retry_strategy = retry_strategy

    def set_event_callback(self, callback):
        self.handle_callback = callback

    def set_error_callback(self, callback):
        self.error_callback = callback

    def get_priority(self) -> int:
        return (self.sys_priority.value << 8) & self.user_priority.value

    def __index__(self):
        return self.get_priority()

    def set_event_timeout(self, timeout):
        self.event_timout = timeout

    def _on_error(self, topic, content, exception: Exception):
        if self.error_callback is not None:
            self.error_callback(self.reactor_name, topic, content, exception)

    def _on_success(self, topic, content):
        if self.success_callback is not None:
            self.success_callback(self.reactor_name, topic, content)

    def _on_done(self, topic, content):
        if self.done_callback is not None:
            self.done_callback(self.reactor_name, topic, content)

    @staticmethod
    def _serialize_content(content):
        return content

    # 根据重试策略,执行事件
    def _execute(self, topic, content):
        req = EventReactorReq(topic, content, self.reactor_name)
        # 如果是失败后不再重试,直接执行
        if self.retry_strategy == EventRetryStrategy.RetryOnce:
            # 重试一次
            self.retry_times = 1
            while self.retry_times > 0:
                try:
                    self.handle_callback(req)
                    return
                except Exception as e:
                    self.retry_times -= 1
                    self._on_error(topic, content, e)
        elif self.retry_strategy == EventRetryStrategy.RetryTimes:
            while self.retry_times > 0:
                try:
                    self.handle_callback(req)
                    return
                except Exception as e:
                    self.retry_times -= 1
                    self._on_error(topic, content, e)
        elif (
            self.retry_strategy == EventRetryStrategy.RetryForever
            or self.retry_strategy == EventRetryStrategy.RetryNever
        ):
            while True:
                try:
                    self.handle_callback(req)
                    return
                except Exception as e:
                    self._on_error(topic, content, e)
        else:
            raise Exception("未知的事件重试策略")

    def execute(self, topic, content):
        """执行事件."""
        # 获得执行方法
        event_handler = self.handle_callback

        if event_handler is None:
            return

        try:
            # 序列化事件内容
            _content = self._serialize_content(content)
            # 执行事件
            self._execute(topic, _content)
            # 执行成功后的回调
            self._on_success(topic, content)
        except Exception as e:
            # 执行失败后的回调
            self._on_error(topic, content, e)
        finally:
            # 执行完成后的回调
            self._on_done(topic, content)

""""""
