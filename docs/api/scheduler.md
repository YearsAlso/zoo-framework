# 调度

调度模型与背压策略。`worker:mode` 选择执行模型，`worker:runPolicy` 设置池的背压。

已实现三种执行模型：

- `thread`（`ThreadPerTaskModel`）：每次派发一个线程，无背压；
- `thread_pool`（`ThreadPoolModel`）：有界资源池，由 `worker:runPolicy` 决定池满行为；
- `event_loop`（`EventLoopModel`）：独立守护线程上的**常驻事件循环**，只接纳协程 Worker（`AsyncWorker` 子类）。整段运行期只创建一个循环，多个等待型协程调用可并发推进而无需每等待一线程；解决的是**等待**而非计算吞吐，同步/CPU 密集代码不得进入循环线程（应经 `run_in_executor` 移出）。停机 `stop_semantics = stop_dispatch_cancel_queued`：已开始的协程不被中断，尚未开始的被丢弃。

::: zoo_framework.core.waiter.base_waiter.BaseWaiter

## 调度模型

::: zoo_framework.core.waiter.scheduler_model

## 派发与结算

::: zoo_framework.core.waiter.dispatch_core

## 常量

::: zoo_framework.constant.worker_constant.WorkerConstant
::: zoo_framework.constant.waiter_constant.WaiterConstant
