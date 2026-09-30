"""运行标识：区分「一次运行」与「一个会话」，并使其贯穿事件、状态与日志.

两级标识：

- **运行标识** ``run_id``——标识一次逻辑运行，每次运行唯一、运行期间不变
- **会话标识** ``session_id``——标识会话或上下文归属，同一会话可包含多次运行

传播契约（与 design 的 D3 一致，也是本模块存在的理由）：

- **显式字段是真相来源**：``WorkerResult``、``EventNode`` 等载体各自持有显式字段，
  不依赖隐式上下文即可读取与按标识筛选
- 上下文变量只是**便利读法**，且 MUST NOT 假定它会跨线程自动生效——
  ``ThreadPoolExecutor`` 提交的任务与新建线程**都不会继承**调用方的 ``ContextVar``。
  因此跨线程派发 MUST 经 :func:`carry_context`，由它显式复制上下文后执行。

若只依赖上下文变量而不复制，标识会在派发到工作线程时**静默丢失**：拿到的是
``None`` 或（更糟）别处绑定的值，而两者都不会报错。
"""

import contextvars
import uuid
from collections.abc import Callable
from contextlib import contextmanager
from typing import Any


class RunIdentity:
    """一次运行的标识：运行标识 + 会话标识."""

    __slots__ = ("run_id", "session_id")

    def __init__(self, run_id: str, session_id: str):
        self.run_id = run_id
        self.session_id = session_id

    def __repr__(self) -> str:
        return f"RunIdentity(run_id={self.run_id!r}, session_id={self.session_id!r})"

    def __eq__(self, other) -> bool:
        return (
            isinstance(other, RunIdentity)
            and self.run_id == other.run_id
            and self.session_id == other.session_id
        )

    def __hash__(self) -> int:
        return hash((self.run_id, self.session_id))

    @classmethod
    def start(cls, session_id: str | None = None) -> "RunIdentity":
        """生成一次新的运行标识.

        Args:
            session_id: 所属会话；None 表示同时开启一个新会话

        Returns:
            新的运行标识。同一会话的多次运行共享 ``session_id``，而 ``run_id`` 各不相同
        """
        return cls(run_id=uuid.uuid4().hex, session_id=session_id or uuid.uuid4().hex)

    @contextmanager
    def bind(self):
        """把本标识绑定为当前上下文，退出时恢复原状."""
        token = _CURRENT_IDENTITY.set(self)
        try:
            yield self
        finally:
            _CURRENT_IDENTITY.reset(token)


_CURRENT_IDENTITY: contextvars.ContextVar[RunIdentity | None] = contextvars.ContextVar(
    "zoo_run_identity", default=None
)


def current_identity() -> RunIdentity | None:
    """读取当前上下文绑定的运行标识；未绑定返回 None."""
    return _CURRENT_IDENTITY.get()


def current_run_id() -> str | None:
    """当前运行标识的 ``run_id``；未绑定返回 None."""
    identity = current_identity()
    return identity.run_id if identity else None


def current_session_id() -> str | None:
    """当前运行标识的 ``session_id``；未绑定返回 None."""
    identity = current_identity()
    return identity.session_id if identity else None


def carry_context(func: Callable[..., Any]) -> Callable[..., Any]:
    """把 ``func`` 包成「连同调用方上下文一起执行」的可调用对象.

    新建线程与线程池任务都不会继承调用方的 ``ContextVar``，因此工作线程里的执行体
    与完成收口都 MUST 经由此包装执行，否则运行标识会在派发时静默丢失。

    Returns:
        包装后的可调用对象；每次调用都在**创建包装时**捕获的那份上下文副本里执行
    """
    ctx = contextvars.copy_context()

    def _carried(*args: Any, **kwargs: Any) -> Any:
        return ctx.run(func, *args, **kwargs)

    return _carried
