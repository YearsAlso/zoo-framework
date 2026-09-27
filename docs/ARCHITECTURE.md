# 🏗️ 架构设计

本文档介绍 Zoo Framework 的整体架构设计，帮助开发者理解框架的工作原理。

---

## 🎯 设计哲学

Zoo Framework 采用**动物园隐喻**设计：

| 现实世界 | 框架概念 | 职责 |
|----------|----------|------|
| 👨‍🌾 园长 | Master | 管理整个动物园 |
| 🦁 动物 | Worker | 执行任务的基本单元 |
| 🏠 笼子 | Cage | 保护 Worker，提供线程安全 |
| 🍎 食物 | Event | Worker 之间通信的载体 |
| 🥘 饲养员队列 | FIFO | 管理事件的有序处理 |

---

## 🏛️ 整体架构

```mermaid
graph TB
    subgraph "🎪 Zoo Framework"
        M[👨‍🌾 Master<br/>园长] -->|调度| W[🍽️ Waiter<br/>饲养员]
        W -->|分发任务| Wr[👷 Workers<br/>动物群]
        
        subgraph Workers
            Wr1[🦁 Worker 1]
            Wr2[🐒 Worker 2]
            Wr3[🐘 Worker 3]
        end
        
        Wr1 -->|住在| C1[🏠 Cage 1]
        Wr2 -->|住在| C2[🏠 Cage 2]
        Wr3 -->|住在| C3[🏠 Cage 3]
        
        M -->|管理| SM[🔄 StateMachine<br/>状态机]
        M -->|监控| SVM[📊 SVM<br/>状态向量机]
        M -->|加载| PM[🔌 Plugin<br/>插件系统]
        
        E[📢 Event<br/>事件] -->|排队| F[📊 FIFO<br/>饲养员队列]
        F -->|分发| Wr
        
        SM -.->|状态变更| Wr
        SVM -.->|健康检查| Wr
    end
```

---

## 📦 核心模块

### 1. 👨‍🌾 Master - 园长

**职责**：管理整个框架的生命周期

```mermaid
classDiagram
    class Master {
        +WorkerRegistry worker_registry
        +SVMWorker svm_worker
        +Waiter waiter
        +__init__(config)
        +register_worker(name, worker_class)
        +run()
        +shutdown()
        +get_health_report()
    }
    
    class MasterConfig {
        +str config_path
        +bool enable_svm
        +int svm_check_interval
    }
    
    Master --> MasterConfig
    Master --> WorkerRegistry
    Master --> SVMWorker
    Master --> Waiter
```

**关键特性**：
- Worker 自动注册和生命周期管理
- SVM 健康监控
- 优雅关闭

### 2. 👷 Worker - 动物

**职责**：执行业务逻辑的基本单元

```mermaid
classDiagram
    class BaseWorker {
        <<abstract>>
        +bool is_loop
        +float delay_time
        +str name
        +_execute()* 
        +_destroy(result)
        +stop()
    }
    
    class EventWorker {
        +handle_event(event)
    }
    
    class StateMachineWorker {
        +setup_state_machine()
        +persist_state()
    }
    
    class AsyncWorker {
        +async_execute()* 
        +run_in_background()
    }
    
    BaseWorker <|-- EventWorker
    BaseWorker <|-- StateMachineWorker
    BaseWorker <|-- AsyncWorker
```

**Worker 类型**：
| 类型 | 说明 | 使用场景 |
|------|------|----------|
| BaseWorker | 基础 Worker | 简单任务 |
| EventWorker | 事件 Worker | 响应事件 |
| StateMachineWorker | 状态机 Worker | 状态管理 |
| AsyncWorker | 异步 Worker | IO 密集型任务 |

### 3. 🏠 Cage - 笼子

**职责**：提供线程安全和生命周期管理

```mermaid
classDiagram
    class cage {
        <<decorator>>
        +protect(worker)
        +monitor(worker)
    }
    
    class ThreadSafeDict {
        +get(key)
        +set(key, value)
        +delete(key)
    }
    
    class SafeCage {
        +RLock lock
        +isolate()
    }
    
    cage --> ThreadSafeDict
    cage --> SafeCage
```

