"""Zoo Framework - A simple and quick multi-threaded Python framework with zoo metaphor.

🎪 动物园框架 - 基于动物园隐喻的 Python 多线程框架

核心概念：
- 🦁 Worker: 动物，执行任务的基本单元
- 🏠 Cage: 笼子，提供线程安全和生命周期管理
- 👨‍🌾 Master: 园长，管理整个动物园
- 🍎 Event: 食物，Worker 间通信的载体
- 🥘 FIFO: 饲养员队列，管理事件的有序处理

示例：
    >>> from zoo_framework.core import Master
    >>> from zoo_framework.workers import BaseWorker
    >>>
    >>> class MyWorker(BaseWorker):
    ...     def _execute(self):
    ...         print("Hello from MyWorker!")
    >>>
    >>> master = Master()
    >>> master.run()

版本: 0.1.0
作者: XiangMeng
许可证: Apache-2.0
"""

__version__ = "0.1.1-beta"
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
    """显式加载工程根目录下的 .env 文件（不在包导入时自动运行）。

    调用示例：
        from zoo_framework import load_env
        load_env()
    """
    load_dotenv(find_dotenv())


# NOTE: 原先代码在模块导入时会立即运行 `load_dotenv(find_dotenv())`，
# 为了降低导入时的副作用（并减少 linter 噪声），已改为显式函数调用。
