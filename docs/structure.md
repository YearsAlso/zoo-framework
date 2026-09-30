# 目录结构 / Repository structure

[English](#english) | [中文](#中文)

本文说明仓库与 `zoo_framework/` 包的物理布局，以及各部分承担的职责。
行为层面的设计见 [`ARCHITECTURE.md`](ARCHITECTURE.md)。

---

<a name="english"></a>
## 🇬🇧 English

### Repository root

```
zoo-framework/
├── zoo_framework/       the package (the only thing shipped in the wheel)
├── tests/               the live test suite — 367 cases, 23 files
├── docs/                deep-dive documentation
├── example/             usage examples (see the caveat below)
├── bench/               Rust feasibility measurement & decision — NOT product code
├── openspec/            specs + in-flight changes (spec-first workflow)
├── script/              legacy release scripts (pro.sh / pro.bat → setup.py + twine)
├── .github/workflows/   build / tests / quality / docs / release
├── pyproject.toml       metadata, dependencies, and all tool config
├── setup.py             legacy build path, reads the version from .env
└── .env                 VERSION (one of the three places the version lives)
```

Two caveats about the tree:

- `test/` (singular) at the root contains only stale `__pycache__` artifacts, not sources.
  The live suite is `tests/`.
- `example/main.py` and `example/event/demo_event.py` are **stale against the current
  API** — `main.py` calls `Master(1)`, and `demo_event.py` imports from
  `build.lib.zoo_framework`. `example/threads/demo_thread.py` is the example that reflects
  current usage.

### `zoo_framework/` by concern

```
zoo_framework/
├── __init__.py            __version__
├── __main__.py            the zfc / zoo CLI: scaffolding (--create) and worker adding (--worker)
├── core/                  lifecycle and scheduling
├── workers/               the execution units
├── event/ + fifo/ + reactor/    the event pipeline
├── statemachine/          state store, scopes and persistence
├── params/                configuration schema
├── constant/              shared constants (mode names, policies, topics)
├── lock/                  lock primitives (base / count / time)
├── utils/                 log, file, datetime, thread-safe dict, command helpers
├── conf/                  log configuration
├── plugin/                the whole plugin system, in one module
└── templates/             scaffold templates consumed by the CLI (*.pyt)
```

| Path | Responsibility |
|---|---|
| `core/master.py` | `Master` — the lifecycle entry point: load config → register Workers → start scheduling → shut down |
| `core/aop/` | The process-global decorators: `cage` (singleton factory), `params` (resolve `ParamsPath` into literals), `event`, `worker`, `configure`, `logger`, `stopwatch`, `validation` |
| `core/waiter/` | The scheduler. `base_waiter.py` composes a `WorkerDispatchCore` (model-agnostic bookkeeping: single settlement point, timeout observation, shutdown reclaim, runtime registration) with a `SchedulerModel` (`ThreadPerTaskModel` / `ThreadPoolModel`); `waiter_factory.py` builds it from `worker:mode` |
| `core/worker_registry.py` | `WorkerRegistry` — a **module-level singleton**, never reset between `Master` instances |
| `core/params_factory.py`, `core/params_path.py` | `config.json` loading, `_exports` resolution, and the `ParamsPath` value handle |
| `core/persistence_scheduler.py` | Atomic-write + checksum + rolling-backup persistence, reusable outside the state machine |
| `workers/base_worker.py` | `BaseWorker` — `_execute()` is the single extension point; `is_loop` / `run_timeout` / `delay_time` are properties read from `_props` |
| `workers/event_worker.py` | Drains every channel, drops expired nodes, requeues retryable ones, runs reactors concurrently |
| `workers/state_machine_work.py` | Loop worker: loads the pickle on the first pass, saves on subsequent ones |
| `workers/async_worker.py` | `AsyncWorker` — coroutine workers on the scheduler path |
| `event/` | `EventChannel` + channel registry. `event_channel_register.py` lazily creates channels; each channel owns an `EventFIFO` |
| `fifo/` | Queue implementations (`base` / `single` / `delay` / `event`) plus `fifo/node/` for the event and delay node types |
| `reactor/` | `EventReactor` + manager, priority calculation, retry strategies, and the `waiter` topic's result reactor |
| `statemachine/` | `StateMachineManager` → `StateScope` → pluggable `StateIndex`; `state_node.py` holds the read/write node, `state_effect*.py` the side effects |
| `params/` | One schema class per concern (`worker` / `event` / `log` / `stateMachine`) |
| `constant/` | `waiter_constant.py` (implemented modes, result topic) and `worker_constant.py` (run policies, kinds) |
| `plugin/` | `Plugin` ABC, `PluginManager` (registration, dependency ordering, `load_from_path`), delay strategies |
| `templates/` | `main.pyt` / `thread.pyt`, rendered by `__main__.py` when scaffolding |

### Boot and data flow

```
Master.__init__          ParamsFactory reads config.json (+ _exports)
                         → @configure callbacks run (log config)
                         → StateMachineWorker / EventWorker registered as classes
                         → SVMWorker starts on a daemon thread
                         → _create_waiter() builds the scheduler from worker:mode

Master.run               asyncio task loops waiter.execute_service() every 1s
                         → per Worker: timed out? circuit-break
                                       in flight? skip this round
                                       otherwise → dispatch to a thread / the pool
                         → on completion: unregister in-flight, report to the event pipeline
```

### Two facts worth knowing before you touch the wiring

**Configuration resolution happens once, at first import of a params module.** `@params`
rewrites each `ParamsPath` into the resolved literal, cached by class name. That is why
`zoo_framework.params` is imported lazily (inside `Master._create_waiter`,
`BaseWaiter.__init__` and `StateMachineWorker`) — so `ParamsFactory` has read `config.json`
first. Importing a params class before constructing `Master` freezes the defaults instead.
`ParamsFactory()` with a missing path returns early and leaves the config empty, silently.

**The decorators are process-global.** `@cage` returns a singleton cached by class name, and
`@event` registers a reactor at import time. State on caged classes (`EventReactorManager`'s
`reactor_map`, the channel manager's `_channel_map`) is therefore shared across the whole
process and can leak between tests. `WorkerRegistry` is a module-level singleton for the
same reason.

---

<a name="中文"></a>
## 🇨🇳 中文

### 仓库根目录

```
zoo-framework/
├── zoo_framework/       包本体（wheel 里唯一发布的东西）
├── tests/               生效的测试套件 —— 367 条用例，23 个文件
├── docs/                深入文档
├── example/             使用示例（注意下面的例外）
├── bench/               Rust 可行性测量与决策 —— 不属于产品代码
├── openspec/            规范 + 在途变更（规范先行工作流）
├── script/              遗留发布脚本（pro.sh / pro.bat → setup.py + twine）
├── .github/workflows/   build / tests / quality / docs / release
├── pyproject.toml       元数据、依赖，以及全部工具配置
├── setup.py             遗留构建路径，从 .env 读版本号
└── .env                 VERSION（版本号所在的三处之一）
```

两个需要注意的地方：

- 根目录的 `test/`（单数）里只有过期的 `__pycache__` 产物，不是源码。生效的套件是 `tests/`。
- `example/main.py` 与 `example/event/demo_event.py` **已过期，与当前 API 不符** ——
  `main.py` 调用的是 `Master(1)`，`demo_event.py` 从 `build.lib.zoo_framework` 导入。
  反映当前用法的是 `example/threads/demo_thread.py`。

### `zoo_framework/` 按关注点划分

```
zoo_framework/
├── __init__.py            __version__
├── __main__.py            zfc / zoo CLI：脚手架（--create）与新增 Worker（--worker）
├── core/                  生命周期与调度
├── workers/               执行单元
├── event/ + fifo/ + reactor/    事件管道
├── statemachine/          状态存储、作用域与持久化
├── params/                配置 schema
├── constant/              共享常量（模式名、策略、主题）
├── lock/                  锁原语（base / count / time）
├── utils/                 日志、文件、日期时间、线程安全字典、命令执行辅助
├── conf/                  日志配置
├── plugin/                整个插件系统，集中在一个模块
└── templates/             CLI 消费的脚手架模板（*.pyt）
```

| 路径 | 职责 |
|---|---|
| `core/master.py` | `Master` —— 生命周期入口：加载配置 → 注册 Worker → 启动调度 → 停机 |
| `core/aop/` | 进程级装饰器：`cage`（单例工厂）、`params`（把 `ParamsPath` 解析为字面值）、`event`、`worker`、`configure`、`logger`、`stopwatch`、`validation` |
| `core/waiter/` | 调度器。`base_waiter.py` 把 `WorkerDispatchCore`（模型无关的簿记：单一结算收口、超时观测、停机资源回收、运行期注册）与 `SchedulerModel`（`ThreadPerTaskModel` / `ThreadPoolModel`）组合起来；`waiter_factory.py` 按 `worker:mode` 装配 |
| `core/worker_registry.py` | `WorkerRegistry` —— **模块级单例**，在不同 `Master` 实例之间从不重置 |
| `core/params_factory.py`、`core/params_path.py` | `config.json` 加载、`_exports` 解析，以及 `ParamsPath` 取值句柄 |
| `core/persistence_scheduler.py` | 原子写入 + 校验和 + 滚动备份，可在状态机之外复用 |
| `workers/base_worker.py` | `BaseWorker` —— `_execute()` 是唯一扩展点；`is_loop` / `run_timeout` / `delay_time` 是从 `_props` 读取的属性 |
| `workers/event_worker.py` | 清空所有通道、丢弃过期节点、重入可重试节点、并发执行响应器 |
| `workers/state_machine_work.py` | 循环 Worker：第一轮加载 pickle，之后各轮保存 |
| `workers/async_worker.py` | `AsyncWorker` —— 走调度路径的协程 Worker |
| `event/` | `EventChannel` 与通道注册表。`event_channel_register.py` 惰性创建通道，每个通道持有一条 `EventFIFO` |
| `fifo/` | 队列实现（`base` / `single` / `delay` / `event`），以及 `fifo/node/` 下的事件与延迟节点类型 |
| `reactor/` | `EventReactor` 与管理器、优先级计算、重试策略，以及 `waiter` 主题的结果响应器 |
| `statemachine/` | `StateMachineManager` → `StateScope` → 可插拔的 `StateIndex`；`state_node.py` 持读写节点，`state_effect*.py` 持副作用 |
| `params/` | 一个关注点一个 schema 类（`worker` / `event` / `log` / `stateMachine`） |
| `constant/` | `waiter_constant.py`（已实现的模式、结果主题）与 `worker_constant.py`（运行策略、Worker 类别） |
| `plugin/` | `Plugin` 抽象基类、`PluginManager`（注册、依赖排序、`load_from_path`）、延迟策略 |
| `templates/` | `main.pyt` / `thread.pyt`，脚手架时由 `__main__.py` 渲染 |

### 启动与数据流

```
Master.__init__          ParamsFactory 读取 config.json（及 _exports）
                         → 运行所有 @configure 回调（日志配置）
                         → 把 StateMachineWorker / EventWorker 以类形式注册
                         → SVMWorker 在守护线程上启动
                         → _create_waiter() 按 worker:mode 装配调度器

Master.run               asyncio 任务每秒循环一次 waiter.execute_service()
                         → 遍历每个 Worker：已超时？→ 熔断
                                             仍在执行？→ 本轮跳过
                                             否则 → 派发到线程 / 资源池
                         → 执行结束时：注销在飞状态，把结果投递进事件管道
```

### 改动装配逻辑前需要知道的两件事

**配置解析只发生一次，在对应 params 模块首次导入时。** `@params` 把每个 `ParamsPath`
改写为解析后的字面值，并按类名缓存。这正是 `zoo_framework.params` 被惰性导入的原因
（在 `Master._create_waiter`、`BaseWaiter.__init__` 与 `StateMachineWorker` 内部）——
好让 `ParamsFactory` 先读完 `config.json`。在构造 `Master` 之前导入某个 params 类，会把
默认值**冻结**下来。`ParamsFactory()` 在路径缺失时会提前返回，并**静默**留下空配置。

**装饰器是进程级的。** `@cage` 返回按类名缓存的单例，`@event` 在导入时注册响应器。因此
被 cage 的类上的状态（`EventReactorManager` 的 `reactor_map`、通道管理器的 `_channel_map`）
在整个进程内共享，并且可能在测试之间泄漏。`WorkerRegistry` 出于同样的原因是模块级单例。
