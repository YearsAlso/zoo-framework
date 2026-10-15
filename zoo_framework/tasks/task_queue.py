"""可持久化任务队列：落到状态机持久化作用域，重启不丢排队中的活。

变更 add-task-layer（GitHub issue #234 形状 2）。队列存储于 ``StateMachineManager`` 的
一个状态作用域内，因此随既有状态机持久化机制一起落盘、随恢复机制一起读回——**重启后
处于待跑状态的任务不丢**。

边界（见变更 design.md 的 Non-Goals）：

- **不接管派发**：队列只提供"可持久化的排队 + 原子认领"语义，消费者（Worker）自行决定
  怎么把认领到的任务跑起来。``WorkerDispatchCore`` 的调度语义一处不改。
- **不做容量 / 伸缩策略 / 背压**（形状 3 / 4）：不提供容量、并发度或退避配置。
- **取消只阻止尚未启动的**（形状 5 的诚实约束）：CPython 无法抢占，本队列 MUST NOT 声称
  能中断一个已开始的执行。
- **不建投递幂等**：只保证"任务身份在队列内唯一"，不承诺投递语义（issue #74 未决）。

并发正确性：所有变更走 ``_mutate`` 的**乐观读-改-写**——读节点版本，构造新列表，用
``StateScope.compare_and_set`` 在版本匹配时提交；版本被并发推高则重试。这把"检查 + 写入"
的两步窗口收敛进一次 CAS，复用 ``add-state-append-and-cas`` 交付的 scope 级锁与 CAS，
不新造并发原语。
"""

from __future__ import annotations

import threading
import time
from typing import TYPE_CHECKING, Any, TypeVar

from zoo_framework.statemachine.state_machine_manager import StateMachineManager
from zoo_framework.tasks.task import Task, TaskStatus

if TYPE_CHECKING:
    from collections.abc import Callable

#: 队列在状态作用域内所占的**顶层**节点键。不含点分——状态机把点分键当树路径解析，
#: 而任务身份可能含点，故不能让身份参与键构造。
_QUEUE_KEY = "tasks"

#: ``_mutate`` 的乐观重试上限。CAS 冲突即重试；持续争用耗尽是**异常**，显式失败而非静默丢更新。
_MUTATE_RETRIES = 256

# 队列节点的"引导锁"：``StateScope`` 没有原子的 create-if-absent，故用一个模块级锁 +
# 双重检查保证"建一次空列表"。它**只守护创建那一步**，之后全部走 CAS（design D4）。
# 用 ``threading.Lock``（非可变容器），不触发 core/process_state 的载体扫描。
_bootstrap_lock = threading.Lock()

_T = TypeVar("_T")


