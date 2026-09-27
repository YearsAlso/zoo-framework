# 📊 API 参考

Zoo Framework 核心 API 速查手册。

---

## 👨‍🌾 Master API

### Master

```python
from zoo_framework.core import Master, MasterConfig

# 创建 Master
master = Master()

# 使用配置
config = MasterConfig(
    config_path="./config.json",
    enable_svm=True
)
master = Master(config)

# 注册 Worker
master.register_worker("MyWorker", MyWorkerClass)

# 运行（阻塞）
master.run()

# 获取健康报告
report = master.get_health_report()

# 获取 Worker 统计
stats = master.get_worker_stats("WorkerName")

# 优雅关闭
master.shutdown()
```

---

## 👷 Worker API

### BaseWorker

```python
from zoo_framework.workers import BaseWorker

class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__({
            "is_loop": True,         # 是否在调度轮次之间保留并重复执行
            "delay_time": 1.0,       # 单次执行结束后的等待秒数
            "name": "MyWorker",      # Worker 名称
            "run_timeout": 30,       # 可选：执行超时秒数
            "sleep_func": None,      # 可选：替换延迟等待的实现（测试用）
        })

    def _execute(self):
        """执行业务逻辑（必须实现）"""
        pass

    def _destroy(self, result):
        """销毁回调（可选）：Worker 被注销时调用，停机流程会触发它"""
        pass

    def _on_error(self):
        """执行抛异常时调用（可选）"""
        pass

    def _on_done(self):
        """单次执行结束（无论成败）时调用（可选）"""
        pass
```

**配置读取**：`is_loop` / `run_timeout` / `delay_time` 都是以 `_props` 字典为唯一真源的**属性**，
读取不需要调用语法（`worker.is_loop`，而非 `worker.is_loop()`）。子类不得用实例属性遮蔽它们。

**执行语义**：

- `_execute()` 抛出的异常在记录并调用 `_on_error()` 之后**继续向上传播**，由调度器收口处理；
  失败的执行不会产生 `WorkerResult`，因此不会被误当作空结果上报。
- `run_timeout` 的语义是**观测 + 熔断**：超时后记录错误、标记该 Worker 不健康、不再派发它。
  系统**不会**强制终止仍在执行的 Worker——CPython 无法安全中断一个正在执行的线程，
  因此框架不声称具备该能力。

### 停机

```python
master = Master()
...
master.shutdown()   # 可重复调用
```

停机顺序：停止派发 → 取消调度任务 → 停止事件循环 → 停止监控 → 注销 Worker（触发 `_destroy`）。
状态机 Worker 的最后一次落盘发生在这条链路的末尾。

### AsyncWorker

```python
from zoo_framework.workers import AsyncWorker

class MyAsyncWorker(AsyncWorker):
    async def async_execute(self):
        """异步执行业务逻辑"""
        result = await some_async_operation()
        return result

# 使用
worker = MyAsyncWorker()
result = worker.execute()  # 同步等待

# 或后台运行
task = worker.run_in_background()
```

### EventWorker

```python
from zoo_framework.workers import EventWorker

class MyEventWorker(EventWorker):
    def handle_event(self, event):
        """处理事件"""
        print(f"收到事件: {event.topic}")
```

### StateMachineWorker

```python
from zoo_framework.workers import StateMachineWorker

class MyStateWorker(StateMachineWorker):
    def setup_state_machine(self):
        """设置状态机"""
        sm = StateMachineManager()
        sm.create_state_machine("my_machine")
        sm.add_state("my_machine", "idle")
```

---

## 🏠 Cage API

### 装饰器使用

```python
from zoo_framework.core.aop import cage

@cage
class SafeWorker(BaseWorker):
    """线程安全的 Worker"""
    pass
```

### ThreadSafeDict

```python
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

data = ThreadSafeDict()
data["key"] = "value"
value = data.get("key")
```

---

## 🔄 StateMachine API

### StateMachineManager

```python
from zoo_framework.statemachine import StateMachineManager

sm = StateMachineManager()

# 创建状态机
sm.create_state_machine("machine_name")

# 添加状态
sm.add_state("machine_name", "state_name")

# 状态转换
sm.transition("machine_name", "from_state", "to_state")

# 观察状态
sm.observe_state("key", callback)

# 取消观察
sm.unobserve_state("key", callback)

# 设置状态值
sm.set_state("key", value)

# 获取状态值
value = sm.get_state("key")
```

### StateScope

```python
from zoo_framework.statemachine import StateScope

scope = StateScope(index_type="dict")

# 注册节点
scope.register_node("key", value)

# 获取节点
node = scope.get_state_node("key")

# 观察节点
scope.observe_state_node("key", callback)

# 取消观察
scope.unobserve_state_node("key", callback)
```

---

## 📢 Event API

### EventReactorManager

```python
from zoo_framework.reactor import EventReactorManager
from zoo_framework.reactor.event_reactor_req import ChannelType

# 分发事件
EventReactorManager.dispatch(
    topic="event.topic",
    content={"data": "value"},
    reactor_name="reactor_name",
    channel=ChannelType.BUSINESS.value
)

# 按通道分发
EventReactorManager.dispatch_by_channel(
    topic="event.topic",
    content={"data": "value"},
    channel=ChannelType.SYSTEM.value
)

# 注册响应器通道
EventReactorManager.register_reactor_channels(
    "reactor_name",
    [ChannelType.BUSINESS.value, ChannelType.SYSTEM.value]
)
```

