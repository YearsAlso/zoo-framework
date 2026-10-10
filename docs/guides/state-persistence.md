# 状态持久化

[教程 02](../tutorial/02-state-persistence.md) 走过一遍基本用法。本页补齐语义边界。

## 读写

```python
from zoo_framework.statemachine import StateMachineManager

sm = StateMachineManager()                 # 进程级单例，任何地方拿到的是同一个

sm.set_state("order", "status", "pending") # 首次写入即创建作用域
sm.set_state("order", "status", "paid")    # 覆盖

sm.get_state("order", "status")            # -> 'paid'
sm.get_state("order", "nothing")           # -> None（键不存在）

sm.set_state("order", "item.count", 2)     # 点分键路径，自动嵌套
sm.get_state("order", "item.count")        # -> 2

sm.remove_state("order", "status")
```

| 方法 | 说明 |
|---|---|
| `set_state(scope, key, value)` | 写入；`scope` 不存在时自动创建 |
| `get_state(scope, key)` | 读取；不存在返回 `None` |
| `remove_state(scope, key)` | 删除 |
| `observe_state(scope, key, cb)` | 订阅变更 |
| `unobserve_state(scope, key, cb)` | 取消订阅 |

## 观察者

```python
def on_status_change(payload):
    print(payload["value"])

sm.observe_state("order", "status", on_status_change)
sm.set_state("order", "status", "shipped")     # 触发回调
sm.unobserve_state("order", "status", on_status_change)
```

> **记得取消订阅。** 回调会持有引用；长期运行的进程里忘记 `unobserve_state`
> 是内存增长的常见来源——示例 Worker 里就有针对这一点的写法。

## 落盘

| 项 | 值 |
|---|---|
| 路径 | `stateMachine:picklePath`，默认 `./zooStates.pic` |
| 间隔 | `stateMachine:delay`，默认 5 秒 |
| 停机 | `Master.shutdown()` 时**再存一次**（这是最后一次保存） |
| 方式 | 先写 `.tmp`，再**原子替换** |
| 备份 | 替换前把旧文件复制进同级 `backups/`，**保留最近 5 份** |

## 三条必须知道的语义

### 1. 恢复是「整表替换」，不是逐键合并

读盘时用文件里的状态**整体替换**内存状态。手工改过状态文件、或多个进程共用一个文件，
行为都不会如你所愿。

### 2. 只有优雅停机才触发最后一次保存

`kill -9`、断电、容器强制销毁都不会。`stateMachine:delay` 决定了你最多丢多少。

### 3. 状态在内存里，不在数据库里

它的规模上限就是你愿意放进内存的量。需要持久化大量业务数据的场景，
本框架不是合适的地方。

## 多进程

**不要多个进程共用同一个状态文件。** 恢复语义是整表替换，它们会互相覆盖。

需要跨进程共享状态请用 Celery 这类方案——本框架明确不做跨进程协调，
见[与其它方案对比](comparison.md)。
