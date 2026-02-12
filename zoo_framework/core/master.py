# -*- coding: utf-8 -*-
import asyncio
import threading
from typing import Dict, List, Optional, Any

from zoo_framework.workers import EventWorker
from zoo_framework.workers import StateMachineWorker
from zoo_framework.utils import LogUtils

from .aop import worker_register, config_funcs
from .params_factory import ParamsFactory


class SVMWorker:
    """SVM (State Vector Machine) Worker - 状态向量机工作器
    
    SVM Worker 是一种特殊的 Worker，用于管理 Worker 的状态向量。
    它可以监控 Worker 的健康状态、性能指标，并根据策略进行调整。
    
    特性：
    - 监控 Worker 运行状态
    - 收集性能指标（执行时间、错误率等）
    - 动态调整 Worker 参数
    - 自动故障恢复
    
    Attributes:
        workers: 被管理的 Worker 字典
        metrics: Worker 性能指标
        policies: 管理策略
    """
    
    def __init__(self):
        self._workers: Dict[str, Any] = {}
        self._metrics: Dict[str, Dict] = {}
        self._policies: List[str] = []
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
    
    def register_worker(self, name: str, worker: Any) -> None:
        """注册 Worker 到 SVM 管理
        
        Args:
            name: Worker 名称
            worker: Worker 实例
        """
        with self._lock:
            self._workers[name] = worker
            self._metrics[name] = {
                'execute_count': 0,
                'error_count': 0,
                'total_execute_time': 0.0,
                'last_execute_time': 0.0,
                'status': 'running'
            }
            LogUtils.info(f"✅ Worker '{name}' registered to SVM")
    
    def unregister_worker(self, name: str) -> None:
        """从 SVM 管理移除 Worker
        
        Args:
            name: Worker 名称
        """
        with self._lock:
            self._workers.pop(name, None)
            self._metrics.pop(name, None)
            LogUtils.info(f"🗑️ Worker '{name}' unregistered from SVM")
    
    def record_execute(self, name: str, duration: float, success: bool = True) -> None:
        """记录 Worker 执行指标
        
        Args:
            name: Worker 名称
            duration: 执行耗时
            success: 是否成功
        """
        with self._lock:
            if name not in self._metrics:
                return
            
            metrics = self._metrics[name]
            metrics['execute_count'] += 1
            metrics['total_execute_time'] += duration
            metrics['last_execute_time'] = duration
            
            if not success:
                metrics['error_count'] += 1
    
    def get_worker_health(self, name: str) -> Dict:
        """获取 Worker 健康状态
        
        Args:
            name: Worker 名称
            
        Returns:
            健康状态字典
        """
        with self._lock:
            if name not in self._metrics:
                return {'status': 'unknown'}
            
            metrics = self._metrics[name]
            execute_count = metrics['execute_count']
            error_count = metrics['error_count']
            
            # 计算健康度
            if execute_count == 0:
                health_score = 100
            else:
                error_rate = error_count / execute_count
                health_score = max(0, int((1 - error_rate) * 100))
            
            # 计算平均执行时间
            avg_time = (metrics['total_execute_time'] / execute_count 
                       if execute_count > 0 else 0)
            
            return {
                'status': metrics['status'],
                'health_score': health_score,
                'execute_count': execute_count,
                'error_count': error_count,
                'error_rate': error_count / execute_count if execute_count > 0 else 0,
                'avg_execute_time': avg_time,
                'last_execute_time': metrics['last_execute_time']
            }
    
    def get_all_workers_health(self) -> Dict[str, Dict]:
        """获取所有 Worker 健康状态
        
        Returns:
            Worker 健康状态字典
        """
        with self._lock:
            return {name: self.get_worker_health(name) 
                    for name in self._workers.keys()}
    
    def start_monitoring(self) -> None:
        """启动监控线程"""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop)
        self._monitor_thread.daemon = True
        self._monitor_thread.start()
        LogUtils.info("🔍 SVM monitoring started")
    
    def stop_monitoring(self) -> None:
        """停止监控线程"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        LogUtils.info("🛑 SVM monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """监控循环"""
        import time
        while self._running:
            try:
                self._check_workers_health()
                time.sleep(10)  # 每 10 秒检查一次
            except Exception as e:
                LogUtils.error(f"❌ SVM monitor error: {e}")
                time.sleep(5)
    
    def _check_workers_health(self) -> None:
        """检查所有 Worker 健康状态"""
        with self._lock:
            for name, metrics in self._metrics.items():
                execute_count = metrics['execute_count']
                error_count = metrics['error_count']
                
                if execute_count == 0:
                    continue
                
                error_rate = error_count / execute_count
                
                # 如果错误率超过 50%，标记为不健康
                if error_rate > 0.5 and execute_count > 10:
                    metrics['status'] = 'unhealthy'
                    LogUtils.warning(f"⚠️ Worker '{name}' is unhealthy (error rate: {error_rate:.2%})")
                # 如果错误率超过 20%，标记为警告
                elif error_rate > 0.2 and execute_count > 10:
                    metrics['status'] = 'warning'
                    LogUtils.warning(f"⚠️ Worker '{name}' has warnings (error rate: {error_rate:.2%})")
                else:
                    metrics['status'] = 'running'


class Master(object):
    def __init__(self, loop_interval=1):
        # TODO: 创建各类注册器
        # TODO: loop_interval 这个参数有些多余，可以考虑去掉
        from zoo_framework.core.waiter import WaiterFactory
        # load params
        ParamsFactory("./config.json")
        self.config()

        from zoo_framework.params import WorkerParams
        self.worker_register = worker_register
        self.worker_register.register(StateMachineWorker.__name__, StateMachineWorker())
        self.worker_register.register(EventWorker.__name__, EventWorker())

        # TODO: add svm to manager worker
        # SVM Worker 集成 - P1 任务
        self._svm_worker = SVMWorker()
        self._setup_svm_workers()
        
        self.loop_interval = loop_interval

        # 根据策略生成waiter
        waiter = WaiterFactory.get_waiter(WorkerParams.WORKER_RUN_POLICY)
        if waiter is not None:
            self.waiter = waiter
            self.waiter.call_workers(self.worker_register.get_all_worker())
        else:
            raise Exception("Master hasn't available waiter,the application can't start.")

    def _setup_svm_workers(self) -> None:
        """设置 SVM Worker 监控 - P1 任务实现"""
        # 注册所有 Worker 到 SVM
        for name, worker in self.worker_register.get_all_worker().items():
            self._svm_worker.register_worker(name, worker)
        
        # 启动监控
        self._svm_worker.start_monitoring()
        LogUtils.info("✅ SVM Worker setup completed")

    def change_waiter(self, waiter):
        if self.waiter is not None:
            raise Exception("")
        self.waiter = waiter

    def config(self):
        for key, value in config_funcs.items():
            value()

    async def perform(self):
        """
        执行任务
        """
        # TODO： 可以考虑使用异步的方式来执行
        while True:
            self.waiter.execute_service()
            if self.loop_interval > 0:
                LogUtils.debug("Master Sleep")
                await asyncio.sleep(self.loop_interval)

    def run(self):
        """运行 Master - 集成 SVM 监控"""
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(self.perform())
            loop.run_forever()
        finally:
            # 停止 SVM 监控
            self._svm_worker.stop_monitoring()

    def get_svm_health_report(self) -> Dict:
        """获取 SVM 健康报告
        
        Returns:
            所有 Worker 的健康状态
        """
        return self._svm_worker.get_all_workers_health()
