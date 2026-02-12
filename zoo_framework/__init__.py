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

__version__ = "0.1.0"
__author__ = "XiangMeng"
__email__ = "mengxiang931015@live.com"
__license__ = "Apache-2.0"

from dotenv import find_dotenv, load_dotenv

from zoo_framework.conf import *
from zoo_framework.core import *
from zoo_framework.fifo import *
from zoo_framework.params import *
from zoo_framework.reactor import *
from zoo_framework.statemachine import *
from zoo_framework.utils import *
from zoo_framework.workers import *

__all__ = [
    "__version__",
    "conf",
    "core",
    "fifo",
    "handler",
    "params",
    "statemachine",
    "utils",
    "workers",
]

load_dotenv(find_dotenv())
