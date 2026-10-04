## Why

Waiter 调度器与 Worker 多模式实现存在**成对且方向相反**的缺陷：声明"只跑一次"的 Worker 每个 tick 都会重复执行（`is_loop` 定义为方法却被调用方按属性读取，bound method 恒为真），而"瞬时完成"的 Worker 在线程池模式下执行一次后**永久停摆**（`submit` 后先挂 done-callback、后写登记表，任务体内已抢先注销，残留记录使该 Worker 再不被派发）。两者叠加，表现为"有时能跑、有时静默僵死，且没有任何日志"。

结果上报链路在两处独立断裂：线程模式根本不接 done-callback；线程池模式虽有回调，但 Worker 上报的主题是 `<类名>_result`，而 `WaiterResultReactor` 绑在 `"waiter"` 主题上——实测该响应器自注册起从未被触发过。

超时控制是整段死代码（`worker_band` 无任何副作用，取消逻辑被注释，`run_timeout` 无配置入口故恒为 `None`）；`Master.shutdown()` 不停止 Waiter、不取消调度任务、不落盘状态机；`AsyncWorker` 未覆写 `_execute`，在调度器下**完全不执行**（占一个线程空睡 `delay_time` 后返回空结果）。

`zoo-framework` 已发布到 PyPI（0.5.3-beta），下游拿到的是调度不可靠的版本。现有 208 个用例全绿，说明上述路径**零覆盖**。

## What Changes

**A 组 · 调度器生命周期（P0）**

- **BREAKING** `core/waiter/base_waiter.py`:消除提交/登记竞态——登记必须在 `submit` 之前完成，注销与上报统一由一个 Future 的 done-callback 收口，`worker_running` 不再接收 `callback` 参数。修复后瞬时完成的 Worker 不再永久停摆
- **BREAKING** `workers/base_worker.py`:`is_loop` 由方法改为 `@property`，`_props` 成为唯一真源；同步删除 `EventWorker`/`StateMachineWorker` 中遮蔽它的实例属性赋值。修复后按 props 声明"只跑一次"的 Worker 不再重复执行
- `core/waiter/base_waiter.py`:线程模式补上结果上报（此前 `WorkerResult` 被直接丢弃）
- **BREAKING** `workers/base_worker.py` 与 `reactor/waiter_result_reactor.py`:结果上报主题统一。`WorkerResult` 由类名小写拼接改为显式主题，并携带 Worker 名称以支持按名过滤；依赖旧 `<类名>_result` 主题的下游需同步调整

**B 组 · 超时控制与停机（P1）**

- `core/waiter/base_waiter.py`:超时控制落地为"观测 + 熔断"——给出默认超时与 Worker 级覆盖入口，超时后记录错误、标记不健康、不再重派该 Worker。文档与代码同时明确**不支持抢占式强杀**，避免维持"定义了但永不生效"的现状
- `params/worker_params.py`:补齐 Worker 调度相关配置入口（默认超时、默认循环标志、默认延迟、按 Worker 名覆盖），使调度器读配置而非只读 Worker 自报的 props
- `core/master.py`:`shutdown()` 全链路停机——取消调度任务、停止 Waiter、等待在飞 Worker、触发 Worker 销毁钩子（含状态机落盘）；`run()` 为调度任务挂异常回调，`perform()` 抛异常时记录并停止，而非让 `run_forever()` 空转成假死

**C 组 · 异步 Worker 与调度体系接合（P0）**

- `workers/async_worker.py`:覆写 `_execute`，使 `async_execute` 真正在调度路径上被执行、返回值进入 `WorkerResult`；异常显式传播而非丢失
- `workers/async_worker.py`:`run_in_background` 的兜底线程改为 daemon 并保存异常供 `result()` 重抛；`AsyncWorkerPool` 的信号量与队列改为按当前事件循环惰性创建；抽象约束补齐或移除，不再出现"看起来强制、实则可实例化"

**D 组 · 事件管道可靠性（P1）**

