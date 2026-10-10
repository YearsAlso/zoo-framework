# 迁移指南

本页逐项列出**已发生的破坏性变更**，每条给出：变更原因、旧写法 → 新写法、**报错原文**、
以及影响范围。

> **口径**：无法从仓库历史中考据的条目留空并标注「未回填」，不编造。
> 每一条的报错原文都是在 Python 3.13 上**实际执行**得到的。

---

## `@worker(count=N)` 装饰器（废弃，将在下个 minor 删除）

### 症状

装饰时立即崩溃：

```
TypeError: BaseWorker.__init__() missing 1 required positional argument: 'props'
```

或（取决于导入写法）连调用都到不了：

```
TypeError: 'module' object is not callable
```

### 原因

`@worker` 在**装饰时**就实例化被装饰的类（`cls()`），而本框架的 `Worker` 子类
`__init__` 需要 `props` 参数，因此必然失败。

即使实例化成功，注册进去的也是 **legacy `WorkerRegister` 表**——`Master` 的派发链
读的是 `WorkerRegistry`，**从不读那张表**。也就是说：过去用它注册的实例**从未被派发过**。

### 迁移

```python
# 旧（不可用）—— 本块是反例，不参与文档导入校验
# doc-example: skip
from zoo_framework.core.aop.worker import worker

@worker(count=20)
class OrderSync(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})
    def _execute(self):
        sync_orders()
```

```python
# 新
from zoo_framework.core import Master

class OrderSync(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})
    def _execute(self):
        sync_orders()

master = Master()
master.register_worker("OrderSync", OrderSync)   # 注册的是**类**
```

### 影响范围

**仅影响显式使用了 `@worker` 的代码。** 使用 `Master.register_worker(name, cls)` 的代码不受影响。

> **导入陷阱**：`from zoo_framework.core.aop import worker` 拿到的是**模块**（不是装饰器），
> 因此 `@worker(...)` 会报 `TypeError: 'module' object is not callable`。
> 模块 `zoo_framework/core/aop/worker.py` 为留一个 minor 周期的迁移窗口而保留，
> 下个 minor 将与 `workers.WorkerRegister` 一并删除。

---

## `register_worker` 装饰器（已删除）

```
ImportError: cannot import name 'register_worker' from 'zoo_framework.core.worker_registry'
```

**迁移**：`Master.register_worker(name, worker_class)`。

删除原因：它的 `isinstance(registry, WorkerRegistry)` 判定恒为 False，实际只走"写入不被派发的表"
的分支——零使用、死分支，且与 `Master.register_worker` 构成第二条注册真源。

---

## `@cage` 装饰器（已删除）

```
ImportError: cannot import name 'cage' from 'zoo_framework.core.aop'
```

**迁移**：改用作用域容器。

```python
# 旧 —— 本块是反例，不参与文档导入校验
# doc-example: skip
from zoo_framework.core.aop import cage

@cage
class ConnectionPool:
    ...
```

```python
# 新
from zoo_framework.core.container import ScopedContainer, Scope

container = ScopedContainer()
container.register(
    ConnectionPool,
    scope_kind="process",              # 实例活在进程作用域
    thread_safety="instance_guaranteed",  # 必填：线程安全归属必须显式声明
)
pool = container.resolve(ConnectionPool, Scope.process())
```

**删除原因**：`@cage` 用工厂函数**替换了类**，导致 `issubclass` / `isinstance` 失效，
曾造成一次 P0。新容器**保持类身份不变**，类型契约、类型检查、IDE 补全全部原样可用。

---

## `@validation` 模块（已删除）

```
ImportError: cannot import name 'validation' from 'zoo_framework.core.aop'
```

**迁移**：直接删除相关用法。该模块零使用、零规格，删除时未提供替代路径。

---

## 等待器子类 `SimpleWaiter` / `StableWaiter` / `SafeWaiter`（已删除）

```
ImportError: cannot import name 'SafeWaiter' from 'zoo_framework.core.waiter'
```

**迁移**：改用 `ThreadPoolModel` 的**背压策略参数** `worker:runPolicy`：

| 旧类 | 新配置值 | 池尺寸不足时的行为 |
|---|---|---|
| `SimpleWaiter` | `"simple"` | 扩容 |
| `StableWaiter` | `"stable"` | 排队 |
| `SafeWaiter` | `"safe"` | 拒绝 |

```json
{ "worker": { "mode": "thread_pool", "runPolicy": "stable", "pool": { "size": 16 } } }
```

---

## 运行依赖移除 `gevent`

```
ModuleNotFoundError: No module named 'gevent'
```

**迁移**：若你的代码直接 `import gevent`，请自行把它加进你的依赖清单。
框架本身不再依赖它——事件投递与状态 effect 改用 `concurrent.futures` 线程执行器，
`greenlet` / `zope-event` / `zope-interface` 随之退出依赖树（安装不再触发源码构建）。

**影响范围**：仅影响"依赖框架顺带装上 gevent"的代码。框架 API 未变。

---

## 配置键 `event:sleep`（已移除）

**迁移**：改用 `event:delay`。

```json
// 旧：填写它没有任何效果（零消费）
{ "event": { "sleep": 5 } }

// 新
{ "event": { "delay": 5 } }
```

**原因**：`event:sleep` 在 gevent 消费循环删除后成为零消费的死键——
配置表"看起来可调"而实际不可调，是一种误导。

---

## 未回填

以下变更在仓库历史中无法完整考据，留待后续补齐，**不在此处编造**：

- `0.9.x` 之前的版本间变更（`CHANGELOG.md` 目前只覆盖到 `0.8.0`，见 issue #117）
- `workers` 包在文档英文化变更中减少的两个导出名
