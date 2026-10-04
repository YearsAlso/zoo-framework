"""作用域表达。

作用域是"跨 Worker 复用同一个对象"的边界：同一作用域内同一注册项解析到同一实例，
不同作用域解析到不同实例。之所以需要它，是因为**进程级全局单例**在多会话场景下是
错的——两个用户的 agent 会共享同一个工具客户端（串会话数据），两台设备会共享同一个
连接句柄（写错设备）。

作用域以**显式句柄**表达（见 design D3）。调用方传入句柄，MUST NOT 从上下文变量隐式
读取：`ThreadPoolExecutor` 提交的任务不继承调用方的上下文变量，隐式读取一旦落空，
后果不是"丢标识"而是**取到别的会话的对象**，且是静默的。

三种作用域：

- 进程级：全进程唯一，跨会话仍是同一实例
- 会话级：每个会话一个；会话边界由 ``core/run_identity`` 的会话标识承载
- 原型级：每次解析都新建，不缓存
"""

from typing import Any

PROCESS_SCOPE_KEY = ("process",)


class ScopeKind:
    """作用域种类."""

    PROCESS = "process"
    SESSION = "session"
    PROTOTYPE = "prototype"

    ALL = (PROCESS, SESSION, PROTOTYPE)


class Scope:
    """作用域句柄.

    句柄是不可变的标识，可安全地跨线程传递；它**不**携带实例缓存——缓存归容器所有。

    Attributes:
        kind: 作用域种类，取值见 ``ScopeKind``
        session_id: 会话标识；仅会话级作用域携带，其余为 None
    """

    __slots__ = ("kind", "session_id")

    def __init__(self, kind: str, session_id: str | None = None):
        """构造作用域句柄。

        Args:
            kind: 作用域种类
            session_id: 会话标识；仅会话级需要

        Raises:
            ValueError: 种类无法识别，或会话标识与种类不匹配（缺或多）
        """
        if kind not in ScopeKind.ALL:
            raise ValueError(f"无法识别的作用域 {kind!r}；可选 {list(ScopeKind.ALL)}")

        # 会话级没有会话标识就无从区分会话，缓存会退化成进程级——这是静默的语义降级，
        # 故在此明确拒绝，而不是补一个默认标识
        if kind == ScopeKind.SESSION and not session_id:
            raise ValueError("会话级作用域必须携带会话标识")

        # 非会话级带上会话标识，说明调用方以为自己在隔离而实际没有，同样明确拒绝
        if kind != ScopeKind.SESSION and session_id is not None:
            raise ValueError(f"{kind} 作用域不接受会话标识，收到 {session_id!r}")

        self.kind = kind
        self.session_id = session_id

    @classmethod
    def process(cls) -> "Scope":
        """进程级作用域句柄."""
        return cls(ScopeKind.PROCESS)

    @classmethod
    def session(cls, session_id: str) -> "Scope":
        """会话级作用域句柄.

        Args:
            session_id: 会话标识，通常取自 ``RunIdentity.session_id``
        """
        return cls(ScopeKind.SESSION, session_id)

    @classmethod
    def prototype(cls) -> "Scope":
        """原型级作用域句柄（每次解析新建）."""
        return cls(ScopeKind.PROTOTYPE)

    @classmethod
    def of(cls, identity: Any) -> "Scope":
        """由运行标识派生会话作用域.

        这是**显式**调用：句柄仍由调用方传入容器，只是省去了手工取 ``session_id``。
        标识为 None 时明确拒绝，而不是退回进程级——那会静默地把两个会话合成一个。

        Args:
            identity: ``RunIdentity`` 实例

        Raises:
            ValueError: 标识为 None 或缺少会话标识
        """
        if identity is None:
            raise ValueError("无运行标识，无法派生会话作用域（MUST NOT 静默退回进程级）")
        session_id = getattr(identity, "session_id", None)
        if not session_id:
            raise ValueError(f"运行标识 {identity!r} 不带会话标识，无法派生会话作用域")
        return cls.session(session_id)

    @property
    def cache_key(self) -> tuple | None:
        """该作用域的缓存主体；原型级不缓存，返回 None."""
        if self.kind == ScopeKind.PROTOTYPE:
            return None
        if self.kind == ScopeKind.PROCESS:
            return PROCESS_SCOPE_KEY
        return ("session", self.session_id)

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Scope):
            return NotImplemented
        return (self.kind, self.session_id) == (other.kind, other.session_id)

    def __hash__(self) -> int:
        return hash((self.kind, self.session_id))

    def __repr__(self) -> str:
        if self.kind == ScopeKind.SESSION:
            return f"Scope(session={self.session_id!r})"
        return f"Scope({self.kind})"
