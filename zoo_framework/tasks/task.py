"""任务值对象：与 Worker 解耦的任务身份、状态与生命周期。

变更 add-task-layer（GitHub issue #234 形状 1）：框架的执行单元原是 ``Worker``——一个
**有名字的长期槽位**（名字即身份），没有承载"一批活"的实体。本模块提供语言无关的任务
值对象：身份、载荷、状态、尝试次数、结果 / 错误与时间戳；**身份由调用方给定，与 Worker
名字无绑定关系**，同一 Worker 可消费任意身份的任务。

本模块只定义**值**（可构造、可序列化、无副作用）。状态迁移的合法性与原子性判定在
``task_queue`` 中与"读-改-写"同处一个临界区（见变更 design.md 的 D2）——把判定放在
``Task`` 上会诱使调用方在临界区外改状态。
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class TaskStatus(StrEnum):
    """任务状态。

    用 ``str`` 子类枚举（Python 3.11+，与项目下界一致）使成员**等同其字面值**
    （``TaskStatus.PENDING == "pending"``），便于持久化与比较。
    """

    PENDING = "pending"  # 待跑
    RUNNING = "running"  # 执行中
    SUCCEEDED = "succeeded"  # 成功
    FAILED = "failed"  # 失败
    CANCELLED = "cancelled"  # 已取消


@dataclass
class Task:
    """任务值对象（身份与 Worker 解耦）。

    字段覆盖 issue #234 形状 1 的建议形状：``task_id``（身份）、``payload``（载荷）、
    ``status``（状态）、``attempts``（尝试次数）、``result`` / ``error``（结果 / 错误）
    与时间戳（``created_at`` / ``updated_at`` / ``started_at`` / ``finished_at``）。

    时间戳取**墙钟** ``time.time()``：它们要跨进程重启表达"何时创建 / 何时开始"，
    ``time.monotonic()`` 跨进程无意义。这与 ``WorkerDispatchCore`` 的单调时钟契约互不
    影响——任务层不触碰调度器。

    Attributes:
        task_id: 任务身份（调用方给定，队列内唯一）
        payload: 载荷（任务体入参）
        status: 状态，见 ``TaskStatus``
        attempts: 尝试次数（每次认领 +1）
        result: 成功时的结果
        error: 失败时的错误信息
        created_at: 创建时间（墙钟秒）
        updated_at: 最近更新时间（墙钟秒）
        started_at: 最近一次开始执行的时间；未开始为 None
        finished_at: 结束时间（成功 / 失败 / 取消）；未结束为 None
    """

    task_id: str
    payload: Any = None
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = 0
    result: Any = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started_at: float | None = None
    finished_at: float | None = None

    def __post_init__(self) -> None:
        """把状态归一为 ``TaskStatus``（便于以字面量构造）。

        ``TaskStatus(成员)`` 返回该成员自身、``TaskStatus("pending")`` 返回对应成员，
        故对已是 ``TaskStatus`` 的入参是幂等的。传未知字面量时这里抛 ``ValueError``。
        """
        self.status = TaskStatus(self.status)

    @classmethod
    def new(cls, payload: Any = None, task_id: str | None = None) -> Task:
        """创建一个新任务（身份缺省时自动生成）。

        Args:
            payload: 载荷
            task_id: 任务身份；None 时用 ``uuid4().hex`` 生成

        Returns:
            处于待跑状态、尝试次数为 0 的新任务
        """
        return cls(task_id=task_id if task_id is not None else uuid.uuid4().hex, payload=payload)

    def to_dict(self) -> dict[str, Any]:
        """序列化为持久化用的普通字典（状态存其字面值）。

        Returns:
            可直接落进状态机节点的任务字典
        """
        return {
            "task_id": self.task_id,
            "payload": self.payload,
            "status": str(self.status),
            "attempts": self.attempts,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Task:
        """从持久化字典还原任务。

        Args:
            data: ``to_dict`` 产出的字典

        Returns:
            还原出的任务

        Raises:
            ValueError: ``status`` 不是已知状态字面量（显式失败，不静默退化）
            KeyError: 缺少必需字段（``task_id`` / ``status`` / 时间戳）
        """
        return cls(
            task_id=data["task_id"],
            payload=data.get("payload"),
            status=TaskStatus(data["status"]),
            attempts=data.get("attempts", 0),
            result=data.get("result"),
            error=data.get("error"),
            created_at=data["created_at"],
            updated_at=data["updated_at"],
            started_at=data.get("started_at"),
            finished_at=data.get("finished_at"),
        )