class TaskQueue:
    """落到状态机持久化作用域的可持久化任务队列。

    队列由一个**作用域名**参数化：不同作用域名即不同队列，持久化真源由进程级
    ``StateMachineManager`` 共享。本类**不是**进程级单例——单例会把不同名字的队列折叠
    成同一个，与"按作用域区分队列"冲突（design D5）。

    Attributes:
        _scope_name: 队列所处状态作用域名
        _manager: 底层状态机管理器
    """

    def __init__(
        self, scope: str | None = None, manager: StateMachineManager | None = None
    ) -> None:
        """初始化任务队列。

        Args:
            scope: 队列作用域名；None 时**运行期**读取配置键 ``task:queue:scope``
                的默认值（惰性导入 ``TaskParams``，避免 ``@params`` 在模块导入期
                冻结默认值）
            manager: 底层状态机管理器；None 时取进程级单例（测试可注入）
        """
        if scope is None:
            # 惰性导入：保证配置键在 ParamsFactory 读过配置之后才被解析。
            from zoo_framework.params import TaskParams

            scope = TaskParams.QUEUE_SCOPE
        self._scope_name = scope
        self._manager = manager if manager is not None else StateMachineManager()

    # ------------------------------------------------------------------ 内部

    def _scope(self):
        """取（必要时创建）队列所处状态作用域。"""
        return self._manager.get_and_create_scope(self._scope_name)

    def _ensure_node(self) -> None:
        """保证队列节点存在（双重检查锁：只建一次空列表）。"""
        scope = self._scope()
        if scope.get_state_node(_QUEUE_KEY) is not None:
            return
        with _bootstrap_lock:
            if scope.get_state_node(_QUEUE_KEY) is None:
                self._manager.set_state(self._scope_name, _QUEUE_KEY, [])

    def _read_items(self) -> list[dict[str, Any]]:
        """读取队列当前的任务字典列表（不创建作用域 / 节点）。"""
        value = self._manager.get_state(self._scope_name, _QUEUE_KEY)
        if not isinstance(value, list):
            return []
        return value

    def _mutate(
        self,
        transform: Callable[[list[dict[str, Any]]], tuple[list[dict[str, Any]], _T] | None],
    ) -> _T | None:
        """在队列节点上做原子读-改-写（乐观 CAS + 重试）。

        ``transform`` 接收当前任务字典列表的**副本**，返回 ``(新列表, 结果)``；返回
        ``None`` 表示"无需修改"（如目标状态不满足前置条件、任务不存在）。仅在版本未被
        并发改写时提交；冲突（``compare_and_set`` 返回 False）则重试，重试耗尽抛错。

        Args:
            transform: 变换函数，见上

        Returns:
            变换成功时的结果；``transform`` 返回 None 时为 None

        Raises:
            RuntimeError: 持续 CAS 冲突、重试耗尽
        """
        self._ensure_node()
        scope = self._scope()
        for _ in range(_MUTATE_RETRIES):
            node = scope.get_state_node(_QUEUE_KEY)
            if node is None:
                # 极端情形：节点被并发移除，重建后重试。
                self._ensure_node()
                continue
            version = node.get_version()
            current = node.get_value()
            snapshot = [dict(item) for item in current] if isinstance(current, list) else []
            outcome = transform(snapshot)
            if outcome is None:
                return None
            new_items, result = outcome
            if scope.compare_and_set(_QUEUE_KEY, version, new_items):
                return result
        raise RuntimeError(
            f"task queue '{self._scope_name}' mutation kept conflicting after "
            f"{_MUTATE_RETRIES} retries"
        )

    # ------------------------------------------------------------------ 提交与查询

    def submit(self, task: Task) -> Task:
        """提交一个任务（持久化入队）。

        身份在队列内 MUST 唯一：若队列已存在同 ``task_id`` 的任务，MUST 显式拒绝
        （抛错），MUST NOT 静默产生第二条同身份任务。该拒绝只保证"身份唯一"，
        **不含投递幂等承诺**（投递语义仍是未决问题，issue #74）。

        Args:
            task: 要提交的任务

        Returns:
            已入队的任务

        Raises:
            TypeError: 入参不是 ``Task``
            ValueError: ``task_id`` 为空，或队列已存在同一身份
        """
        if not isinstance(task, Task):
            raise TypeError(f"submit expects a Task, got {type(task).__name__}")
        if not task.task_id:
            raise ValueError("任务身份（task_id）MUST NOT 为空")

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Task] | None:
            for item in items:
                if item.get("task_id") == task.task_id:
                    raise ValueError(
                        f"task '{task.task_id}' already exists in queue '{self._scope_name}'"
                    )
            items.append(task.to_dict())
            return items, task

        result = self._mutate(transform)
        return result if result is not None else task

    def get(self, task_id: str) -> Task | None:
        """按身份查询任务。

        Args:
            task_id: 任务身份

        Returns:
            任务；不存在时 None（不抛错）
        """
        for item in self._read_items():
            if item.get("task_id") == task_id:
                return Task.from_dict(item)
        return None

    def tasks(self, status: TaskStatus | str | None = None) -> list[Task]:
        """按提交顺序返回任务快照，可按状态过滤。

        Args:
            status: 只返回该状态的任务；None 表示不过滤

        Returns:
            任务列表（提交顺序）
        """
        wanted = None if status is None else TaskStatus(status)
        result: list[Task] = []
        for item in self._read_items():
            task = Task.from_dict(item)
            if wanted is None or task.status == wanted:
                result.append(task)
        return result

    # ------------------------------------------------------------------ 生命周期迁移

    def claim(self, task_id: str) -> Task | None:
        """原子认领一个待跑任务（待跑 -> 执行中，尝试次数 +1）。

        仅当目标任务当前为**待跑**时生效；并发认领同一任务时恰好一个成功。

        Args:
            task_id: 任务身份

        Returns:
            认领后的任务；任务不存在或状态不是待跑时 None
        """
        now = time.time()

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Task] | None:
            for item in items:
                if item.get("task_id") != task_id:
                    continue
                if item.get("status") != TaskStatus.PENDING.value:
                    return None
                item["status"] = TaskStatus.RUNNING.value
                item["attempts"] = int(item.get("attempts", 0)) + 1
                item["started_at"] = now
                item["updated_at"] = now
                return items, Task.from_dict(item)
            return None

        return self._mutate(transform)

    def claim_next(self) -> Task | None:
        """原子认领**最老的**待跑任务（待跑 -> 执行中，尝试次数 +1）。

        Returns:
            认领后的任务；无待跑任务时 None
        """
        now = time.time()

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Task] | None:
            for item in items:
                if item.get("status") == TaskStatus.PENDING.value:
                    item["status"] = TaskStatus.RUNNING.value
                    item["attempts"] = int(item.get("attempts", 0)) + 1
                    item["started_at"] = now
                    item["updated_at"] = now
                    return items, Task.from_dict(item)
            return None

        return self._mutate(transform)

    def complete(self, task_id: str, result: Any = None) -> Task | None:
        """完成一个执行中的任务（执行中 -> 成功，记录结果与结束时间）。

        Args:
            task_id: 任务身份
            result: 成功结果

        Returns:
            完成后的任务；任务不存在或状态不是执行中时 None
        """
        now = time.time()

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Task] | None:
            for item in items:
                if item.get("task_id") != task_id:
                    continue
                if item.get("status") != TaskStatus.RUNNING.value:
                    return None
                item["status"] = TaskStatus.SUCCEEDED.value
                item["result"] = result
                item["finished_at"] = now
                item["updated_at"] = now
                return items, Task.from_dict(item)
            return None

        return self._mutate(transform)

    def fail(self, task_id: str, error: Any) -> Task | None:
        """让一个执行中的任务失败（执行中 -> 失败，记录错误与结束时间）。

        Args:
            task_id: 任务身份
            error: 错误信息（转成字符串保存）

        Returns:
            失败后的任务；任务不存在或状态不是执行中时 None
        """
        now = time.time()

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Task] | None:
            for item in items:
                if item.get("task_id") != task_id:
                    continue
                if item.get("status") != TaskStatus.RUNNING.value:
                    return None
                item["status"] = TaskStatus.FAILED.value
                item["error"] = str(error)
                item["finished_at"] = now
                item["updated_at"] = now
                return items, Task.from_dict(item)
            return None

        return self._mutate(transform)

    def requeue(self, task_id: str) -> Task | None:
        """把执行中或失败的任务重新排队回待跑。

        用于进程重启后处理"落盘时处于执行中"的任务（其执行者已不存在、结果不可知）——
        框架 MUST NOT 自动把它改回待跑，由调用方显式决定。尝试次数**不再额外递增**。

        Args:
            task_id: 任务身份

        Returns:
            重新排队后的任务；任务不存在或状态不是执行中 / 失败时 None
        """
        now = time.time()

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], Task] | None:
            for item in items:
                if item.get("task_id") != task_id:
                    continue
                if item.get("status") not in (
                    TaskStatus.RUNNING.value,
                    TaskStatus.FAILED.value,
                ):
                    return None
                item["status"] = TaskStatus.PENDING.value
                item["started_at"] = None
                item["finished_at"] = None
                item["error"] = None
                item["updated_at"] = now
                return items, Task.from_dict(item)
            return None

        return self._mutate(transform)

    def cancel(self, task_id: str) -> bool:
        """取消一个**待跑**任务（待跑 -> 已取消）。

        只对尚未启动的任务生效。对执行中或已终态的任务 MUST NOT 生效（返回 False），
        且框架 MUST NOT 声称取消能中断一个已经开始执行的运行——CPython 无法安全抢占。

        Args:
            task_id: 任务身份

        Returns:
            已取消返回 True；任务不存在或状态不是待跑时 False
        """
        now = time.time()

        def transform(items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool] | None:
            for item in items:
                if item.get("task_id") != task_id:
                    continue
                if item.get("status") != TaskStatus.PENDING.value:
                    return None
                item["status"] = TaskStatus.CANCELLED.value
                item["finished_at"] = now
                item["updated_at"] = now
                return items, True
            return None

        return self._mutate(transform) is True
