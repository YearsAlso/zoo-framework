"""同进程管理器的运行边界：一个进程至多一个**运行态**管理器。

契约见 ``openspec/specs/nested-master-boundary/spec.md``，本模块是它的实现缝。

**为什么这条边界存在**：进程级共享对象使"同进程两个运行态管理器"不成立——
``WorkerRegistry`` 经容器注册为进程级实例，两个管理器会各自遍历**同一份**注册表
并派发同一批同名 Worker；此外部分注册项（``EventRegister`` / ``WaiterResultReactor``）
声明为 ``SINGLE_THREAD``，在**构造期**就把实例绑定到首次解析它的线程。后者今天
抛出的原生报错只有内部注册项名与线程号，指不到病根，故本模块在那个位置**之前**
把病根说清楚（design D3）。

**边界只约束运行态，不约束构造**（design D1）：同线程先后构造多个管理器是既有
契约（``worker-lifecycle`` 的「构造过程可重复」），本模块 MUST NOT 使其失败。

**登记载体由容器的进程级作用域持有**（design D2）：``framework_container().reset()``
会把登记一并清除（下次解析重建），因此测试基座不需要为本状态留容器外的手工复位
条目；MUST NOT 用模块级全局或类属性另存一份——那正是 ``scoped-container`` 的
「登记于容器的进程级管理器 MUST 由容器复位统一承载」禁止的形态。
"""

import threading
from typing import Any

from .container import ThreadSafety, process_scoped

#: 受支持的替代形态：被拒绝者的下一步（文档落点见 ``docs/FAQ.md``）
CROSS_PROCESS_GUIDANCE = (
    "需要多个运行时，请改用独立进程承载（每个进程一个管理器，框架不替你跨进程分派），"
    "或用进程池承载子运行时并让子进程把结果以事件回传。"
    "详见 docs/FAQ.md 的「一个进程能跑多个运行时吗？」"
)


class NestedMasterBoundaryError(ValueError):
    """越过同进程管理器边界时抛出（构造期的跨线程重复构造、运行态的二次进入）。

    继承 ``ValueError``：跨线程构造第二个管理器的原生报错正是 ``ValueError``
    （容器 ``_claim_thread``），沿用该类型使既有捕获写法继续有效。
    """


@process_scoped(thread_safety=ThreadSafety.INSTANCE_GUARANTEED)
class MasterBoundaryRegistry:
    """进程内管理器的登记簿：构造线程与运行态持有者。

    声明为 ``INSTANCE_GUARANTEED`` 要求"实例自己负责"，故实例内部自带互斥
    （见 ``scoped-container`` 的「线程安全归属声明 MUST 与实例实际行为相符」）。
    """

    def __init__(self) -> None:
        """构造空的登记簿：既无管理器，也无运行态持有者。"""
        self._lock = threading.RLock()
        self._construction_thread: int | None = None
        self._active: Any | None = None

    def note_construction(self) -> None:
        """记录本进程首个管理器的构造线程；当前线程不同即拒绝并指明病根。

        由 ``Master.__init__`` 在**解析任何进程级共享对象之前**调用（design D3）：
        若不前置，跨线程构造会先撞上容器内部某个 ``SINGLE_THREAD`` 注册项的
        线程归属报错——那条报错对本进程所有此类注册项都正确（故不改它），
        但它指不到"同进程放了两个管理器"这一病根。

        Raises:
            NestedMasterBoundaryError: 本进程已有管理器，且当前线程不是它的构造线程
        """
        current = threading.get_ident()
        with self._lock:
            owner = self._construction_thread
            if owner is None:
                # 首个管理器：记录构造线程。同线程再构造不重复判定，故可重复构造
                self._construction_thread = current
                return
        if owner != current:
            raise NestedMasterBoundaryError(
                f"同一个进程内至多允许一个框架管理器：本进程的管理器构造于线程 {owner}，"
                f"当前线程 {current} 不能构造第二个——这是同进程边界问题，"
                f"不是容器某个注册项的线程归属问题。{CROSS_PROCESS_GUIDANCE}"
            )

    def active_master(self) -> Any | None:
        """当前处于运行态的管理器；没有则为 None。"""
        with self._lock:
            return self._active

    def claim_runtime(self, master: Any) -> None:
        """让 ``master`` 进入运行态；已被别的管理器占用时拒绝。

        由 ``Master.run()`` 在创建事件循环、派发任何 Worker **之前**调用，故被拒
        的请求不产生第二轮派发（规格「拒绝 MUST 发生在真正开始派发之前」）。

        Args:
            master: 请求进入运行态的管理器

        Raises:
            NestedMasterBoundaryError: 本进程已有另一个处于运行态的管理器
        """
        with self._lock:
            holder = self._active
            if holder is not None and holder is not master:
                raise NestedMasterBoundaryError(
                    "同一个进程内至多允许一个处于运行态的框架管理器：已有管理器正在运行，"
                    "第二个管理器的进入运行请求被拒绝——这是同进程边界问题，"
                    f"且本次请求在产生任何派发之前就被拒绝。{CROSS_PROCESS_GUIDANCE}"
                )
            self._active = master

    def release_runtime(self, master: Any) -> None:
        """归还运行态名额；只有持有者本人能归还，且可重复调用。

        Args:
            master: 请求归还名额的管理器；不是当前持有者时什么也不做
        """
        with self._lock:
            if self._active is master:
                self._active = None


def master_boundary() -> MasterBoundaryRegistry:
    """取本进程的管理器边界登记簿（经容器解析，故容器 ``reset()`` 即可清除）。"""
    return MasterBoundaryRegistry()
