from collections.abc import Callable

from .event_priorities import EventPriorities
from .event_reactor_req import EventReactorReq
from .event_retry_strategy import EventRetryStrategy


class EventReactor:
    def __init__(self, reactor_name):
        self.error_callback = None

        # The event handler method set here - naming history: not 'callback',
        # should be 'event_handler'
        self.handle_callback = None
        # Set the reactor name
        self.reactor_name = reactor_name

        self.event_timout = 1
        # Set the kernel priority (store the EventPriorities member itself,
        # not its .value)
        self.sys_priority: EventPriorities = EventPriorities.NORMAL
        # Set the user priority
        self.user_priority: EventPriorities = EventPriorities.NORMAL
        # The event handling strategy; default is retry once after failure.
        # Retry until success; give up after failure; retry a fixed number
        # of times after failure
        self.retry_strategy: EventRetryStrategy = EventRetryStrategy.RetryOnce
        # The callback after the event is handled successfully
        self.success_callback = None
        # The callback after the event handling fails
        self.retry_times = 0
        # The callback after completion
        self.done_callback = None

    def set_done_callback(self, callback: Callable):
        self.done_callback = callback

    def set_success_callback(self, callback: Callable):
        self.success_callback = callback

    def set_retry_strategy(self, retry_strategy: EventRetryStrategy, retry_times=0):
        """Set the retry strategy."""
        self.retry_times = retry_times
        self.retry_strategy = retry_strategy

    def set_event_callback(self, callback):
        self.handle_callback = callback

    def set_error_callback(self, callback):
        self.error_callback = callback

    @staticmethod
    def _priority_value(priority) -> int:
        """Normalize a priority into an integer.

        Accepts both an `EventPriorities` member and its integer value: the
        historical implementation assigned an int to `sys_priority`, so this
        stays compatible with that usage to keep the same crash from
        recurring.
        """
        if isinstance(priority, EventPriorities):
            return priority.value
        return int(priority)

    def get_priority(self) -> int:
        """The combined priority.

        Segmented encoding: the system priority takes the high bits (shifted
        left by 8), the user priority the low bits; together they decide
        ordering. This MUST be bitwise OR, not bitwise AND - `&` would zero
        the low segment under the high segment, degrading every reactor's
        combined priority to the same value.
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

    # Retry strategy semantics table (design D5):
    #   RetryOnce / RetryNever      the callback runs at most once; stop on failure
    #   RetryTimes                  the callback runs at most retry_times times
    #   RetryForever / RetryAlways  return only when the callback succeeds
    #                               (RetryAlways is an alias of RetryForever)
    _SINGLE_ATTEMPT_STRATEGIES = (
        EventRetryStrategy.RetryOnce,
        EventRetryStrategy.RetryNever,
    )
    _UNLIMITED_ATTEMPT_STRATEGIES = (
        EventRetryStrategy.RetryForever,
        EventRetryStrategy.RetryAlways,
    )

    # Execute the event according to the retry strategy
    def _execute(self, topic, content):
        req = EventReactorReq(topic, content, self.reactor_name)

        if self.retry_strategy in self._SINGLE_ATTEMPT_STRATEGIES:
            attempts = 1
        elif self.retry_strategy == EventRetryStrategy.RetryTimes:
            attempts = self.retry_times
        elif self.retry_strategy in self._UNLIMITED_ATTEMPT_STRATEGIES:
            attempts = None  # unlimited; return only on success
        else:
            raise Exception(f"unknown event retry strategy: {self.retry_strategy}")

        while attempts is None or attempts > 0:
            if attempts is not None:
                attempts -= 1
            try:
                if self.handle_callback is None:
                    # Give a readable reason when no callback is set; it
                    # falls into the except below all the same, going
                    # through the existing "log error + retry" path (the old
                    # code raised "NoneType is not callable" - same
                    # semantics, but the reason was unreadable).
                    raise ValueError(f"reactor {self.reactor_name} has no event callback set")
                self.handle_callback(req)
                return
            except Exception as e:
                self._on_error(topic, content, e)

    def execute(self, topic, content):
        """Execute the event."""
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