**保护机制**：
- 线程锁（RLock/Lock）
- 自动异常处理
- 资源清理

### 4. 🔄 StateMachine - 状态机

**职责**：管理应用状态

```mermaid
classDiagram
    class StateMachineManager {
        +create_scope(scope)
        +get_and_create_scope(scope)
        +set_state(scope, key, value)
        +get_state(scope, key)
        +remove_state(scope, key)
        +observe_state(scope, key, effect)
        +unobserve_state(scope, key, effect)
        +load_state_machines()
        +get_state_machines()
    }
    
    class StateScope {
        +StateIndex _state_index
        +register_node(key, value)
        +set_state_node(key, value)
        +get_state_node(key)
        +get_state_value(key)
        +observe_state_node(key, effect)
        +unobserve_state_node(key, effect)
    }
    
    class StateIndex {
        <<interface>>
        +get(key)
        +set(key, value)
        +remove(key)
    }
    
    class ThreadSafeDictIndex {
        +ThreadSafeDict _index
    }
    
    class HierarchicalIndex {
        +dict _root
    }
    
    StateMachineManager --> StateScope
    StateScope --> StateIndex
    StateIndex <|.. ThreadSafeDictIndex
    StateIndex <|.. HierarchicalIndex
```

**P2 优化**：使用工厂模式创建索引，支持多种实现方式。

### 5. 📢 Event & Reactor - 事件系统

**职责**：Worker 间通信

```mermaid
sequenceDiagram
    participant P as 📤 Producer
    participant F as 📊 FIFO
    participant R as 📢 Reactor
    participant C as 📬 Consumer
    
    P->>F: push(event)
    F->>F: sort by priority
    
    loop Polling
        R->>F: pop()
        F-->>R: event
        R->>R: channel filter
        R->>C: dispatch(event)
        C->>C: handle(event)
    end
```

**P1 优化**：事件通道隔离，防止不同通道事件误处理。

### 6. 💾 PersistenceScheduler - 持久化调度器

**职责**：解耦持久化逻辑

```mermaid
classDiagram
    class PersistenceScheduler {
        +str filepath
        +PersistenceStrategy strategy
        +int auto_save_interval
        +start()
        +stop()
        +load()
        +save()
        +mark_dirty()
    }
    
    class PersistenceStrategy {
        <<interface>>
        +save(data, filepath)
        +load(filepath)
        +validate(filepath)
    }
    
    class PicklePersistenceStrategy {
        +save(data, filepath)
        +load(filepath)
    }
    
    class BackupManager {
        +create_backup(filepath)
        +restore_backup(filepath)
        +cleanup_old_backups()
    }
    
    class FileChecksumValidator {
        +calculate_checksum(filepath)
        +verify_checksum(filepath, expected)
    }
    
    PersistenceScheduler --> PersistenceStrategy
    PersistenceScheduler --> BackupManager
    PersistenceScheduler --> FileChecksumValidator
    PersistenceStrategy <|.. PicklePersistenceStrategy
```

**P1 特性**：
- 解耦持久化逻辑
- 文件校验和
- 自动备份恢复

### 7. 🔌 Plugin - 插件系统

**职责**：支持第三方扩展

```mermaid
classDiagram
    class Plugin {
        <<abstract>>
        +str name
        +str version
        +activate()
        +deactivate()
    }
    
    class PluginManager {
        +register(plugin)
        +unregister(plugin)
        +get_plugin(name)
        +load_from_path(path)
    }
    
    class WorkerDelayManager {
        +set_delay(worker, delay)
        +set_delay_strategy(strategy)
    }
    
    class DelayStrategy {
        <<interface>>
        +calculate_delay(attempt)
    }
    
    class FixedDelay
    class ExponentialDelay
    class AdaptiveDelay
    
    PluginManager --> Plugin
    PluginManager --> WorkerDelayManager
    WorkerDelayManager --> DelayStrategy
    DelayStrategy <|.. FixedDelay
    DelayStrategy <|.. ExponentialDelay
    DelayStrategy <|.. AdaptiveDelay
```

