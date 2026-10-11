# Proposal: add-event-push-model

## Why

`EventWorker` 当前是**纯拉模型**：`is_loop=True` 按固定心跳（`EventParams.EVENT_DELAY_TIME`）轮询所有通道的 `.size()`，通道空闲时也在空转。每个事件要等到下一次心跳才被消费——空闲 CPU 浪费 + 平均半拍心跳的投递延迟。用户在剖析 native 阶段 0 时提出 epoll 类机制的方向：内核 epoll 等的是 socket fd 就绪，进程内队列没有 fd 可等；其等价物是**条件变量推模型**——生产者入队即 `notify`，消费者无活挂起、来活即醒。空闲零开销、投递延迟从「平均半拍」降到「立即」，同时不改事件语义（恰好一次去向：投递/回队/死信）。

## What Changes

- `EventChannel` / `EventFIFO` 生产侧：入队成功后挂 `Condition.notify`（每次 `push_value` / `dispatch` 后）
- `EventWorker` 消费侧：无事件时在 `Condition.wait(timeout)` 挂起（timeout 为兜底节拍，防生产者漏 notify 时的最终一致），不再纯靠心跳轮询
- 新参数键（`event:*` 键族内）：推模型启用开关（默认关闭 = 现行为零变化）与挂起兜底超时
- **不改变**：排队语义、重试语义、死信语义、响应器查找与投递全路径、`is_expire` 判定

## Capabilities

### New Capabilities

- `event-push-model`: 事件通道推模型消费。SHALL 让消费者在通道无事件时挂起等待生产者通知，SHALL 携带兜底超时防通知丢失，MUST NOT 改变既有事件去向语义（投递/回队/死信恰好其一）；关闭时保持既有轮询行为。

### Modified Capabilities

无——`event-dispatch` 的既有 REQUIREMENTS（通道隔离、优先级、重试、死信可观测）全部不变。

## Impact

- **代码**：`zoo_framework/event/event_channel.py`（notify 挂点）、`zoo_framework/fifo/event_fifo.py` 或 `base_fifo.py`（入队钩子）、`zoo_framework/workers/event_worker.py`（wait 挂起）、`zoo_framework/params/event_params.py`
- **并发**：Condition 锁阵线须与 FIFO deque 操作对齐（notify 在锁内，防丢失唤醒）；`per-channel` 一把锁，避免全局锁阵线
- **测试**：`tests/test_event_push_model.py`（通知唤醒、兜底超时、丢失唤醒防护、关闭零影响）
- **风险**：丢失唤醒（notify 早于 wait）→ 兜底超时 + 通知前先置位队列非空标志的经典双保险形态
- **与 native 线的关系**：无直接耦合；这是事件管道独立的形态改造
