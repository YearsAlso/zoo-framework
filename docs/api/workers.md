# Worker

任务单元。继承 `BaseWorker` 并实现 `_execute()`。

```python
from zoo_framework.workers import BaseWorker
```

> **Worker 必须以「类」注册。** `WorkerRegistry` 用 `issubclass` 校验，传入函数或实例会得到
> `TypeError: issubclass() arg 1 must be a class`。

::: zoo_framework.workers.base_worker.BaseWorker

## 内建 Worker

::: zoo_framework.workers.event_worker.EventWorker
::: zoo_framework.workers.state_machine_work.StateMachineWorker

## 协程 Worker

::: zoo_framework.workers.async_worker.AsyncWorker

## 原生执行 Worker

::: zoo_framework.workers.dual_arm_worker.DualArmWorker
::: zoo_framework.native.worker.NativeTaskWorker

## Worker 相关值对象

::: zoo_framework.workers.worker_props.WorkerProps
::: zoo_framework.workers.worker_result.WorkerResult
::: zoo_framework.workers.worker_register.WorkerRegister
