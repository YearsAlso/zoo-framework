"""任务层：与 Worker 解耦的任务值对象与落到状态机持久化作用域的任务队列。

变更 add-task-layer（GitHub issue #234 形状 1 + 形状 2）。任务层是**新能力**，只在
**存储**上依赖状态机（依赖方向 ``tasks -> statemachine`` 单向）。公共 API 见
``Task`` / ``TaskStatus`` / ``TaskQueue``。
"""

from .task import Task, TaskStatus
from .task_queue import TaskQueue

__all__ = ["Task", "TaskQueue", "TaskStatus"]
