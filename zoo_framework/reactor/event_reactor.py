from collections.abc import Callable

from .event_priorities import EventPriorities
from .event_reactor_req import EventReactorReq
from .event_retry_strategy import EventRetryStrategy


class EventReactor:
    def __init__(self, reactor_name):
        self.error_callback = None

        # 设置事件处理方法,不应该叫callback,应该叫event_handler
        self.handle_callback = None
        # 设置响应器名称
        self.reactor_name = reactor_name

        self.event_timout = 1
        # 设置内核优先级（存 EventPriorities 成员本身，而非其 .value）
        self.sys_priority: EventPriorities = EventPriorities.NORMAL
        # 设置用户优先级
        self.user_priority: EventPriorities = EventPriorities.NORMAL
        # 事件处理策略, 默认为失败后重试一次, 失败重试，直到成功；失败后，不再重试；失败后，重试一定次数；
        self.retry_strategy: EventRetryStrategy = EventRetryStrategy.RetryOnce
        # 事件处理成功后的回调
        self.success_callback = None
        # 事件处理失败后的回调
        self.retry_times = 0
        # 完成后的回调
        self.done_callback = None

    def set_done_callback(self, callback: Callable):
        self.done_callback = callback

    def set_success_callback(self, callback: Callable):
        self.success_callback = callback

    def set_retry_strategy(self, retry_strategy: EventRetryStrategy, retry_times=0):
        """设置重试策略."""
        self.retry_times = retry_times
        self.retry_strategy = retry_strategy

    def set_event_callback(self, callback):
        self.handle_callback = callback

    def set_error_callback(self, callback):
        self.error_callback = callback

    @staticmethod
    def _priority_value(priority) -> int:
        """把优先级规整为整数.

        同时接受 `EventPriorities` 成员与其整数值：历史实现里 `sys_priority`
        被赋成了 int，此处对这种用法保持兼容，避免同类崩溃复现。
        """
        if isinstance(priority, EventPriorities):
            return priority.value
        return int(priority)

    def get_priority(self) -> int:
        """综合优先级.

        分段编码：系统优先级占高位（左移 8 位），用户优先级占低位，二者共同
        决定排序。此处必须是按位或而非按位与——用 `&` 会让低位段被高位段清零，
        使所有响应器的综合优先级退化为同一个值。
        """
        return (self._priority_value(self.sys_priority) << 8) | self._priority_value(
            self.user_priority
        )

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

    # 重试策略语义表（design D5）：
    #   RetryOnce / RetryNever      回调最多调用 1 次，失败即停止
    #   RetryTimes                  回调最多调用 retry_times 次
    #   RetryForever / RetryAlways  仅在回调成功时返回（RetryAlways 是 RetryForever 的别名）
    _SINGLE_ATTEMPT_STRATEGIES = (
        EventRetryStrategy.RetryOnce,
        EventRetryStrategy.RetryNever,
    )
    _UNLIMITED_ATTEMPT_STRATEGIES = (
        EventRetryStrategy.RetryForever,
        EventRetryStrategy.RetryAlways,
    )

    # 根据重试策略，执行事件
    def _execute(self, topic, content):
        req = EventReactorReq(topic, content, self.reactor_name)

        if self.retry_strategy in self._SINGLE_ATTEMPT_STRATEGIES:
            attempts = 1
        elif self.retry_strategy == EventRetryStrategy.RetryTimes:
            attempts = self.retry_times
        elif self.retry_strategy in self._UNLIMITED_ATTEMPT_STRATEGIES:
            attempts = None  # 无上限，仅在成功时返回
        else:
            raise Exception(f"未知的事件重试策略: {self.retry_strategy}")

        while attempts is None or attempts > 0:
            if attempts is not None:
                attempts -= 1
            try:
                self.handle_callback(req)
                return
            except Exception as e:
                self._on_error(topic, content, e)

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