### 8. 📊 SVM - 状态向量机

**职责**：Worker 健康监控

```mermaid
classDiagram
    class SVMWorker {
        +Dict workers
        +Dict metrics
        +register_worker(name, worker)
        +record_execute(name, duration, success)
        +get_worker_health(name)
        +start_monitoring()
        +stop_monitoring()
    }
    
    class WorkerMetrics {
        +int execute_count
        +int error_count
        +float avg_execute_time
        +str status
    }
```

**监控指标**：
- 执行次数
- 错误率
- 平均执行时间
- 健康评分

---

## 🔄 数据流

### Worker 执行流程

```mermaid
sequenceDiagram
    participant M as 👨‍🌾 Master
    participant W as 🍽️ Waiter
    participant C as 🏠 Cage
    participant Wr as 👷 Worker
    
    M->>W: call_workers(workers)
    
    loop Main Loop
        W->>C: enter()
        C->>C: 🔒 acquire lock
        C->>Wr: _execute()
        
        alt Success
            Wr-->>C: result
        else Error
            Wr-->>C: exception
            C->>C: handle exception
        end
        
        C->>C: 🔓 release lock
        C->>C: leave()
    end
    
    Wr->>Wr: _destroy(result)
```

### 事件处理流程

```mermaid
sequenceDiagram
    participant Wr as 👷 Worker
    participant E as 📢 EventReactor
    participant F as 📊 FIFO
    participant Ch as 📡 ChannelManager
    
    Wr->>E: dispatch(topic, content, channel)
    E->>Ch: can_handle_event(reactor_name, event)
    
    alt Channel Valid
        Ch-->>E: True
        E->>F: push(event)
        F->>F: sort by priority
        F-->>E: event
        E->>Wr: handle(event)
    else Channel Invalid
        Ch-->>E: False
        E->>E: drop event
    end
```

---

## 🛡️ 线程安全设计

### 线程安全组件

| 组件 | 线程安全机制 | 说明 |
|------|-------------|------|
| ThreadSafeDict | RLock | 线程安全字典 |
| Cage | RLock | Worker 保护 |
| StateScope | StateIndex | 状态隔离 |
| PersistenceScheduler | RLock | 文件操作安全 |

### 最佳实践

```python
# ✅ 使用 Cage 装饰器保护 Worker
from zoo_framework.core.aop import cage

@cage
class MyWorker(BaseWorker):
    pass

# ✅ 使用 ThreadSafeDict 存储共享数据
from zoo_framework.utils.thread_safe_dict import ThreadSafeDict

data = ThreadSafeDict()

# ✅ 使用 RLock 保护关键代码
import threading

_lock = threading.RLock()

with _lock:
    # 临界区代码
    pass
```

---

## 📈 性能优化

### P2 优化方案

1. **优先级算法优化**
   - 加权优先级：基础优先级 + 等待时间加成
   - 防止低优先级任务饿死

2. **异步 Worker**
   - 支持 asyncio 协程
   - Worker 池管理并发

3. **索引工厂模式**
   - 支持多种索引实现
   - 按需选择最优实现

---

## 🔗 模块依赖

```
zoo_framework/
├── core/
│   ├── master.py          → workers, statemachine, plugin
│   ├── waiter.py          → workers
│   ├── worker_registry.py → workers
│   └── persistence_scheduler.py → utils
├── workers/
│   ├── base_worker.py     → utils
│   ├── async_worker.py    → base_worker
│   └── state_machine_work.py → statemachine
├── statemachine/
│   ├── state_machine_manager.py → utils
│   ├── state_scope.py     → state_index_factory
│   └── state_index_factory.py → utils
├── fifo/
│   └── event_fifo.py      → utils
├── reactor/
│   ├── event_reactor.py   → utils
│   └── event_reactor_manager.py → event_reactor
└── plugin/
    └── __init__.py        → workers, utils
```

---

## 📚 相关文档

- [快速开始](DEVELOPMENT.md)
- [贡献指南](CONTRIBUTING.md)
- [调试技巧](DEBUGGING.md)
- [API 参考](API_REFERENCE.md)
