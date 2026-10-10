"""Async Worker support.

P2: async IO optimization - async Worker implementations.

The only integration point with the scheduling system is ``_execute``. The
scheduler calls it through ``BaseWorker.run()`` and the scheduling thread has
no running event loop, so it must drive the coroutine directly with
``asyncio.run``. Not overriding the method makes an async Worker run only the
base class' empty implementation under the scheduler - it occupies the
thread, sleeps ``delay_time`` and returns an empty result while the business
logic never executes.
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
    """Async Worker types."""

    COROUTINE = "coroutine"  # coroutine Worker
    TASK = "task"  # task Worker
    CALLBACK = "callback"  # callback Worker


class _BackgroundTask:
    """A handle to a background async task.

    Provides ``done()`` and ``result()``; ``result()`` re-raises an exception
    thrown by the background coroutine instead of returning an empty value -
    silently swallowing the exception would disguise the failure as "no
    result".
    """

    def __init__(self, thread: threading.Thread, container: dict):
        self._thread = thread
        self._container = container

    def done(self) -> bool:
        """Whether the background task has finished."""
        return not self._thread.is_alive()

    def result(self, timeout: float | None = None) -> Any:
        """Collect the background task's result.

        Raises:
            TimeoutError: the task has not finished when the timeout elapses
            BaseException: an exception raised by the background coroutine
        """
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise TimeoutError("background async task has not finished yet")

        exception = self._container.get("exception")
        if exception is not None:
            raise exception

        return self._container.get("result")


class AsyncWorker(BaseWorker, metaclass=ABCMeta):
    """Async Worker base class.

    Features:
    - native coroutine support
    - automatic event loop management
    - both synchronous and asynchronous execution modes

    The abstract constraint is enforced by ``ABCMeta``: a subclass that does
    not implement ``async_execute`` cannot be instantiated.
    """

    def __init__(self, name: str | None = None):
        # Keep `name` as the public signature but convert it into the props dict
        # for BaseWorker - BaseWorker carries config in the _props dict, and
        # passing a bare string would crash the name / is_loop property access.
        super().__init__({"is_loop": False, "delay_time": 1, "name": name})
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_type = AsyncWorkerType.COROUTINE
        self._max_concurrent = 10  # max concurrency
        self._semaphore: asyncio.Semaphore | None = None

    async def async_init(self) -> None:
        """Async initialization.

        Subclasses may override this to initialize async resources.
        """
        LogUtils.info(f"✅ AsyncWorker '{self.name}' initialized")

    async def async_destroy(self, timeout: float | None = None) -> None:
        """Async teardown.

        Subclasses may override this to clean up async resources.

        Args:
            timeout: the timeout
        """
        LogUtils.info(f"🛑 AsyncWorker '{self.name}' destroyed")

    @abstractmethod
    async def async_execute(self, *args: Any, **kwargs: Any) -> Any:
        """The async execution method (subclasses MUST implement).

        Args:
            *args: positional arguments
            **kwargs: keyword arguments

        Returns:
            The execution result
        """
        raise NotImplementedError("Subclasses must implement async_execute")

    def _execute(self):
        """The only entry point on the scheduling path.

        The scheduling thread is an ordinary thread with no running event loop,
        so the coroutine is driven directly here. The return value flows into
        ``WorkerResult`` through ``BaseWorker.run()``.

        Returns:
            The business return value of the async execution body
        """
        return asyncio.run(self._execute_async())

    def execute(self, *args, **kwargs) -> Any:
        """The synchronous execution entry point.

        MUST be called from a thread with no running event loop. Calling it
        inside an event loop and returning a Task that nobody awaits would
        silently skip the coroutine, so this refuses explicitly and states the
        alternative.

        Args:
            *args: positional arguments
            **kwargs: keyword arguments

        Returns:
            The execution result

        Raises:
            RuntimeError: called inside a running event loop
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self._execute_async(*args, **kwargs))

        raise RuntimeError(
            "execute() cannot be called inside a running event loop - it "
            "cannot synchronously wait on a coroutine's result, and returning "
            "an un-awaited Task would let the coroutine silently never run. "
            "Please directly await worker.async_execute(...) inside a coroutine."
        )

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get the concurrency semaphore for the current event loop.

        ``asyncio.Semaphore`` binds to the event loop it was created on, and
        reusing it across loops fails; so it is rebuilt lazily per loop instead
        of being created once at construction or initialization.

        Returns:
            The semaphore under the current loop
        """
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._semaphore = asyncio.Semaphore(self._max_concurrent)
            self._loop = loop
        return self._semaphore

    async def _execute_async(self, *args: Any, **kwargs: Any) -> Any:
        """Internal async execution."""
        # Duration is an interval quantity and MUST use the monotonic clock -
        # wall-clock jumps would produce negative or wildly wrong durations
        start_time = time.monotonic()

        try:
            # Limit concurrency with the semaphore
            async with self._get_semaphore():
                result = await self.async_execute(*args, **kwargs)

            duration = time.monotonic() - start_time
            LogUtils.info(f"✅ AsyncWorker '{self.name}' executed in {duration:.3f}s")

            return result

        except Exception as e:
            duration = time.monotonic() - start_time
            LogUtils.error(f"❌ AsyncWorker '{self.name}' failed after {duration:.3f}s: {e}")
            raise

    def run_in_background(self, *args: Any, **kwargs: Any) -> _BackgroundTask:
        """Run in the background.

        The worker thread is a daemon: unfinished background tasks MUST NOT
        prevent interpreter exit.

        Args:
            *args: positional arguments
            **kwargs: keyword arguments

        Returns:
            _BackgroundTask: the background task, observable via done() /
                result()
        """
        result_container: dict = {}

        def run_async():
            try:
                result_container["result"] = asyncio.run(self._execute_async(*args, **kwargs))
            except BaseException as e:  # kept for result() to re-raise
                result_container["exception"] = e

        thread = threading.Thread(target=run_async, daemon=True, name=f"zoo-async-{self.name}")
        thread.start()

        return _BackgroundTask(thread, result_container)


class AsyncEventWorker(AsyncWorker):
    """Async event Worker.

    A Worker supporting asynchronous event handling.
    """

    def __init__(self, name: str = "AsyncEventWorker"):
        super().__init__(name)
        self._handlers: dict[str, Callable[..., Awaitable[Any]]] = {}

    def register_handler(self, event_type: str, handler: Callable[..., Awaitable[Any]]) -> None:
        """Register an async event handler.

        Args:
            event_type: the event type
            handler: the async handler function
        """
        self._handlers[event_type] = handler
        LogUtils.info(f"🎯 Handler registered for '{event_type}'")

    async def async_execute(self, event_type: str, *args: Any, **kwargs: Any) -> Any:
        """Run the async event handling.

        Args:
            event_type: the event type
            *args: positional arguments
            **kwargs: keyword arguments

        Returns:
            The handling result
        """
        if event_type not in self._handlers:
            raise ValueError(f"No handler registered for event type: {event_type}")

        handler = self._handlers[event_type]
        return await handler(*args, **kwargs)


class AsyncStateMachineWorker(AsyncWorker):
    """Async state machine Worker.

    A Worker supporting asynchronous state transitions.
    """

    def __init__(self, name: str = "AsyncStateMachineWorker"):
        super().__init__(name)
        self._state_transitions: dict[str, Callable[..., Awaitable[Any]]] = {}
        self._current_state = "idle"

    def register_transition(self, state: str, handler: Callable[..., Awaitable[Any]]) -> None:
        """Register a state transition handler.

        Args:
            state: the state name
            handler: the async handler function
        """
        self._state_transitions[state] = handler

    async def async_execute(self, target_state: str, *args: Any, **kwargs: Any) -> Any:
        """Run the async state transition.

        Args:
            target_state: the target state
            *args: positional arguments
            **kwargs: keyword arguments

        Returns:
            The transition result
        """
        if target_state not in self._state_transitions:
            raise ValueError(f"No transition registered for state: {target_state}")

        handler = self._state_transitions[target_state]
        result = await handler(*args, **kwargs)
        self._current_state = target_state

        return result

    def get_current_state(self) -> str:
        """Get the current state."""
        return self._current_state


class AsyncWorkerPool:
    """Async Worker pool.

    A pool managing several async Workers. The concurrency semaphore is created
    lazily per the current event loop - creating it at construction would bind
    the semaphore to the then-current loop and stop the pool from being reused
    on another loop.
    """

    def __init__(self, max_workers: int = 10):
        self._max_workers = max_workers
        self._workers: list[AsyncWorker] = []
        self._semaphore: asyncio.Semaphore | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

    def _get_semaphore(self) -> asyncio.Semaphore:
        """Get the semaphore for the current event loop."""
        loop = asyncio.get_running_loop()
        if self._semaphore is None or self._loop is not loop:
            self._semaphore = asyncio.Semaphore(self._max_workers)
            self._loop = loop
        return self._semaphore

    async def submit(self, worker: AsyncWorker, *args: Any, **kwargs: Any) -> Any:
        """Submit a task to the Worker pool.

        Args:
            worker: the async Worker
            *args: positional arguments
            **kwargs: keyword arguments

        Returns:
            The execution result
        """
        async with self._get_semaphore():
            return await worker._execute_async(*args, **kwargs)

    async def map(self, worker: AsyncWorker, items: list) -> list:
        """Process items in bulk.

        Args:
            worker: the async Worker
            items: the items to process

        Returns:
            The list of results
        """
        tasks = [self.submit(worker, item) for item in items]
        return await asyncio.gather(*tasks)


# Public API exports
__all__ = [
    "AsyncEventWorker",
    "AsyncStateMachineWorker",
    "AsyncWorker",
    "AsyncWorkerPool",
    "AsyncWorkerType",
]
