# 03 · 事件管道

**目标**：让两个任务互相通信——一个干完活，通知另一个。

承接[上一篇](02-state-persistence.md)。

## 1. 一个最小的发布 / 订阅

新建 `events_demo.py`：

```python
from zoo_framework.core.aop import event
from zoo_framework.reactor.event_reactor_manager import EventReactorManager

received = []


@event(topic="order.created", channel="business")
def on_order_created(req):
    received.append((req.topic, req.content))
    print(f"收到事件: {req.topic} {req.content}", flush=True)


manager = EventReactorManager()
manager.dispatch("order.created", {"id": 42}, channel="business")
print(f"回调收到了: {received}", flush=True)
```

运行：

```bash
python -u events_demo.py
```

**期望输出**：

```
收到事件: order.created {'id': 42}
回调收到了: [('order.created', {'id': 42})]
```

## 2. 通道隔离——这条管道最重要的性质

再注册一个**同名 topic 但不同频道**的响应者：

```python
@event(topic="order.created", channel="audit")     # 注意频道不同
def on_audit(req):
    received.append(("AUDIT", req.content))
```

**往 `channel="business"` 派发时，`on_audit` 不会被调用。**

这意味着你可以把"必须处理"的响应者与"能丢就丢"的响应者放在不同频道，
避免一个慢响应者拖住整条链路。

## 3. 在 Worker 里发事件

```python
class OrderSyncWorker(BaseWorker):
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})

    def _execute(self):
        synced = sync_orders()

        @event(topic="order.synced", channel="business")
        def _on_synced(req):
            print(f"对账任务收到: {req.content}", flush=True)

        EventReactorManager().dispatch(
            "order.synced", {"count": synced}, channel="business"
        )
```

## 4. 重试与死信

```python
from zoo_framework.reactor.event_retry_strategy import EventRetryStrategy

@event(topic="order.synced", channel="business",
       retry_time=3, retry_strategy=EventRetryStrategy.RetryTimes)
def on_synced(req):
    push_to_downstream(req.content)      # 可能失败
```

重试耗尽后事件进入**死信记录**，可通过 `EventChannel.get_dead_letters()` 取出——
**不会被静默丢弃**。

## 5. 必须知道的语义边界

| 保证 | 状态 |
|---|---|
| **恰好一次** | ❌ **没有**。回调失败会重放 |
| 至少一次 | ✅ 在重试策略生效范围内 |
| 跨进程 | ❌ 进程内管道 |
| 重启后仍在队列 | ❌ 队列在内存中 |

**如果你的业务不能接受重复处理，去重必须由你自己做**（例如以业务键做幂等）。

## 常见错误

### 回调注册了但从不触发

三件事排查：topic 完全相同（大小写敏感）、channel 完全相同、
以及响应者是在**派发之前**注册的。

### 回调抛异常后事件消失了

检查重试策略。默认是 `RetryOnce`；若重试耗尽，事件会进死信记录而非消失——
用 `EventChannel.get_dead_letters()` 确认它在哪里。

### 事件延迟很久才到

事件管道默认按**节拍**检查（`event:delay`，默认 5 秒）。
对延迟敏感可启用推送模型：

```json
{ "event": { "pushModelEnabled": true } }
```

## 下一步

- 04 作用域容器 —— 让两个任务共享同一个实例
- [指南：事件管道](../guides/event-pipeline.md) —— 优先级、批量派发与更多细节
