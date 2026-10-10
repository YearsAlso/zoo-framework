# 事件

进程内事件管道：通道隔离、优先级排序、重试策略与死信记录。

```python
from zoo_framework.core.aop import event
```

::: zoo_framework.event.event_channel.EventChannel
::: zoo_framework.event.event_channel_register.EventChannelRegister
::: zoo_framework.event.event_register.EventRegister

## 反应器

::: zoo_framework.reactor.event_reactor.EventReactor
::: zoo_framework.reactor.event_reactor_manager.EventReactorManager
::: zoo_framework.reactor.waiter_result_reactor.WaiterResultReactor
::: zoo_framework.reactor.event_priorities
::: zoo_framework.reactor.event_retry_strategy.EventRetryStrategy

## 队列

::: zoo_framework.fifo.base_fifo.BaseFIFO
::: zoo_framework.fifo.event_fifo.EventFIFO
::: zoo_framework.fifo.delay_fifo.DelayFIFO
::: zoo_framework.fifo.single_fifo.SingleFIFO
