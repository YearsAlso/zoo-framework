"""异步 Worker 支持.

P2: 异步 IO 优化 - 支持异步 Worker 实现

与调度体系的接合点只有一个：``_execute``。调度器通过 ``BaseWorker.run()`` 调用它，
而调度线程不具备运行中的事件循环，因此它必须用 ``asyncio.run`` 直接驱动协程。
未覆写该方法会让异步 Worker 在调度器下只执行基类的空实现——占着线程空睡
``delay_time`` 后返回空结果，业务逻辑完全不被执行。
"""

import asyncio
import threading
import time
from abc import ABCMeta, abstractmethod
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import Any

from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker


class AsyncWorkerType(Enum):
    """异步 Worker 类型."""

    COROUTINE = "coroutine"  # 协程 Worker
    TASK = "task"  # 任务 Worker
    CALLBACK = "callback"  # 回调 Worker


class _BackgroundTask:
    """后台异步任务的句柄.

    提供 ``done()`` 与 ``result()``；``result()`` 会把后台协程抛出的异常重新抛出，
    而不是返回空值——静默丢失异常会让失败伪装成"没有结果"。
    """

    def __init__(self, thread: threading.Thread, container: dict):
        self._thread = thread
        self._container = container

    def done(self) -> bool:
        """后台任务是否已结束."""
        return not self._thread.is_alive()

    def result(self, timeout: float | None = None) -> Any:
        """取回后台任务的结果.

        Raises:
            TimeoutError: 超时后任务仍未结束
            BaseException: 后台协程抛出的异常
        """
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError("后台异步任务尚未结束")

        exception = self._container.get("exception")
        if exception is not None:
            raise exception

        return self._container.get("result")


class AsyncWorker(BaseWorker, metaclass=ABCMeta):
    """异步 Worker 基类.

    特性：
    - 原生协程支持
    - 自动事件循环管理
    - 支持同步和异步两种执行模式

    抽象约束由 ``ABCMeta`` 强制：未实现 ``async_execute`` 的子类无法被实例化。
    """

    def __init__(self, name: str | None = None):
        # 保留 name 这一公开签名，内部转成属性字典再交给 BaseWorker——BaseWorker
        # 以 _props 字典承载配置，直接传字符串会让 name / is_loop 等属性访问崩溃。
        super().__init__({"is_loop": False, "delay_time": 1, "name": name})
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_type = AsyncWorkerType.COROUTINE
        self._max_concurrent = 10  # 最大并发数
        self._semaphore: asyncio.Semaphore | None = None

    async def async_init(self) -> None:
        """异步初始化.

        子类可重写此方法进行异步资源初始化
        """
        LogUtils.info(f"✅ AsyncWorker '{self.name}' initialized")

    async def async_destroy(self, timeout: float | None = None) -> None:
        """异步销毁.

        子类可重写此方法进行异步资源清理

        Args:
            timeout: 超时时间
        """
        LogUtils.info(f"🛑 AsyncWorker '{self.name}' destroyed")

    @abstractmethod
    async def async_execute(self, *args, **kwargs) -> Any:
        """异步执行方法（子类必须实现）.

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        raise NotImplementedError("Subclasses must implement async_execute")

    def _execute(self):
        """调度路径的唯一入口.

        调度线程是普通线程，不具备运行中的事件循环，因此直接驱动一次协程。
        返回值会经 ``BaseWorker.run()`` 进入 ``WorkerResult``。

        Returns:
            异步执行体的业务返回值
        """
        return asyncio.run(self._execute_async())

    def execute(self, *args, **kwargs) -> Any:
        """同步执行入口.

        MUST 在没有运行中事件循环的线程中调用。在事件循环内调用时直接返回一个
        无人 await 的 Task 会让协程静默不执行，因此此处明确拒绝并给出替代用法。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果

        Raises:
            RuntimeError: 在已运行的事件循环中调用
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._execute_async(*args, **kwargs))

        raise RuntimeError(
            "execute() 不能在已运行的事件循环中调用——它无法同步等待协程结果，"
            "返回未 await 的 Task 会让协程静默不执行。请在协程中直接 await "
            "worker.async_execute(...)"
        )

    def _get_semaphore(self) -> asyncio.Semaphore:
        """按当前事件循环获取并发信号量.

        ``asyncio.Semaphore`` 会绑定到创建时的事件循环，跨循环复用会失败，
        因此按循环惰性重建，而不是在构造或初始化时一次性创建。

        Returns:
            当前循环下的信号量
        """
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
            self._loop = loop
        return self._semaphore

    async def _execute_async(self, *args, **kwargs) -> Any:
        """内部异步执行."""
        # 耗时是区间量，MUST 用单调时钟——墙钟跳变会产生负的或用巨的耗时
        start_time = time.monotonic()

        try:
            # 使用信号量限制并发
            async with self._get_semaphore():
                result = await self.async_execute(*args, **kwargs)

            duration = time.monotonic() - start_time
            LogUtils.info(f"✅ AsyncWorker '{self.name}' executed in {duration:.3f}s")

            return result

        except Exception as e:
            duration = time.monotonic() - start_time
            LogUtils.error(f"❌ AsyncWorker '{self.name}' failed after {duration:.3f}s: {e}")
            raise

    def run_in_background(self, *args, **kwargs) -> _BackgroundTask:
        """在后台运行.

        工作线程为守护线程：未完成的后台任务 MUST NOT 阻止解释器退出。

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            _BackgroundTask: 可通过 done() / result() 观察后台任务
        """
        result_container: dict = {}

        def run_async():
            try:
                result_container["result"] = asyncio.run(self._execute_async(*args, **kwargs))
            except BaseException as e:  # 异常保留给 result() 重抛
                result_container["exception"] = e

        thread = threading.Thread(target=run_async, daemon=True, name=f"zoo-async-{self.name}")
        thread.start()

        return _BackgroundTask(thread, result_container)


