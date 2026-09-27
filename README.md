<div align="center">

<img src="https://mxstorage.oss-cn-beijing.aliyuncs.com/oss-accesslog/zf-main-logo.png" alt="Zoo Framework Logo" width="400"/>

# 🎪 Zoo Framework

**后台任务编排框架** —— 调度 Worker、投递事件、持久化状态

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue)](https://www.python.org/)
[![PyPI](https://img.shields.io/pypi/v/zoo-framework)](https://pypi.org/project/zoo-framework/)
[![License](https://img.shields.io/badge/License-Apache%202.0-green.svg)](LICENSE)
[![Tests](https://github.com/YearsAlso/zoo-framework/workflows/Tests/badge.svg)](https://github.com/YearsAlso/zoo-framework/actions)

[English](#english) | [中文](#中文)

</div>

---

<a name="english"></a>
## 🇬🇧 English

### What it is

Zoo Framework runs **long-lived background tasks** in Python. You declare task units
("Workers"), register them, and the framework keeps them running: it decides when each
one is dispatched, keeps concurrent instances apart, observes how long they take, and
shuts down cleanly with state on disk.

It is **not** a web framework and **not** a task queue — there is no HTTP layer, no
broker, and no distributed scheduling. It is the in-process equivalent: a scheduler, an
event pipeline, and a state store that you embed in a service.

The extension surface is deliberately narrow — **subclass, implement `_execute`,
register** — and every unsupported input fails loudly rather than degrading silently.
That makes it well suited to **AI-agent-generated code**: short diffs, no glue code to
get wrong, and a test suite that can judge a change automatically.
See [Built for AI-agent-generated code](#built-for-ai-agent-generated-code).

### Capabilities

| Capability | Status |
|---|---|
| **Multi-threaded scheduling** | ✅ Two modes: `thread` (one thread per dispatch) and `thread_pool` (bounded pool) |
| Loop / single-shot workers | ✅ Declared via `is_loop` |
| In-flight tracking & timeouts | ✅ Observe + circuit-break. The framework does **not** force-kill a running worker |
| **Coroutine workers** | ✅ `AsyncWorker` subclasses execute on the scheduler path. Each execution gets its own event loop (`asyncio.run`), so separate workers do not share an event loop |
| **Multi-process execution** | ❌ **Not implemented.** The mode constants are placeholders and a request for them is explicitly rejected |
| Event pipeline | ✅ Channel isolation, priority ordering, retry strategies, dead-letter records |
| State persistence | ✅ Periodic + on-shutdown save, atomic replace, rolling backups |
| Worker registration | ✅ By class, instance, or factory; lazy instantiation; metadata, tags, priority |
| Health monitoring (SVM) | ⚠️ Metric pipeline not yet wired — `get_health_report()` always reports `execute_count: 0` |

### Installation

```bash
pip install zoo-framework
```

### Quick Start

```python
from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker

class MyWorker(BaseWorker):
    """A task unit that runs in a loop."""

    def __init__(self):
        super().__init__({
            "is_loop": True,      # keep running across scheduling rounds
            "delay_time": 1.0,    # seconds to wait after each execution
            "name": "MyWorker",
            # "run_timeout": 30,  # optional: observe + circuit-break after 30s
        })
        self.counter = 0

    def _execute(self):
        self.counter += 1
        print(f"Hello from MyWorker! Count: {self.counter}")

if __name__ == "__main__":
    master = Master()
    # Registered workers join the schedule. Master() alone only runs the two
    # built-in system workers (EventWorker / StateMachineWorker).
    master.register_worker("MyWorker", MyWorker)
    master.run()
```

> **Do not decorate a Worker with `@cage`.** It replaces the class with a factory
> function, and `WorkerRegistry` validates with `issubclass` — registration fails with
> `TypeError: issubclass() arg 1 must be a class`. `@cage` is a singleton factory for
> *service* classes, not a thread-safety wrapper.

### How it runs

```
Master.run()
   └─ scheduling round (every 1s)
        ├─ for each registered Worker:
        │    ├─ timed out?        → circuit-break, stop dispatching it
        │    ├─ still in flight?  → skip this round
        │    └─ otherwise         → dispatch to a thread / the pool
        └─ on completion: unregister in-flight, report result to the event pipeline
```

Workers execute **concurrently** within a round and are never dispatched twice at the
same time. `Master.shutdown()` stops dispatch first, then cancels the scheduling task,
stops the event loop, stops monitoring, and finally unregisters every Worker — which is
where the state machine's last save happens.

### Performance

Measured on Windows, Python 3.13, with a representative workload (JSON encode/decode +
string processing). `bench/` has the scripts and raw data.

| Worker body | End-to-end | Framework overhead | Share |
|---|---|---|---|
| ~0.04 ms | 0.133 ms | 0.094 ms | 71% |
| ~0.29 ms | 0.391 ms | 0.102 ms | 26% |
| ~2.7 ms | 2.858 ms | 0.124 ms | 4.3% |
| ~10.3 ms | 10.551 ms | 0.219 ms | 2.1% |

Framework overhead is roughly **100–220 µs per task** and is dominated by thread
dispatch and the wake-up back to the scheduler. It is therefore negligible for
millisecond-scale work and dominant for sub-100 µs work — pick your task granularity
accordingly. `bench/DECISION.md` has the breakdown and the cross-platform caveats.

### Built for AI-agent-generated code

The extension surface is deliberately narrow, so generated code is short, verifiable,
and — when it is wrong — wrong *loudly*.

**Three steps, no glue code**

```python
class OrderSyncWorker(BaseWorker):          # 1. subclass
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})

    def _execute(self):                     # 2. write only the business logic
        sync_orders()

master.register_worker("OrderSync", OrderSyncWorker)   # 3. register
```

Thread management, concurrency limits, in-flight de-duplication, timeout
circuit-breaking, graceful shutdown and state persistence are the framework's job.
An agent does not have to generate that code — and therefore cannot get it wrong.

**Configuration is separate from implementation**

A Worker only depends on the `props` dict handed to `__init__`. It has no visibility
into framework internals, so generating one does not require reading the source or
understanding how `Waiter` / `WorkerRegistry` / `EventReactor` relate.

**Failures are explicit, never silently swallowed**

| Input | Behaviour |
|---|---|
| A scheduler mode that isn't implemented (`process`) | raises `NotImplementedError` |
| An unrecognised run-policy name in config | raises `ValueError` |
| Importing a public name that doesn't exist | `ImportError` |
| A text file in an unexpected encoding | emits a warning naming the file |

This matters more for generated code than for hand-written code: an agent **cannot
detect a silent downgrade**, and a loud error is the signal it needs to self-correct.

**Changes can be checked automatically**

The framework carries a spec baseline and a 313-case regression suite covering the
core contracts, so an agent's change can be judged by running `pytest` rather than by
asking a human to read it.

### Documentation

- [Architecture](docs/ARCHITECTURE.md) — module layout and data flow
- [API Reference](docs/API_REFERENCE.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Contributing](docs/CONTRIBUTING.md)

### License

Apache License 2.0 © [XiangMeng](https://github.com/YearsAlso)

---

<a name="中文"></a>
## 🇨🇳 中文

### 这是什么

Zoo Framework 用来运行**长期存活的后台任务**。你声明任务单元（Worker）并注册它们，
框架负责让它们持续跑下去：决定每一个何时被派发、避免并发实例互相干扰、观测它们跑了
多久、并在停机时把状态干净地落盘。

它**不是** Web 框架，也**不是**任务队列 —— 没有 HTTP 层、没有 broker、没有分布式调度。
它是进程内的等价物：一个可以嵌进服务里的调度器 + 事件管道 + 状态存储。

框架的扩展面被刻意收窄 —— **继承、实现 `_execute`、注册**，三步；且所有不受支持的
输入都会**显式报错**而非静默降级。这使它很适合 **AI Agent 生成代码**：改动短、没有
容易写错的胶水代码、且有测试套件可以自动判断改动对错。
详见[面向 AI Agent 的代码生成](#面向-ai-agent-的代码生成)。

### 能力清单

| 能力 | 状态 |
|---|---|
| **多线程调度** | ✅ 两种模式：`thread`（每次派发一个线程）与 `thread_pool`（有界资源池） |
| 循环 / 单次 Worker | ✅ 由 `is_loop` 声明 |
| 在飞管理与超时 | ✅ 观测 + 熔断。框架**不会**强制终止正在执行的 Worker |
| **协程 Worker** | ✅ `AsyncWorker` 子类在调度路径上执行。每次执行使用独立事件循环（`asyncio.run`），因此不同 Worker 之间不共享事件循环 |
| **多进程执行** | ❌ **未实现**。模式常量是占位，请求会被显式拒绝 |
| 事件管道 | ✅ 通道隔离、优先级排序、重试策略、死信记录 |
| 状态持久化 | ✅ 周期落盘 + 停机落盘，临时文件原子替换，滚动备份 |
| Worker 注册 | ✅ 支持类 / 实例 / 工厂，延迟实例化，元数据、标签、优先级 |
| 健康监控（SVM） | ⚠️ 指标链路尚未接通 —— `get_health_report()` 恒返回 `execute_count: 0` |

### 安装

```bash
pip install zoo-framework
```

### 快速开始

```python
from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker

class MyWorker(BaseWorker):
    """一个循环执行的任务单元。"""

    def __init__(self):
        super().__init__({
            "is_loop": True,      # 跨调度轮次持续执行
            "delay_time": 1.0,    # 单次执行结束后的等待秒数
            "name": "MyWorker",
            # "run_timeout": 30,  # 可选：超过 30 秒则熔断
        })
        self.counter = 0

    def _execute(self):
        self.counter += 1
        print(f"Hello from MyWorker! 计数: {self.counter}")

if __name__ == "__main__":
    master = Master()
    # 注册后的 Worker 才会进入调度。只 Master() 的话只会跑内置的两个
    # 系统 Worker（EventWorker / StateMachineWorker）。
    master.register_worker("MyWorker", MyWorker)
    master.run()
```

> **不要用 `@cage` 装饰 Worker。** 它会把类替换成工厂函数，而 `WorkerRegistry` 用
> `issubclass` 校验契约，注册会抛 `TypeError: issubclass() arg 1 must be a class`。
> `@cage` 是给**服务类**用的单例工厂，不是线程安全包装器。

### 运行方式

```
Master.run()
   └─ 调度轮次（每秒一次）
        ├─ 遍历已注册的 Worker：
        │    ├─ 已超时？        → 熔断，不再派发
        │    ├─ 仍在执行？      → 本轮跳过
        │    └─ 否则            → 派发到线程 / 资源池
        └─ 执行结束时：注销在飞状态，把结果投递进事件管道
```

同一轮里多个 Worker **并发**执行；同一个 Worker 永远不会被同时派发两次。
`Master.shutdown()` 先停止派发，再取消调度任务、停事件循环、停监控，最后注销全部
Worker —— 状态机的最后一次落盘就发生在这条链路的末尾。

### 性能

Windows / Python 3.13 实测，负载为代表性任务（JSON 编解码 + 字符串处理）。
脚本与原始数据在 `bench/`。

| Worker 体耗时 | 端到端 | 框架开销 | 占比 |
|---|---|---|---|
| ~0.04 ms | 0.133 ms | 0.094 ms | 71% |
| ~0.29 ms | 0.391 ms | 0.102 ms | 26% |
| ~2.7 ms | 2.858 ms | 0.124 ms | 4.3% |
| ~10.3 ms | 10.551 ms | 0.219 ms | 2.1% |

框架自身开销约为**每任务 100–220 µs**，主要来自线程派发与调度线程的唤醒。因此它对
毫秒级任务是可忽略的，对 100 µs 以下的任务则占主导 —— 任务粒度请据此选择。
拆解与跨平台说明见 `bench/DECISION.md`。

### 面向 AI Agent 的代码生成

框架的扩展面被刻意收窄，使生成的代码短、可校验，而且 —— 出错时**出错得很大声**。

**三步接入，没有胶水代码**

```python
class OrderSyncWorker(BaseWorker):          # 1. 继承
    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 5, "name": "OrderSync"})

    def _execute(self):                     # 2. 只写业务逻辑
        sync_orders()

master.register_worker("OrderSync", OrderSyncWorker)   # 3. 注册
```

线程管理、并发上限、在飞去重、超时熔断、优雅停机、状态落盘全部由框架承担。
Agent 不需要生成这些代码，也就不会把它们生成错。

**配置与实现分离**

Worker 只依赖传给 `__init__` 的 props 字典，不感知框架内部结构。生成一个 Worker
不需要读框架源码，也不需要理解 `Waiter` / `WorkerRegistry` / `EventReactor` 之间的关系。

**失败是显式的，不会被静默吞掉**

| 输入 | 行为 |
|---|---|
| 请求未实现的调度模式（如 `process`） | 抛 `NotImplementedError` |
| 配置里写了无法识别的运行策略名 | 抛 `ValueError` |
| 导入不存在的公开名称 | `ImportError` |
| 文本文件编码与预期不符 | 输出告警并指明文件 |

这一点对生成式代码比对人工代码更重要：**Agent 无法从"静默降级"中察觉自己写错了**，
而明确的报错正是它自我修正所需的信号。

**改动可被自动校验**

框架带 spec 基线与 313 条回归用例，核心契约都有对应用例守护 —— Agent 生成的改动
可以靠 `pytest` 判断对错，而不必靠人逐行读。

### 核心概念

框架用动物园隐喻命名，但**隐喻只影响命名，不影响语义** —— 看不懂名字时看右列即可：

| 隐喻 | 对应组件 | 职责 |
|------|----------|------|
| 🦁 **Worker** | `BaseWorker` 子类 | 任务执行单元，实现 `_execute()` |
| 👨‍🌾 **Master** | `Master` | 生命周期入口：加载配置、注册 Worker、启动调度、停机 |
| 🍽️ **Waiter** | `core/waiter/` | 调度器。三种策略：`simple`（池不足时自动扩容）/ `stable`（按配置）/ `safe`（超限拒绝） |
| 🏠 **Cage** | `@cage` | **单例工厂**：按类名缓存实例。与线程安全无关 |
| 🍎 **Event** | `EventNode` / `EventChannel` | Worker 间通信的事件，带通道、优先级与重试次数 |
| 🥘 **FIFO** | `EventFIFO` | 每个通道一条独立队列 |
| 📢 **Reactor** | `EventReactor` | 事件响应器：`@event(topic, channel=...)` 注册 |
| 🔄 **StateMachine** | `StateMachineManager` | 按「作用域 + 键路径」读写状态，支持观察者与落盘 |

### 事件管道

```python
from zoo_framework.core.aop import event

@event(topic="order.created", channel="business")
def on_order_created(req):
    print(req.topic, req.content)
```

事件按通道隔离；同一事件可选择响应机制（仅首个 / 按优先级 / 全部 / 指定响应器）。
响应器注册是幂等的 —— 同一对象重复注册不会重复追加。

### 状态机

按「作用域 + 键路径」读写，键路径支持点号嵌套：

```python
from zoo_framework.statemachine import StateMachineManager

sm = StateMachineManager()

sm.set_state("order", "status", "pending")     # 首次写入自动创建作用域
sm.set_state("order", "status", "paid")        # 重复写入覆盖
sm.get_state("order", "status")                # -> 'paid'

sm.set_state("order", "item.count", 2)         # 嵌套键
sm.get_state("order", "item.count")            # -> 2

# 观察状态变化
sm.observe_state("order", "status", lambda payload: print(payload["value"]))
sm.unobserve_state("order", "status", observer)
```

状态由 `StateMachineWorker` 周期落盘，停机时再保存一次（写入 `.tmp` 后原子替换，
并在相邻的 `backups/` 目录保留最近 5 份备份）。

### CLI 工具

```bash
# 生成一个脚手架项目（产出 <name>/src/{main.py,workers,conf,params,events}）
zfc --create myapp

# 在项目里新增一个 Worker（写入 src/workers/，并接入 src/main.py 的注册表）
cd myapp
zfc --worker my_task

# 启动
python src/main.py
```

### 文档

- [架构设计](docs/ARCHITECTURE.md) — 模块划分与数据流
- [API 参考](docs/API_REFERENCE.md)
- [开发指南](docs/DEVELOPMENT.md)
- [贡献指南](docs/CONTRIBUTING.md)

### 贡献代码

```bash
git clone https://github.com/YOUR_USERNAME/zoo-framework.git
pip install -e ".[dev]"
pre-commit install
pytest
```

### 许可证

Apache License 2.0 © [XiangMeng](https://github.com/YearsAlso)

---

<div align="center">

🎪 **Happy Coding in the Zoo!** 🦁

</div>
