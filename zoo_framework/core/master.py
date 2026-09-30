"""Master - 优化版本.

P2 优化：
1. 移除冗余参数 loop_interval
2. 使用新的 WorkerRegistry
3. 简化配置加载
4. 优化 SVM 集成
"""

import asyncio
import threading
from typing import Any

from zoo_framework.utils import LogUtils
from zoo_framework.workers import EventWorker, StateMachineWorker

from .aop import config_funcs
from .params_factory import ParamsFactory
from .worker_registry import get_worker_registry


class SVMWorker:
    """SVM (State Vector Machine) Worker - 状态向量机工作器."""

    def __init__(self, check_interval: float = 10):
        self._workers: dict[str, Any] = {}
        self._metrics: dict[str, dict] = {}
        self._policies: list[str] = []
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: threading.Thread | None = None
        self._check_interval = check_interval
        # 用可唤醒的等待替代 sleep：否则停机时要等满一个检查周期，最长 check_interval 秒
        self._stop_event = threading.Event()

    def register_worker(self, name: str, worker: Any) -> None:
        """注册 Worker 到 SVM 管理."""
        with self._lock:
            self._workers[name] = worker
            self._metrics[name] = {
                "execute_count": 0,
                "error_count": 0,
                "total_execute_time": 0.0,
                "last_execute_time": 0.0,
                "status": "running",
            }
            LogUtils.info(f"✅ Worker '{name}' registered to SVM")

    def unregister_worker(self, name: str) -> None:
        """从 SVM 管理移除 Worker."""
        with self._lock:
            self._workers.pop(name, None)
            self._metrics.pop(name, None)
            LogUtils.info(f"🗑️ Worker '{name}' unregistered from SVM")

    def record_execute(self, name: str, duration: float, success: bool = True) -> None:
        """记录 Worker 执行指标."""
        with self._lock:
            if name not in self._metrics:
                return

            metrics = self._metrics[name]
            metrics["execute_count"] += 1
            metrics["total_execute_time"] += duration
            metrics["last_execute_time"] = duration

            if not success:
                metrics["error_count"] += 1

    def get_worker_health(self, name: str) -> dict:
        """获取 Worker 健康状态."""
        with self._lock:
            if name not in self._metrics:
                return {"status": "unknown"}

            metrics = self._metrics[name]
            execute_count = metrics["execute_count"]
            error_count = metrics["error_count"]

            if execute_count == 0:
                health_score = 100
            else:
                error_rate = error_count / execute_count
                health_score = max(0, int((1 - error_rate) * 100))

            avg_time = metrics["total_execute_time"] / execute_count if execute_count > 0 else 0

            return {
                "status": metrics["status"],
                "health_score": health_score,
                "execute_count": execute_count,
                "error_count": error_count,
                "error_rate": error_count / execute_count if execute_count > 0 else 0,
                "avg_execute_time": avg_time,
                "last_execute_time": metrics["last_execute_time"],
            }

    def get_all_workers_health(self) -> dict[str, dict]:
        """获取所有 Worker 健康状态."""
        with self._lock:
            return {name: self.get_worker_health(name) for name in self._workers}

    def start_monitoring(self) -> None:
        """启动监控线程."""
        if self._running:
            return

        self._stop_event.clear()
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, name="zoo-svm")
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        LogUtils.info("🔍 SVM monitoring started")

    def stop_monitoring(self) -> None:
        """停止监控线程.

        通过事件唤醒监控循环，使停机不必等满一个检查周期。
        """
        self._running = False
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        LogUtils.info("🛑 SVM monitoring stopped")

    def _monitor_loop(self) -> None:
        """监控循环."""
        while self._running:
            try:
                self._check_workers_health()
            except Exception as e:
                LogUtils.error(f"❌ SVM monitor error: {e}")

            # 可被停机唤醒的等待
            if self._stop_event.wait(self._check_interval):
                break

    def _check_workers_health(self) -> None:
        """检查所有 Worker 健康状态."""
        with self._lock:
            for name, metrics in self._metrics.items():
                execute_count = metrics["execute_count"]
                error_count = metrics["error_count"]

                if execute_count == 0:
                    continue

                error_rate = error_count / execute_count

                if error_rate > 0.5 and execute_count > 10:
                    metrics["status"] = "unhealthy"
                    LogUtils.warning(f"⚠️ Worker '{name}' is unhealthy")
                elif error_rate > 0.2 and execute_count > 10:
                    metrics["status"] = "warning"
                    LogUtils.warning(f"⚠️ Worker '{name}' has warnings")
                else:
                    metrics["status"] = "running"