### EventNode

```python
from zoo_framework.fifo.node import EventNode, PriorityLevel

# 创建事件节点
node = EventNode(
    topic="topic",
    content="content",
    channel_name="default",
    priority=100,
    priority_level=PriorityLevel.HIGH
)

# 获取有效优先级
priority = node.get_effective_priority()

# 获取紧急程度
urgency = node.get_urgency()
```

---

## 💾 Persistence API

### PersistenceScheduler

```python
from zoo_framework.core.persistence_scheduler import PersistenceScheduler

scheduler = PersistenceScheduler(
    filepath="data.pkl",
    auto_save_interval=60,
    enable_backup=True,
    max_backups=5
)

# 启动
scheduler.start()

# 加载数据
data = scheduler.load()

# 更新数据
scheduler.update_data(new_data, auto_save=False)

# 标记脏数据
scheduler.mark_dirty()

# 手动保存
scheduler.save(force=True)

# 停止
scheduler.stop()
```

### BackupManager

```python
from zoo_framework.core.persistence_scheduler import BackupManager

backup_mgr = BackupManager(max_backups=5)

# 创建备份
backup_path = backup_mgr.create_backup("data.pkl")

# 恢复备份
success = backup_mgr.restore_backup("data.pkl")
```

---

## 🔌 Plugin API

### PluginManager

```python
from zoo_framework.plugin import PluginManager, Plugin

# 创建插件管理器
pm = PluginManager()

# 注册插件
pm.register(MyPlugin())

# 加载插件目录
pm.load_plugins_from_directory("./plugins")

# 获取插件
plugin = pm.get_plugin("plugin_name")

# 启用/禁用
pm.enable_plugin("plugin_name")
pm.disable_plugin("plugin_name")
```

### WorkerDelayManager

```python
from zoo_framework.plugin import WorkerDelayManager
from zoo_framework.plugin import ExponentialDelayStrategy

delay_mgr = WorkerDelayManager()

# 设置延迟策略
delay_mgr.set_delay_strategy(ExponentialDelayStrategy(base_delay=1.0))

# 设置 Worker 延迟
delay_mgr.set_delay("worker_name", 5.0)
```

---

## 📝 Logging API

### StructuredLogUtils

```python
from zoo_framework.utils.structured_log import get_logger

logger = get_logger("MyModule")

# 绑定上下文
logger.bind(worker_id="123", task="process")

# 记录日志
logger.info("任务开始", priority=10)
logger.error("处理失败", error="timeout")

# 记录指标
logger.metric("execution_time", 0.5, "seconds")

# 解绑
logger.unbind("worker_id")
```

---

## 🛠️ Utils API

### LogUtils

```python
from zoo_framework.utils import LogUtils

LogUtils.info("Message")
LogUtils.error("Error message")
LogUtils.debug("Debug message")
```

### FileUtils

```python
from zoo_framework.utils import FileUtils

# 检查文件存在
exists = FileUtils.file_exists("path/to/file")

# 读取文件
content = FileUtils.read_file("path/to/file")

# 写入文件
FileUtils.write_file("path/to/file", content)
```

---

## 🔧 WorkerRegistry API

```python
from zoo_framework.core.worker_registry import WorkerRegistry, register_worker

registry = WorkerRegistry()

# 注册类（延迟实例化）
registry.register_class("WorkerName", WorkerClass, metadata={"priority": 100})

# 注册实例
registry.register_instance("WorkerName", worker_instance)

# 注册工厂
registry.register_factory("WorkerName", factory_function)

# 获取 Worker
worker = registry.get_worker("WorkerName")

# 获取所有 Worker
workers = registry.get_all_workers()

# 注销
registry.unregister("WorkerName")

# 装饰器方式
@register_worker("MyWorker", {"priority": 100})
class MyWorker(BaseWorker):
    pass
```

---

## 📚 类型定义

```python
from typing import Dict, Any, Optional, Callable, Awaitable

# Worker Props
WorkerProps = Dict[str, Any]  # {"is_loop": bool, "delay_time": float, ...}

# Event Handler
EventHandler = Callable[[EventNode], None]

# Async Handler
AsyncHandler = Callable[..., Awaitable[Any]]

# State Observer
StateObserver = Callable[[Any], None]
```

---

## 🎯 快速示例

### 完整 Worker 示例

```python
from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker
from zoo_framework.core.aop import cage
from zoo_framework.utils import LogUtils

@cage
class CompleteWorker(BaseWorker):
    def __init__(self):
        super().__init__({
            "is_loop": True,
            "delay_time": 1.0,
            "name": "CompleteWorker"
        })
        self.counter = 0
    
    def _execute(self):
        self.counter += 1
        LogUtils.info(f"执行次数: {self.counter}")
    
    def _destroy(self, result):
        LogUtils.info(f"Worker 停止，总计: {self.counter}")

# 运行
if __name__ == "__main__":
    master = Master()
    master.run()
```

---

*完整 API 文档请参考源码 docstring*
