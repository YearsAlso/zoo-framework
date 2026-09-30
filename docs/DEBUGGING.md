# 🐛 调试指南

本文档提供 Zoo Framework 的常见问题和调试技巧。

---

## 🔧 常用调试方法

### 1. 开启 DEBUG 日志

```python
import logging

# 设置日志级别
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# 或者只设置框架日志
logging.getLogger("zoo_framework").setLevel(logging.DEBUG)
```

### 2. 使用结构化日志

```python
from zoo_framework.utils.structured_log import get_logger

logger = get_logger("MyWorker")
logger.bind(worker_id="123", task="process")

# 记录日志
logger.info("任务开始", priority=10)
logger.error("处理失败", error="timeout", retry_count=3)

# 记录指标
logger.metric("execution_time", 0.5, "seconds")
```

输出示例：
```json
{"event": "任务开始", "worker_id": "123", "task": "process", "priority": 10, "timestamp": "2024-01-15T10:30:00Z"}
```

### 3. 使用 PDB 调试

```python
def _execute(self):
    import pdb

    pdb.set_trace()

    # 常用命令：
    # n - 下一行
    # s - 进入函数
    # c - 继续执行
    # p variable - 打印变量
    # l - 显示代码

    result = self.process_data()
    return result
```

### 4. Worker 性能分析

```python
import time
from zoo_framework.utils import LogUtils


class ProfiledWorker(BaseWorker):
    def __init__(self):
        super().__init__({"name": "ProfiledWorker"})
        self.execution_times = []

    def _execute(self):
        start = time.perf_counter()

        # 业务逻辑
        self.do_work()

        duration = time.perf_counter() - start
        self.execution_times.append(duration)

        # 打印统计
        if len(self.execution_times) % 10 == 0:
            avg = sum(self.execution_times) / len(self.execution_times)
            LogUtils.info(f"平均执行时间: {avg:.3f}s")
```

---

## 🐛 常见问题

### Q1: Worker 不执行

**症状**：Worker 创建后没有执行 `_execute` 方法。

**排查步骤**：

```python
# 1. 检查 Worker 是否注册
from zoo_framework.core.aop import worker_register

print(worker_register.get_all_worker())  # 应该包含你的 Worker

# 2. 检查 Master 是否启动
master = Master()
# 确保调用了 run()
master.run()  # 这会阻塞


# 3. 检查 is_loop 设置
class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            {
                "is_loop": True,  # 确保设置为 True
                "delay_time": 1.0,
                "name": "MyWorker",
            }
        )
```

### Q2: 线程安全问题

**症状**：数据不一致、竞态条件。

**解决方案**：

```python
from threading import RLock


class SafeWorker(BaseWorker):
    def __init__(self):
        super().__init__({"name": "SafeWorker"})
        self._lock = RLock()
        self.counter = 0

    def _execute(self):
        with self._lock:
            # 临界区代码
            self.counter += 1
            print(f"Counter: {self.counter}")
```

> 注意：这里**不要**给 Worker 加任何"替换类"的装饰器（历史的 `@cage` 正是如此，已删除）。
> `WorkerRegistry` 用 `issubclass` 校验契约，把类换成函数会让注册抛
> `TypeError: issubclass() arg 1 must be a class`。锁要自己加——没有任何装饰器会替你
> 提供线程安全。
>
> 若共享的可变对象不止放一个锁，而是"跨 Worker 复用同一个对象"，那属于容器的作用域问题，
> 用 `ScopedContainer` + 显式的 `ThreadSafety` 声明表达（见 [架构设计](ARCHITECTURE.md)
> 的 Cage 一节）。

### Q3: 内存泄漏

**症状**：内存持续增长，最终 OOM。

**常见原因和解决**：

```python
# 1. 观察者未正确移除
class MyWorker(BaseWorker):
    def __init__(self):
        super().__init__()
        self._effects = []

    def observe(self, key, callback):
        from zoo_framework.statemachine import StateMachineManager

        sm = StateMachineManager()
        sm.observe_state(key, callback)
        self._effects.append((key, callback))

    def _destroy(self, result):
        # 清理观察者
        from zoo_framework.statemachine import StateMachineManager

        sm = StateMachineManager()
        for key, callback in self._effects:
            sm.unobserve_state(key, callback)


# 2. 循环引用
import weakref


class Node:
    def __init__(self):
        # ❌ 错误：强引用
        # self.parent = None
        # self.children = []

        # ✅ 正确：使用弱引用
        self.parent = None
        self.children = weakref.WeakSet()


# 3. 缓存无限制增长
class CachedWorker(BaseWorker):
    def __init__(self):
        super().__init__()
        self._cache = {}
        self._max_cache_size = 1000

    def add_to_cache(self, key, value):
        if len(self._cache) >= self._max_cache_size:
            # 清理旧数据
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[key] = value
```

### Q4: 状态机持久化失败

**症状**：状态无法保存或恢复。

**排查步骤**：

```python
# 1. 检查文件权限
import os

state_file = "state.pkl"
print(f"可写: {os.access(os.path.dirname(state_file) or '.', os.W_OK)}")

# 2. 检查持久化调度器
from zoo_framework.core.persistence_scheduler import PersistenceScheduler

scheduler = PersistenceScheduler("state.pkl")
scheduler.start()

# 标记数据为脏（需要保存）
scheduler.mark_dirty()

# 强制保存
scheduler.save(force=True)

# 检查文件是否存在
print(f"文件存在: {os.path.exists('state.pkl')}")

# 3. 检查数据完整性
if scheduler.strategy.validate("state.pkl"):
    data = scheduler.load()
    print(f"加载成功: {data}")
```