class MasterConfig:
    """Master 配置类.

    P2 优化：将配置集中管理
    """

    def __init__(
        self,
        config_path: str = "./config.json",
        enable_svm: bool = True,
        svm_check_interval: int = 10,
        auto_save_interval: int = 60,
    ):
        self.config_path = config_path
        self.enable_svm = enable_svm
        self.svm_check_interval = svm_check_interval
        self.auto_save_interval = auto_save_interval


class Master:
    """Master - 动物园园长.

    P2 优化版本：
    - 移除冗余的 loop_interval 参数
    - 使用 WorkerRegistry 管理 Worker
    - 简化配置
    - 集成 SVM 监控

    Attributes:
        config: Master 配置
        worker_registry: Worker 注册表
        svm_worker: SVM 监控 Worker
        waiter: Waiter 调度器
    """

    def __init__(self, config: MasterConfig | None = None):
        """初始化 Master.

        P2 优化：简化参数，使用配置对象

        Args:
            config: Master 配置，使用默认配置如果为 None
        """
        # P2 优化：使用配置对象
        self.config = config or MasterConfig()

        # P2 优化：使用新的 WorkerRegistry
        self.worker_registry = get_worker_registry()

        # 调度主循环的运行时句柄
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task | None = None
        self._shutdown_done = False

        # 加载配置
        ParamsFactory(self.config.config_path)
        self._load_config()

        # P2 优化：简化 Worker 注册
        self._register_default_workers()

        # SVM Worker 集成
        # svm_check_interval 此前是声明了但从未被读取的配置项，此处真正生效
        self.svm_worker = (
            SVMWorker(self.config.svm_check_interval) if self.config.enable_svm else None
        )
        if self.svm_worker:
            self._setup_svm()

        # 创建 Waiter
        self._create_waiter()

    def _load_config(self) -> None:
        """加载配置."""
        for value in config_funcs.values():
            value()

    def _register_default_workers(self) -> None:
        """注册默认 Worker.

        P2 优化：使用 WorkerRegistry 注册
        """
        # 使用延迟实例化
        self.worker_registry.register_class(
            "StateMachineWorker",
            StateMachineWorker,
            metadata={"priority": 100, "tags": ["system", "persistence"]},
        )
        self.worker_registry.register_class(
            "EventWorker", EventWorker, metadata={"priority": 50, "tags": ["system", "event"]}
        )

    def _setup_svm(self) -> None:
        """设置 SVM 监控."""
        # 注册所有 Worker 到 SVM
        for name, worker in self.worker_registry.get_all_workers().items():
            self.svm_worker.register_worker(name, worker)

        # 启动监控
        self.svm_worker.start_monitoring()
        LogUtils.info("✅ SVM Worker setup completed")

    def _create_waiter(self) -> None:
        """创建 Waiter.

        调度器按**调度模型名**装配（模型名由 ``worker:mode`` 决定，未配置时由
        ``worker:pool:enable`` 推导）；无法识别的模型名会被明确拒绝。
        """
        from zoo_framework.core.waiter import WaiterFactory

        self.waiter = WaiterFactory.get_waiter()

        # 将 Worker 传递给 Waiter
        self.waiter.call_workers(list(self.worker_registry.get_all_workers().values()))

    def change_waiter(self, waiter) -> None:
        """切换 Waiter.

        Args:
            waiter: 新的 Waiter 实例
        """
        if self.waiter is not None:
            raise Exception("Waiter already exists, cannot change")
        self.waiter = waiter

    def register_worker(self, name: str, worker_class: type, metadata: dict | None = None) -> None:
        """注册 Worker.

        P2 优化：提供简洁的注册接口

        Args:
            name: Worker 名称
            worker_class: Worker 类
            metadata: 元数据
        """
        self.worker_registry.register_class(name, worker_class, metadata)

        # 调度列表由 Waiter 持有：只在注册表登记不会让 Worker 被派发，
        # 必须同步加入调度，否则运行期注册的 Worker 永远不会执行。
        worker = self.worker_registry.get_worker(name)
        if worker is None:
            return

        self.waiter.add_worker(worker)

        # 如果 SVM 已启用，注册到 SVM
        if self.svm_worker:
            self.svm_worker.register_worker(name, worker)

    async def perform(self) -> None:
        """执行任务主循环."""
        while True:
            self.waiter.execute_service()
            # P2 优化：使用配置中的间隔
            await asyncio.sleep(1)

    def run(self) -> None:
        """运行 Master."""
        try:
            LogUtils.info("🎪 Master started, zoo is open!")
            # 显式新建事件循环：asyncio.get_event_loop() 在无运行循环时已弃用，
            # 且会复用上一个循环，使重复启动的 Master 相互干扰。
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop

            self._task = loop.create_task(self.perform())
            # 调度任务抛异常时必须可见并停止主循环；否则 run_forever() 会持续空转，
            # 而调度其实早已停止——表现为进程活着但什么都不做。
            self._task.add_done_callback(self._on_schedule_task_done)

            loop.run_forever()
        except KeyboardInterrupt:
            LogUtils.info("🛑 Master stopping...")
        finally:
            self.shutdown()

    def _on_schedule_task_done(self, task: asyncio.Task) -> None:
        """调度主循环结束时的收口：异常可见，并停止事件循环。

        Args:
            task: 调度任务
        """
        if task.cancelled():
            return

        error = task.exception()
        if error is not None:
            LogUtils.error(f"❌ 调度主循环异常终止: {error!r}")

        # 用 call_soon_threadsafe 以便本回调无论从哪个线程触发都能安全停止循环
        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

    def shutdown(self) -> None:
        """优雅关闭 Master.

        顺序：先停调度（不再派发）→ 取消调度任务 → 停事件循环 → 停监控 →
        注销 Worker（触发其销毁钩子，状态机在此落盘）。MUST 可重复调用。
        """
        if self._shutdown_done:
            return
        self._shutdown_done = True

        LogUtils.info("🧹 Shutting down Master...")

        # 先停调度器：停机过程中 MUST NOT 再派发新的 Worker
        if getattr(self, "waiter", None) is not None:
            self.waiter.shutdown()

        task = self._task
        self._task = None
        if task is not None and not task.done():
            task.cancel()

        loop = self._loop
        if loop is not None and loop.is_running():
            loop.call_soon_threadsafe(loop.stop)

        # 停止 SVM 监控
        if self.svm_worker:
            self.svm_worker.stop_monitoring()

        # 注销已注册的 Worker：WorkerRegistry.unregister 会调用其销毁钩子，
        # 状态机 Worker 的最后一次落盘发生在这里。
        registry = getattr(self, "worker_registry", None)
        if registry is not None:
            for name in list(registry.get_all_workers().keys()):
                registry.unregister(name)

        LogUtils.info("👋 Master stopped")

    def get_health_report(self) -> dict[str, dict]:
        """获取健康报告.

        Returns:
            所有 Worker 的健康状态
        """
        if self.svm_worker:
            return self.svm_worker.get_all_workers_health()
        return {}

    def get_worker_stats(self, worker_name: str) -> dict | None:
        """获取 Worker 统计信息.

        Args:
            worker_name: Worker 名称

        Returns:
            统计信息字典
        """
        worker = self.worker_registry.get_worker(worker_name)
        if worker is None:
            return None

        metadata = self.worker_registry.get_metadata(worker_name) or {}
        health = self.svm_worker.get_worker_health(worker_name) if self.svm_worker else {}

        return {
            "name": worker_name,
            "type": type(worker).__name__,
            "metadata": metadata,
            "health": health,
        }


# 便捷函数
def create_master(config_path: str = "./config.json", enable_svm: bool = True) -> Master:
    """创建 Master 实例.

    P2 优化：提供简洁的创建接口

    Args:
        config_path: 配置文件路径
        enable_svm: 是否启用 SVM 监控

    Returns:
        Master 实例
    """
    config = MasterConfig(config_path=config_path, enable_svm=enable_svm)
    return Master(config)
