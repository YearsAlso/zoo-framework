"""异步 Worker 支持.

P2: 异步 IO 优化 - 支持异步 Worker 实现
"""

import asyncio
import time
from abc import abstractmethod
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


class AsyncWorker(BaseWorker):
    """异步 Worker 基类.

    P2 优化：支持异步执行的 Worker

    特性：
    - 原生协程支持
    - 自动事件循环管理
    - 支持同步和异步两种执行模式
    - 性能大幅提升
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
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
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

    def execute(self, *args, **kwargs) -> Any:
        """同步执行入口.

        自动处理异步执行逻辑

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        # 检查是否在事件循环中
        try:
            loop = asyncio.get_running_loop()
            # 已在事件循环中，创建任务
            return loop.create_task(self._execute_async(*args, **kwargs))
        except RuntimeError:
            # 不在事件循环中，运行新循环
            return asyncio.run(self._execute_async(*args, **kwargs))

    async def _execute_async(self, *args, **kwargs) -> Any:
        """内部异步执行."""
        start_time = time.time()

        try:
            # 使用信号量限制并发
            if self._semaphore:
                async with self._semaphore:
                    result = await self.async_execute(*args, **kwargs)
            else:
                result = await self.async_execute(*args, **kwargs)

            duration = time.time() - start_time
            LogUtils.info(f"✅ AsyncWorker '{self.name}' executed in {duration:.3f}s")

            return result

        except Exception as e:
            duration = time.time() - start_time
            LogUtils.error(f"❌ AsyncWorker '{self.name}' failed after {duration:.3f}s: {e}")
            raise

    def run_in_background(self, *args, **kwargs) -> Any:
        """在后台运行.

        将任务提交到事件循环后台执行

        Args:
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            异步任务或模拟任务对象
        """
        try:
            loop = asyncio.get_running_loop()
            return loop.create_task(self._execute_async(*args, **kwargs))
        except RuntimeError:
            # 没有运行的事件循环，创建新线程运行
            import threading

            result_container = {}

            def run_async():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result = loop.run_until_complete(self._execute_async(*args, **kwargs))
                    result_container["result"] = result
                finally:
                    loop.close()

            thread = threading.Thread(target=run_async)
            thread.start()

            # 返回一个模拟的任务对象
            class FakeTask:
                def __init__(self, thread, container):
                    self._thread = thread
                    self._container = container

                def done(self):
                    return not self._thread.is_alive()

                def result(self):
                    self._thread.join()
                    return self._container.get("result")

            return FakeTask(thread, result_container)


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

    管理多个异步 Worker 的池
    """

    def __init__(self, max_workers: int = 10):
        self._max_workers = max_workers
        self._workers: list[AsyncWorker] = []
        self._semaphore = asyncio.Semaphore(max_workers)
        self._queue: asyncio.Queue = asyncio.Queue()

    async def submit(self, worker: AsyncWorker, *args, **kwargs) -> Any:
        """提交任务到 Worker 池.

        Args:
            worker: 异步 Worker
            *args: 位置参数
            **kwargs: 关键字参数

        Returns:
            执行结果
        """
        async with self._semaphore:
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