### Q5: 事件未触发

**症状**：发送事件但 Worker 未收到。

**排查步骤**：

```python
# 1. 检查通道是否正确
from zoo_framework.reactor.event_reactor_req import ChannelType

# 发送事件
EventReactorManager.dispatch(
    topic="my.event",
    content={"data": "test"},
    channel=ChannelType.BUSINESS.value,  # 确保通道匹配
)

# 2. 检查响应器注册
reactor = EventReactorManager.get_reactor("my.event")
print(f"响应器: {reactor}")

# 3. 检查通道权限
from zoo_framework.reactor.event_reactor_req import get_channel_manager

channel_manager = get_channel_manager()
can_handle = channel_manager.can_handle_event(
    reactor_name="my_reactor",
    event=EventReactorReq("my.event", {}, "my_reactor", ChannelType.BUSINESS.value),
)
print(f"可以处理: {can_handle}")
```

### Q6: 异步 Worker 问题

**症状**：异步 Worker 不执行或报错。

```python
# 1. 确保正确使用 async/await
class MyAsyncWorker(AsyncWorker):
    async def async_execute(self):
        # ✅ 正确：使用 await
        result = await self.async_operation()
        return result

        # ❌ 错误：没有 await
        # result = self.async_operation()


# 2. 检查事件循环
import asyncio

try:
    loop = asyncio.get_running_loop()
    print(f"已有事件循环: {loop}")
except RuntimeError:
    print("没有运行的事件循环")

# 3. 运行异步 Worker
worker = MyAsyncWorker()

# 方式1：同步运行（阻塞）
result = worker.execute()

# 方式2：后台运行（非阻塞）
task = worker.run_in_background()
# 稍后获取结果
if task.done():
    result = task.result()
```

---

## 📊 性能调优

### 1. 监控 Worker 性能

```python
from zoo_framework.core import Master

master = Master()

# 获取健康报告
report = master.get_health_report()
for worker_name, health in report.items():
    print(f"Worker: {worker_name}")
    print(f"  状态: {health['status']}")
    print(f"  健康评分: {health['health_score']}")
    print(f"  执行次数: {health['execute_count']}")
    print(f"  错误率: {health['error_rate']:.2%}")
    print(f"  平均执行时间: {health['avg_execute_time']:.3f}s")
```

### 2. 优化 delay_time

```python
# 高频任务（数据处理）
class FastWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            {
                "is_loop": True,
                "delay_time": 0.01,  # 10ms
                "name": "FastWorker",
            }
        )


# 中频任务（状态检查）
class MediumWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            {
                "is_loop": True,
                "delay_time": 1.0,  # 1s
                "name": "MediumWorker",
            }
        )


# 低频任务（报表生成）
class SlowWorker(BaseWorker):
    def __init__(self):
        super().__init__(
            {
                "is_loop": True,
                "delay_time": 3600,  # 1 hour
                "name": "SlowWorker",
            }
        )
```

### 3. 使用 Worker 池

```python
from zoo_framework.workers import AsyncWorkerPool

# 创建 Worker 池
pool = AsyncWorkerPool(max_workers=10)

# 批量提交任务
items = [1, 2, 3, 4, 5]
results = await pool.map(worker, items)
```

---

## 🔍 诊断工具

### 1. 查看线程状态

```python
import threading


def print_thread_info():
    print(f"当前线程: {threading.current_thread().name}")
    print(f"活跃线程数: {threading.active_count()}")
    print("所有线程:")
    for thread in threading.enumerate():
        print(f"  - {thread.name} (daemon: {thread.daemon})")


print_thread_info()
```

### 2. 内存分析

```python
import tracemalloc

# 开始跟踪
tracemalloc.start()

# 执行业务逻辑
worker.execute()

# 获取内存快照
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics("lineno")

print("[Top 10]")
for stat in top_stats[:10]:
    print(stat)
```

### 3. 性能分析

```python
import cProfile
import pstats

# 创建 profiler
profiler = cProfile.Profile()
profiler.enable()

# 运行代码
master.run()

profiler.disable()

# 打印统计
stats = pstats.Stats(profiler)
stats.sort_stats("cumulative")
stats.print_stats(20)  # 前20个
```

---

## 🆘 紧急修复

### 如何安全停止 Master

```python
import signal
import sys


def graceful_shutdown(signum, frame):
    print("\n🛑 收到停止信号，正在优雅关闭...")
    master.shutdown()
    sys.exit(0)


# 注册信号处理
signal.signal(signal.SIGINT, graceful_shutdown)  # Ctrl+C
signal.signal(signal.SIGTERM, graceful_shutdown)

master.run()
```

### 清理僵尸 Worker

```python
def cleanup_workers():
    """清理未正确停止的 Worker"""
    import threading

    for thread in threading.enumerate():
        if thread.name.startswith("Worker-"):
            print(f"清理 Worker: {thread.name}")
            # 强制停止（不推荐，仅用于紧急情况）
            # 更好的方式是使用 threading.Event


cleanup_workers()
```

---

## 📚 相关文档

- [快速开始](DEVELOPMENT.md)
- [架构设计](ARCHITECTURE.md)
- [贡献指南](CONTRIBUTING.md)
- [API 参考](API_REFERENCE.md)
