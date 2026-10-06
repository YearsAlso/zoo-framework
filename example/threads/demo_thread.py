import weakref
from time import sleep

from zoo_framework.core.aop import logger
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.utils import LogUtils
from zoo_framework.workers import BaseWorker


# 历史上的 `@worker(count=20)` 已随 cleanup-aop-public-surface（#49）判废：它把实例
# 写进不被 Master 读取的 legacy 表，注册 20 个也从不被派发。现在的接通路径是
# `example/main.py` 里的 `master.register_worker("TestThread", DemoThread)`。
@logger
class DemoThread(BaseWorker):
    """Demo Worker - 修复内存泄漏版本

    修复内容：
    1. 使用弱引用避免循环引用
    2. 正确移除状态观察者
    3. 限制状态历史记录大小
    """

    def __init__(self):
        # is_loop 由 BaseWorker 以**只读属性**暴露、并以 _props 为唯一真源
        # （见 base_worker.py 的类 docstring：子类 MUST NOT 用实例属性遮蔽它）。
        # 原先这里在 __init__ 里写 `self.is_loop = True`，给一个无 setter 的 property
        # 赋值会抛 AttributeError —— 故循环标志改为在 _props 里声明。
        BaseWorker.__init__(self, {"is_loop": True, "delay_time": 1, "name": "TestThread"})
        self.i = 0
        self.state_machine_manager = StateMachineManager()

        # 使用弱引用存储回调，避免循环引用
        self._observer_ref = None

        # 限制状态变化历史记录大小
        self._max_history_size = 100
        self._state_history = []

    @classmethod
    def _on_test_number_change(cls, data):
        """状态变化回调（类方法避免实例引用）"""
        value = data.get("value")
        version = data.get("version")
        cls._logger.debug("Test", f"[{version}] Test number change to {value}")

    def _on_create(self):
        """创建时初始化状态"""
        # 设置初始状态
        StateMachineManager().set_state("TestScope", "Test.number", 0)

        # 使用弱引用包装回调
        self._observer_ref = weakref.ref(self._on_test_number_change)

        # 注册状态观察者
        StateMachineManager().observe_state("TestScope", "Test.number", self._on_test_number_change)

    def _destroy(self, result):
        """销毁时清理资源 - 修复内存泄漏"""
        # 移除状态观察者
        try:
            StateMachineManager().unobserve_state(
                "TestScope", "Test.number", self._on_test_number_change
            )
            LogUtils.info("✅ State observer removed successfully")
        except Exception as e:
            LogUtils.warning(f"⚠️ Failed to remove state observer: {e}")

        # 清理历史记录
        self._state_history.clear()
        self._observer_ref = None

        LogUtils.info("🧹 Resources cleaned up")

    def _execute(self):
        """执行任务 - 修复内存泄漏"""
        self._logger.debug("Test")

        # 获取当前状态（不持有长期引用）
        try:
            i = StateMachineManager().get_state("TestScope", "Test.number")
            self._logger.info(f"Test get i:[{i}], self.i:[{self.i}]")

            # 更新状态
            new_value = i + 1
            StateMachineManager().set_state("TestScope", "Test.number", new_value)

            # 记录状态变化历史（限制大小）
            self._record_state_change(i, new_value)

        except Exception as e:
            LogUtils.error(f"❌ Error accessing state: {e}")

        self.i += 1
        sleep(1)

    def _record_state_change(self, old_value, new_value):
        """记录状态变化（限制内存使用）

        Args:
            old_value: 旧值
            new_value: 新值
        """
        from datetime import datetime

        # 添加新记录
        self._state_history.append(
            {
                "timestamp": datetime.now().isoformat(),
                "old_value": old_value,
                "new_value": new_value,
            }
        )

        # 限制历史记录大小，防止内存无限增长
        if len(self._state_history) > self._max_history_size:
            # 移除最旧的记录
            self._state_history.pop(0)
