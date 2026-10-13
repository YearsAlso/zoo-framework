# 作用域容器

## 它解决什么

两个任务需要共享同一个对象（连接池、缓存、配置句柄）时，你会需要它。
**但它的关键差别不在"能共享"，而在"不替换你的类"。**

`ScopedContainer` 保持类身份不变：`issubclass` / `isinstance` / 类型检查 / IDE 补全
全部原样可用。这一点是刻意的——框架历史上有过一个 `@cage` 装饰器，它把类替换成工厂函数，
导致 `issubclass` 失效并造成一次 P0。它已被删除，见[迁移指南](../MIGRATION.md)。

## 三种作用域

| `scope_kind` | 生命周期 | 解析方式 |
|---|---|---|
| `"process"` | 进程内单例 | `Scope.process()` |
| `"session"` | 每个会话 id 一个实例 | `Scope.session("session-id")` |
| `"prototype"` | 每次解析都是新实例 | `Scope.prototype()` |

## 基本用法

```python
from zoo_framework.core.container import ScopedContainer, Scope


class ConnectionPool:
    def __init__(self):
        self.connections = []


container = ScopedContainer()
container.register(
    ConnectionPool,
    scope_kind="process",
    thread_safety="instance_guaranteed",
)

a = container.resolve(ConnectionPool, Scope.process())
b = container.resolve(ConnectionPool, Scope.process())
print(a is b)  # True —— 同一进程作用域内是同一个实例
```

## 必须声明的两项

`register()` 有两个**必填**的语义声明：

### `scope_kind`

决定实例活在哪个作用域。**`resolve()` 时传入的 scope 必须与它匹配**——
注册为 `"process"` 却用 `Scope.prototype()` 解析，拿到的是 process 实例，而不是新实例。

### `thread_safety`

必须三选一，**不声明会报错**：

```
ValueError: registration <class '...'> declares no thread-safety ownership;
expected one of ['container_serialized', 'instance_guaranteed', 'single_thread']
```

| 取值 | 含义 |
|---|---|
| `"container_serialized"` | 由容器保证串行访问 |
| `"instance_guaranteed"` | 由实例自身保证（大多数线程安全对象） |
| `"single_thread"` | 只会在单线程作用域使用。**进程级注册时会绑定首次解析它的线程**，从别的线程解析直接报错（见下） |

这条要求的存在理由是：**线程安全的归属必须被显式声明，而不是被假设。**
框架宁可让你在注册时报错，也不愿在一个默认值上做出你没同意的承诺。

## 测试接缝

| 方法 | 用途 |
|---|---|
| `reset()` | 清空全部注册与实例，返回被清掉的注册项名 |
| `replace()` | 在测试里替换某个注册的实现 |

```python
def test_something():
    container = ScopedContainer()
    container.register(ConnectionPool, scope_kind="process", thread_safety="instance_guaranteed")
    ...
    cleared = container.reset()  # 测试之间彻底隔离
```

## 完整示例：会话作用域

```python
container.register(SessionCache, scope_kind="session", thread_safety="instance_guaranteed")

s1 = container.resolve(SessionCache, Scope.session("user-1"))
s2 = container.resolve(SessionCache, Scope.session("user-1"))
s3 = container.resolve(SessionCache, Scope.session("user-2"))

assert s1 is s2  # 同一会话共享
assert s1 is not s3  # 不同会话隔离
```

## 常见错误

### `ValueError: ... declares no thread-safety ownership`

忘了传 `thread_safety`。三个取值见上。

### 解析出来的不是新实例

多半是 `scope_kind` 与传给 `resolve()` 的 `Scope` 不匹配。
`"prototype"` 必须配 `Scope.prototype()`。

### 想让 Worker 直接拿到容器

Worker 只应依赖构造时传给它的 `props`，不应去解析容器。

### `... is declared as 'single_thread' ... the current thread ... may not consume it`

注册为 `single_thread` 的**进程级**实例会绑定到**首次解析它的那个线程**；换一个线程再解析，
框架直接报错而不是放行：

```
registration 'zoo_framework.reactor.waiter_result_reactor.WaiterResultReactor'
is declared as 'single_thread'(single-thread only), bound to thread 63260;
the current thread 59932 may not consume it; for cross-thread sharing, change
the declaration to 'instance_guaranteed' or 'container_serialized'
```

**它为什么是错误而不是警告**：这类实例内部没有同步，跨线程使用会静默损坏状态。框架宁可当场
拒绝，也不给你一个坏掉的实例。

**典型触发场景：在 Worker 里再构造一个 `Master()`。** Worker 跑在调度器的线程上，与首次绑定
那些进程级实例的线程不同，于是 `Master()` 构造即失败（框架会把它报成 Worker 执行失败）。
也就是说，**同一个进程里不能嵌套两套框架运行时**。

要在一条 Worker 里驱动"另一套运行时"（例如跑一次 agent 会话），正确做法是**跨进程**：把那次
运行交给子进程，Worker 只管调度与生命周期。附带好处是两边的运行期状态彻底隔离——子进程崩了
也不会污染宿主。

> 实测来源：一个消费方在 Worker 里调用另一个基于本框架的项目（那个项目会自建 `Master`），
> 得到的就是上面这条错误；改成子进程后正常。该消费方现已把这一条写进自己的示例说明。
需要共享对象时，在注册 Worker 之前把它准备好，通过 `props` 传进去。

## 相关

- [迁移指南](../MIGRATION.md) —— `@cage` 的迁移
- [配置参考](config-reference.md)
