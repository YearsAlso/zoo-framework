# 02 · 状态持久化

**目标**：让计数器在进程重启后**接着数**，而不是从 1 重新开始。

承接[上一篇](01-quickstart.md)。先确认工作目录里有 `config.json`：

```json
{
  "log": { "path": "./logs", "level": "warning" },
  "stateMachine": { "picklePath": "./zooStates.pic" }
}
```

## 1. 把计数放进状态机

改写 `main.py`：

```python
import sys
import threading

from zoo_framework.core import Master
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.workers import BaseWorker


class CounterWorker(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 0.5, "name": "Counter"})

    def _execute(self):
        sm = StateMachineManager()
        current = sm.get_state("demo", "count") or 0
        sm.set_state("demo", "count", current + 1)
        print(f"count = {current + 1}", flush=True)


if __name__ == "__main__":
    master = Master()
    master.register_worker("Counter", CounterWorker)
    # 跑 7 秒后优雅停机（让 StateMachineWorker 至少落盘一次）
    threading.Timer(float(sys.argv[1]) if len(sys.argv) > 1 else 7.0, master.shutdown).start()
    master.run()
    print("--- 已优雅停机 ---", flush=True)
```

**两个关键点**：

- `StateMachineManager()` 是**进程级单例**，在任何地方 `StateMachineManager()` 拿到的都是同一个
- `set_state("demo", "count", ...)` 的第一个参数是**作用域名**，第二个是**键路径**（支持点分嵌套，如 `"order:item.count"`）

## 2. 第一次运行

```bash
python -u main.py 7
```

**期望输出**：

```
count = 1
count = 2
...
count = 7
count = 8
--- 已优雅停机 ---
```

跑完会多出两个东西：

```
zooStates.pic        # 状态文件
backups/             # 滚动备份目录（首次运行还可能是空的）
```

## 3. 第二次运行——重点在这里

```bash
python -u main.py 5
```

**期望输出**（注意起点不是 1）：

```
count = 9
count = 10
count = 11
count = 12
count = 13
--- 已优雅停机 ---
```

**状态活过了进程生命周期。** 这就是本框架"无 broker 但有状态"的那一层。

## 4. 它是怎么存下来的

| 时机 | 行为 |
|---|---|
| 周期性 | `StateMachineWorker` 每 `stateMachine:delay` 秒（默认 5）落盘一次 |
| 优雅停机 | `Master.shutdown()` 会再存一次——**这是最后一次保存** |
| 写入方式 | 先写 `zooStates.pic.tmp`，再**原子替换**成 `zooStates.pic` |
| 备份 | 每次替换前把旧文件复制进 `backups/`，**保留最近 5 份** |

> **恢复语义是「整表替换」，不是逐键合并。** 也就是说：读盘时用文件里的状态整体替换内存状态。
> 如果你手工改过状态文件，或者两个进程同时写同一个文件，行为不会如你所愿。

## 5. 一个必须知道的限制

**只有优雅停机（`master.shutdown()`）才会触发最后一次保存。**
被 `kill -9`、断电、容器被强制销毁都不会。

因此 `stateMachine:delay` 决定了你最多会丢多少。想要更少丢失就调小它——
代价是更频繁的磁盘写入。

## 常见错误

### 重启后状态没恢复

三个可能：

1. **上一次不是优雅停机**——中间那次保存还没到，且最后一次没触发
2. **`stateMachine:picklePath` 变了**（比如换了工作目录）→ 读的是另一个文件，或读不到
3. **写了状态但从未跨过 `stateMachine:delay`**，且又非优雅停机

### 两个进程共用同一个状态文件

**不要这样做。** 恢复语义是整表替换，两个进程会互相覆盖。
需要多进程请用 Celery 这类方案——本框架明确不做跨进程协调。

### `UnpicklingError` / 读盘失败

状态文件被损坏或来自不兼容的版本。删除 `zooStates.pic` 让框架重建一个，
或从 `backups/` 里挑一份复制回来。

## 下一步

- [指南：状态持久化](../guides/state-persistence.md) —— 观察者、嵌套键路径与更多细节
- [指南：事件管道](../guides/event-pipeline.md) —— 让两个任务互相通信
