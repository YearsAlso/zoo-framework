# 04 · 作用域容器

**目标**：让两个任务共享同一个对象（连接池、缓存），**且不破坏类型契约**。

承接[上一篇](03-event-pipeline.md)。

## 1. 先理解它解决什么

两个任务各自 `ConnectionPool()` 会创建两个连接池——浪费且有状态不一致风险。
你需要的是"同一进程作用域内只有一个"。

**但真正的难点不是"能共享"，而是"共享时不要骗过 Python"。**
框架历史上有一个 `@cage` 装饰器，它把类替换成工厂函数，导致
`issubclass` / `isinstance` 失效并造成一次 P0。它已被删除，
现在的容器**保持类身份不变**。

## 2. 注册与解析

```python
from zoo_framework.core.container import ScopedContainer, Scope


class ConnectionPool:
    def __init__(self):
        self.connections = []


container = ScopedContainer()
container.register(
    ConnectionPool,
    scope_kind="process",                 # 实例活在进程作用域
    thread_safety="instance_guaranteed",   # 必填
)

a = container.resolve(ConnectionPool, Scope.process())
b = container.resolve(ConnectionPool, Scope.process())

print(a is b)                              # True
print(issubclass(ConnectionPool, object))  # True —— 类身份没有被替换
```

**期望输出**：

```
True
True
```

## 3. 三种作用域

| `scope_kind` | 解析方式 | 行为 |
|---|---|---|
| `"process"` | `Scope.process()` | 进程内单例 |
| `"session"` | `Scope.session("id")` | 每个会话一个 |
| `"prototype"` | `Scope.prototype()` | 每次都是新实例 |

```python
container.register(SessionCache, scope_kind="session",
                   thread_safety="instance_guaranteed")

s1 = container.resolve(SessionCache, Scope.session("user-1"))
s2 = container.resolve(SessionCache, Scope.session("user-1"))
s3 = container.resolve(SessionCache, Scope.session("user-2"))

assert s1 is s2        # 同会话共享
assert s1 is not s3    # 跨会话隔离
```

> **注意**：`resolve()` 传入的 scope **必须与注册时的 `scope_kind` 匹配**。
> 注册为 `"process"` 却用 `Scope.prototype()` 解析，拿到的是进程实例，而不是新实例。

## 4. 为什么必须声明 `thread_safety`

忘了传会报错：

```
ValueError: registration <class '...'> declares no thread-safety ownership;
expected one of ['container_serialized', 'instance_guaranteed', 'single_thread']
```

| 取值 | 含义 |
|---|---|
| `"container_serialized"` | 由容器保证串行访问 |
| `"instance_guaranteed"` | 由实例自身保证（大多数线程安全对象） |
| `"single_thread"` | 只会在单线程作用域使用 |

**这条要求是刻意的**：线程安全的归属必须被显式声明，而不是被假设。
框架宁可让你在注册时报错，也不愿在一个默认值上做出你没同意的承诺。

## 5. 测试接缝

```python
def test_something():
    container = ScopedContainer()
    container.register(ConnectionPool, scope_kind="process",
                       thread_safety="instance_guaranteed")
    ...
    cleared = container.reset()      # 测试之间彻底隔离，返回被清掉的项
```

## 6. 怎么把它交给 Worker

**Worker 不应该去解析容器。** 它只应依赖构造时传给它的 `props`。

正确做法是在注册之前把实例准备好，然后作为依赖注入进 Worker 需要的地方：

```python
container = ScopedContainer()
container.register(ConnectionPool, scope_kind="process",
                   thread_safety="instance_guaranteed")
pool = container.resolve(ConnectionPool, Scope.process())

class OrderSyncWorker(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})
        self.pool = pool          # 依赖由外部注入，Worker 不知道容器存在
```

这样 Worker 仍然"只依赖 props"，不需要读框架源码就能写。

## 常见错误

### `ValueError: ... declares no thread-safety ownership`

忘了 `thread_safety`。见上表。

### 解析出来的不是新实例

`scope_kind` 与 `resolve()` 的 `Scope` 不匹配。

### `isinstance` / `issubclass` 行为异常

**这不是容器造成的**——容器不替换类。若你的代码里有"把类换成工厂函数"的装饰器，
问题在那里。（`@cage` 正是因此被删除。）

## 下一步

- 05 使用脚手架 —— 让 `zfc` 帮你生成项目结构
- [指南：作用域容器](../guides/container.md)
