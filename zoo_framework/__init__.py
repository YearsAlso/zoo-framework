"""Zoo Framework - A simple and quick multi-threaded Python framework with zoo metaphor.

A declarative multi-task orchestration framework for long-lived background tasks:
declare task units (Workers), and the framework keeps them running - dispatch
scheduling, in-flight de-duplication, timeout circuit-breaking, an event pipeline,
and state persistence.

Core concepts (naming only - the metaphor does not affect semantics):
- Worker: the task execution unit. Subclass and implement ``_execute()``.
- Master: the lifecycle entry point. Load config, register Workers, run, shut down.
- Waiter: the scheduler. ``worker:mode`` picks the dispatch model.
- Event: the inter-worker message, delivered through channels.
- FIFO: one ordered queue per event channel.

Example:
    >>> from zoo_framework.core import Master
    >>> from zoo_framework.workers import BaseWorker
    >>>
    >>> class MyWorker(BaseWorker):
    ...     def _execute(self):
    ...         print("Hello from MyWorker!")
    >>>
    >>> master = Master()
    >>> master.run()

License: Apache-2.0
"""

__version__ = "0.10.4-beta"
__author__ = "XiangMeng"
__email__ = "mengxiang931015@live.com"
__license__ = "Apache-2.0"

from dotenv import find_dotenv, load_dotenv

# Replace wildcard imports with explicit package submodule imports to reduce linter noise
# and avoid importing many symbols at package import time.
from . import (
    conf,
    core,
    fifo,
    params,
    reactor,
    statemachine,
    utils,
    workers,
)

__all__ = [
    "__version__",
    "conf",
    "core",
    "fifo",
    "params",
    "reactor",
    "statemachine",
    "utils",
    "workers",
]


def load_env() -> None:
    """Explicitly load a .env file from the project root (not run at import time).

    Example:
        from zoo_framework import load_env
        load_env()
    """
    load_dotenv(find_dotenv())


# NOTE: the code used to run `load_dotenv(find_dotenv())` at import time;
# it is now an explicit function call to reduce import-time side effects
# (and linter noise).
