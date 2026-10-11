# 事件管道

## 它解决什么

两个任务需要通信时——"订单同步完了，通知对账任务"——你不需要引入消息队列。
框架提供了一条**进程内**的事件管道：通道隔离、优先级、重试与死信记录。

## 最小示例

```python
from zoo_framework.core.aop import event
from zoo_framework.reactor.event_reactor_manager import EventReactorManager

received = []


@event(topic="order.created", channel="business")
def on_order_created(req):
    received.append((req.topic, req.content))


manager = EventReactorManager()
manager.dispatch("order.created", {"id": 42}, channel="business")

print(received)  # [('order.created', {'id': 42})]
```

`@event` 的参数：

| 参数 | 默认 | 说明 |
|---|---|---|
| `topic` | 必填 | 事件主题 |
| `channel` | `"default"` | 所属通道 |
| `timeout` | `None` | 响应等待超时（秒） |
| `retry_time` | `1` | 失败重试次数 |
| `retry_strategy` | `RetryOnce` | 重试策略 |
| `done_callback` / `error_callback` / `success_callback` | `None` | 各阶段回调 |

## 通道隔离

**不同通道互不串扰**——这是这条管道最重要的性质：

```python
@event(topic="order.created", channel="business")
def on_business(req): ...


@event(topic="order.created", channel="audit")
def on_audit(req): ...
```

往 `channel="business"` 派发，只有 `on_business` 被调用。上例已验证：
业务通道收到，`audit` 未收到。

通道的用途是把"必须处理"与"能丢就丢"的响应者分开，
避免一个慢响应者拖住整条链路。

## 优先级

同一通道内可以有多个响应者，事件可以按优先级选择响应方式
（只给第一个响应者 / 按优先级 / 全部 / 指定名字的响应者）。
优先级由 `zoo_framework/reactor/event_priorities.py` 计算。

## 重试与死信

`@event(retry_time=3, retry_strategy=EventRetryStrategy.RetryTimes)` 可声明重试。

重试耗尽后事件进入**死信记录**，可通过
`EventChannel.get_dead_letters()` 取出——**不会被静默丢弃**。

可选的重试策略（`EventRetryStrategy` 枚举）：

| 取值 | 含义 |
|---|---|
| `RetryOnce` | 重试一次（默认） |
| `RetryAlways` | 总是重试 |
| `RetryNever` | 不重试 |
| `RetryForever` | 一直重试 |
| `RetryTimes` | 重试指定次数（配 `retry_time`） |

## 节拍与推送模型

事件管道默认按**节拍**检查：每个消费轮把已入队的事件排空，然后按 `event:delay`
（默认 5 秒）等待，再开始下一轮。事件等待多久，取决于它落在这一轮的哪个位置。

对延迟敏感的场景可以启用**推送模型**——消费者改为挂在通道上等，
队列一有事件就把它叫醒，而不是睡满节拍再来看：

```json
{ "event": { "pushModelEnabled": true, "pushFallbackTimeout": 1.0 } }
```

被叫醒的这一轮立即排空；没人入队则等满 `event:pushFallbackTimeout`
（默认 1 秒）后照常扫一遍，**通知漏了也不会让事件困在队列里**。
关闭时（默认）走原有轮询路径。

> **它的边界**：等待发生在每个消费轮的**开头**，轮与轮之间的节拍照旧。
> 因此落在等待窗口里的入队事件可以立刻投递，落在节拍里的入队事件仍等下一轮
> ——**最坏延迟不变**。要缩短最坏延迟，调的是 `event:delay` 本身。

**批量派发**同样是可配置的（`event:dispatchBatchingEnabled` 与 `event:batchMaxSize`）：
开启后，同一通道内发给同一响应器的一批事件合并为一次投递，批大小的上限按
「每轮、每通道取出的事件数」计——超出上限的事件**原样留在队列**里等下一轮，
不裁批、不丢失、也不记死信。默认关闭。完整键位见[配置参考](config-reference.md)。

## 语义边界（重要）

| 保证 | 说明 |
|---|---|
| **恰好一次** | ❌ **没有**。回调失败会重放，框架没有"恰好一次"的收口 |
| **至少一次** | 在重试策略生效的范围内 |
| **跨进程** | ❌ 不适用。这是进程内管道 |
| **重启后仍在队列里** | ❌ 不保证。队列在内存中 |

**如果你的业务不能接受重复处理，去重必须由你自己做**（例如以业务键做幂等）。

## 相关

- [配置参考](config-reference.md) —— `event:*` 全部键位
- [API 参考 · 事件](../api/events.md)
