"""线程安全归属声明。

跨 Worker 共享可变对象是并发的脚枪，而 ``@cage`` 现状对此**完全沉默**——它共享的却
正是有状态的 manager。因此本容器把归属作为**注册必填声明**：不给隐式默认值，因为
隐式默认一个安全假设正是这类缺陷的温床。

三种取值（见 design D5）：

- ``CONTAINER_SERIALIZED``：由容器保证串行访问。适合自身不加锁、但可接受串行的项
- ``INSTANCE_GUARANTEED``：由实例自身保证。适合不可变、或内部自带锁的项
- ``SINGLE_THREAD``：仅限单线程作用域使用。用于既不串行也不自保的项

声明是**如实**的断言，不是让容器替实例兜底：把 ``INSTANCE_GUARANTEED`` 写在一个
没有锁的可变对象上，等于把未验证的安全假设写进代码，比不写更糟。
"""


class ThreadSafety:
    """线程安全归属的合法取值."""

    CONTAINER_SERIALIZED = "container_serialized"
    INSTANCE_GUARANTEED = "instance_guaranteed"
    SINGLE_THREAD = "single_thread"

    ALL = (CONTAINER_SERIALIZED, INSTANCE_GUARANTEED, SINGLE_THREAD)

    DESCRIPTIONS = {
        CONTAINER_SERIALIZED: "由容器保证串行访问",
        INSTANCE_GUARANTEED: "由实例自身保证",
        SINGLE_THREAD: "仅限单线程作用域使用",
    }

    @classmethod
    def describe(cls, value: str) -> str:
        """取该取值的说明文字；未知取值返回原值."""
        return cls.DESCRIPTIONS.get(value, str(value))
