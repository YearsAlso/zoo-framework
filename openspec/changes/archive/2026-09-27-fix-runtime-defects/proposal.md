## Why

框架当前**不可运行**：`Master()` 一构造就抛 `TypeError: issubclass() arg 1 must be a class`，事件系统还有 8 处核心路径要么抛异常、要么静默丢弃事件。这些缺陷被 140 个全绿的单测完全掩盖——因为没有任何用例覆盖 `Master` 构造、`EventChannel` 分发、重试策略和 FIFO 查询这几条路径。

`zoo-framework` 已发布到 PyPI（0.5.3-beta），下游拿到的就是不可运行的版本。修复必须在继续加功能之前落地。

## What Changes

**A 组 · 入口可用性（P0）**

- 修复 `@cage` 装饰器与 `WorkerRegistry.register_class` 的契约冲突：`workers/event_worker.py:14` 的 `@cage` 把 `EventWorker` 变成函数，`core/worker_registry.py:64` 的 `issubclass()` 随即抛错，导致 `Master()` 无法构造
- 修复 `lock/base_lock.py:4` 的 `class BaseLock(Lock)`（`multiprocessing.Lock` 是绑定方法不是类），使 `zoo_framework.lock` 包可导入

**B 组 · 事件系统核心逻辑（P0）**

- **BREAKING** `reactor/event_reactor.py`:修正 `RetryNever` 与 `RetryForever` 共用 `while True` 导致的死循环；让 `RetryAlways` 进入分支（当前落到 `raise Exception("未知的事件重试策略")` 且被 `execute()` 吞掉，回调从不执行）
- **BREAKING** `reactor/event_reactor.py`:修正 `get_priority()`——`sys_priority` 被赋值成 `int` 却按 Enum 访问 `.value`
- **BREAKING** `reactor/event_reactor_manager.py`:修正 `dispatch()` 把响应器名当 `topic` 传给 `get_reactor()` 导致 `list.execute` 失败；修复后 worker 结果事件才会真正送达响应器
- **BREAKING** `event/event_channel_manager.py`:修正 `response_mechanism == 2` 分支——`EventReactor` 无 `priority` 属性且 `list.sort()` 返回 `None`
- **BREAKING** `fifo/event_fifo.py` 及 `base_fifo.py` / `single_fifo.py`:修正把 `list.index()` 当作"包含性检查"的用法（未命中会抛 `ValueError`，而调用方 `EventChannel.refresh_event` / `EventProvider.refresh` 的正常路径正是"未命中则不处理"）
- **BREAKING** `fifo/event_fifo.py`:修正 `dispatch(topic, content, provider_name)` 丢弃第三参数，使 `EventChannel` 的通道名真正传到 `EventNode.channel_name`
- **BREAKING** `event/event_channel.py` 与 `fifo/base_fifo.py`:队列存储由类属性改为实例属性（**两层**都要改——`EventChannel._event_fifo` 与 `BaseFIFO._fifo` 都是类属性，只改上层仍会共享底层列表），使通道隔离真正成立。`BaseFIFO` 的类级共享队列是被现有测试刻意验证的契约，改动后 7 个既有 FIFO 用例需改写为实例调用
- **BREAKING** `workers/event_worker.py`:消费循环调用的是**不存在**的 `reactor.perform` 且实参顺序颠倒，事件被从队列弹出后即丢失——端到端投递从未真正发生过。修正为调用 `reactor.execute(topic, content)`

**C 组 · 行为修正（P1）**

- **BREAKING** `statemachine/state_scope.py`:修正无点号的顶层 key 更新被静默忽略（`set_state("S","k",42)` 后 `get_state` 仍返回旧值）
- `workers/async_worker.py`:修正三个 Async 类把 `name: str` 传给 `BaseWorker.__init__(props: dict)` 导致 `self._props` 变成字符串

**测试**

- 上述每条缺陷补一个回归用例：先在当前代码上复现为失败，修复后转绿。回归用例是本次变更的主要验收物

## Capabilities

### New Capabilities

- `worker-lifecycle`:Worker 与 `@cage`/`WorkerRegistry` 的注册契约、Master 可构造性、AsyncWorker 的属性契约
- `event-dispatch`:事件分发语义——重试策略、优先级计算、通道传递与隔离、响应机制、FIFO 查询语义
- `state-machine`:状态作用域的读写语义（含顶层 key 与嵌套 key 的更新一致性）
- `lock-primitives`:锁原语包的可用性与"文档承诺 == 实际行为"契约

### Modified Capabilities

无。`openspec/specs/` 当前为空，本次是首次建立 spec 基线，四个能力均为新建。

## Impact

**受影响代码**

| 模块 | 文件 |
|---|---|
| core | `worker_registry.py`、`aop/cage.py` |
| workers | `event_worker.py`、`async_worker.py` |
| reactor | `event_reactor.py`、`event_reactor_manager.py` |
| event | `event_channel.py`、`event_channel_manager.py` |
| fifo | `event_fifo.py`、`base_fifo.py`、`single_fifo.py` |
| statemachine | `state_scope.py` |
| lock | `base_lock.py`、`count_lock.py`、`time_lock.py` |
| tests | 新增回归用例，涉及 `test_reactor.py`、`test_event.py`、`test_fifo.py`、`test_state_machine.py` 及新增 Master 构造用例 |

**不涉及的边界**

- 不新增运行时依赖、不改 `pyproject.toml` 的依赖列表
- 不涉及类型注解与 CI 门禁（由 `establish-type-gate` 处理）
- 不改 `zoo_framework` 的公开导入路径（`from zoo_framework.core import Master` 等保持可用）
- B 组多条为行为修正，会让"之前静默失败/静默丢弃"的路径开始真正生效。依赖旧有错误行为的下游会观察到差异——这是本次刻意修复的目标，已在 What Changes 中逐条标注 **BREAKING**