class AsyncEventWorker(AsyncWorker):
    """异步事件 Worker.

    支持异步处理事件的 Worker
    """

    def __init__(self, name: str = "AsyncEventWorker"):
        super().__init__(name)
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register_handler(self, event_type: str, handler: Callable[..., Awaitable[Any]]) -> None:
        """注册异步事件处理器.

        Args:
            event_type: 事件类型
            handler: 异步处理函数
        """
        self._handlers[event_type] = handler
        LogUtils.info(f"🎯 Handler registered for '{event_type}'")

    async def async_execute(self, event_type: str, *args, **kwargs) -> Any:
        """执行异步事件处理.

        Args:
            event_type: 事件类型
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            处理结果
        """
        if event_type not in self._handlers:
            raise ValueError(f"No handler registered for event type: {event_type}")

        handler = self._handlers[event_type]
        return await handler(*args, **kwargs)


class AsyncStateMachineWorker(AsyncWorker):
    """异步状态机 Worker.

    支持异步状态转换的 Worker
    """

    def __init__(self, name: str = "AsyncStateMachineWorker"):
        super().__init__(name)
        self._state_transitions: dict[str, Callable[..., Awaitable[Any]]] = {}
        self._current_state = "idle"

    def register_transition(self, state: str, handler: Callable[..., Awaitable[Any]]) -> None:
        """注册状态转换处理器.

        Args:
            state: 状态名称
            handler: 异步处理函数
        """
        self._state_transitions[state] = handler

    async def async_execute(self, target_state: str, *args, **kwargs) -> Any:
        """执行异步状态转换.

        Args:
            target_state: 目标状态
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            转换结果
        """
        if target_state not in self._state_transitions:
            raise ValueError(f"No transition registered for state: {target_state}")

        handler = self._state_transitions[target_state]
        result = await handler(*args, **kwargs)
        self._current_state = target_state

        return result

    def get_current_state(self) -> str:
        """获取当前状态."""
        return self._current_state


class AsyncWorkerPool:
    """异步 Worker 池.

    管理多个异步 Worker 的池。并发信号量按当前事件循环惰性创建——在构造时创建会
    把信号量绑定到当时的事件循环，使池无法在另一个循环中复用。
    """

    def __init__(self, max_workers: int = 10):
        self._max_workers = max_workers
        self._workers: list[AsyncWorker] = []
        self._semaphore: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        """按当前事件循环获取信号量."""
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._semaphore = asyncio.Semaphore(self._max_workers)
            self._loop = loop
        return self._semaphore

    async def submit(self, worker: AsyncWorker, *args, **kwargs) -> Any:
        """提交任务到 Worker 池.

        Args:
            worker: 异步 Worker
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        async with self._get_semaphore():
            return await worker._execute_async(*args, **kwargs)

    async def map(self, worker: AsyncWorker, items: list) -> list:
        """批量处理.

        Args:
            worker: 异步 Worker
            items: 待处理项列表

        Returns:
            结果列表
        """
        tasks = [self.submit(worker, item) for item in items]
        return await asyncio.gather(*tasks)


# 导出公共 API
__all__ = [
    "AsyncEventWorker",
    "AsyncStateMachineWorker",
    "AsyncWorker",
    "AsyncWorkerPool",
    "AsyncWorkerType",
]