- `workers/event_worker.py` 与 `event/event_channel_manager.py`:事件不得静默丢失——队列竞态导致的空元素、响应器缺失、通道查询异常三条路径都要么回队要么进死信，不得弹出即丢；无响应器且声明了重试次数的事件真正按次数重试
- `core/waiter/base_waiter.py` 与 `reactor/event_reactor_manager.py`:响应器注册幂等——同一对象在同一主题下重复注册不得重命名、不得重复追加（当前每构造一次 `Master` 就多一条，进程内无限增长）
- `reactor/event_reactor_manager.py`:`@event(topic, channel=...)` 声明的通道约束在 `dispatch` 路径真正生效（当前仅 `register_reactor_channels` 被测试调用，框架自身从不注册，声明了 `business` 通道的响应器会被默认通道触发）

**测试**

- 上述每条缺陷补一个回归用例：先在当前代码上复现为失败，修复后转绿
- 改写 2 条"锁死错误语义"的既有用例：`tests/test_worker.py:23`、`tests/test_zoo_framework.py:52` 现断言 `worker.is_loop() is True`，`is_loop` 改为属性后需同步修正

## Capabilities

### New Capabilities

- `worker-scheduling`:调度循环的派发与在飞管理、循环/单次语义、超时策略与熔断、停机与资源回收、运行期注册的生效性
- `async-worker-runtime`:异步 Worker 在调度器下的执行与结果返回、异常传播、后台运行的线程约束与资源归属

### Modified Capabilities

- `worker-lifecycle`:Worker 注册后的**调度生效性**发生变化——运行期注册的 Worker 必须进入调度（当前只写注册表不刷新调度列表）；`is_loop` 由方法变更为属性，配置读取路径随之改变
- `event-dispatch`:新增"事件不得静默丢失"与"响应器注册幂等"两条要求；通道约束在 `dispatch` 路径的生效性由"声明即可"改为"声明与执行一致"

## Impact

**受影响代码**

| 模块 | 文件 |
|---|---|
| core | `core/waiter/base_waiter.py`、`core/waiter/safe_waiter.py`、`core/waiter/simple_waiter.py`、`core/master.py` |
| workers | `workers/base_worker.py`、`workers/event_worker.py`、`workers/state_machine_work.py`、`workers/async_worker.py`、`workers/worker_result.py` |
| event / reactor | `workers/event_worker.py`、`event/event_channel_manager.py`、`reactor/event_reactor_manager.py`、`reactor/waiter_result_reactor.py` |
| params | `params/worker_params.py` |
| tests | 新增回归用例（建议 `tests/test_waiter_dispatch.py`、`tests/test_async_worker_integration.py`），改写 `tests/test_worker.py`、`tests/test_zoo_framework.py` 中的 `is_loop` 断言 |

**公开 API 影响（**BREAKING**）**

- `BaseWorker.is_loop` 由方法变属性：下游若写 `worker.is_loop()` 将得到 `TypeError: 'bool' object is not callable`
- Worker 结果事件主题变更：订阅 `<类名>_result` 的下游需改订统一主题
- `BaseWaiter.worker_running(worker, callback=None)` 的 `callback` 形参移除

**不涉及的边界**

- 不新增强制运行时依赖，不改 `pyproject.toml` 的依赖列表
- 不实现进程池模式：`WORKER_MODE_PROCESS*` 与 `RUN_MODE_*` 常量在本次仅做"标注未实现或移出公开 API"的处置，不补齐实现
- 不重构全局单例为会话作用域（`WorkerRegistry` / `reactor_map` / `_channel_map` 的进程级共享本次只在必要处加约束，架构级重构另行提变更）
- 不涉及类型注解与 CI 门禁（由 `establish-type-gate` 处理）。两处有交叠：`establish-type-gate` 的任务 1.1 要求本变更先落地后再重取类型错误基线
- 不改 `zoo_framework` 的公开导入路径（`from zoo_framework.core import Master` 等保持可用）
- D 组多条会让"此前静默失败/静默丢弃"的路径开始真正报错或重试。依赖旧有静默行为的下游会观察到差异——这是本次刻意修复的目标，已在 What Changes 中逐条标注 **BREAKING**
