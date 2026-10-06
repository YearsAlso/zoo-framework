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
├── .github/workflows/   build / tests / quality / docs / release
├── pyproject.toml       metadata, dependencies, and all tool config
└── .env                 VERSION (one of the three places the version lives)
```

Three caveats about the tree:

- `test/` (singular) at the root contains only stale `__pycache__` artifacts, not sources.
  The live suite is `tests/`.
- `example/main.py` and `example/event/demo_event.py` are **stale against the current
  API** — `main.py` calls `Master(1)`, and `demo_event.py` imports from
  `build.lib.zoo_framework`. `example/threads/demo_thread.py` is the example that reflects
  current usage.
- The legacy `setup.py` + `script/pro.{sh,bat}` release path was **removed**: `setup.py`
  imported `distutils`, which left the standard library in Python 3.12, so it could not run
  on any Python this project supports (`>= 3.13`). Releases go through `python -m build`
  (hatchling) and the release workflow.

### `zoo_framework/` by concern

```
zoo_framework/
├── __init__.py            __version__
├── __main__.py            forwarding stub for `python -m zoo_framework`; the CLI lives in cli/
├── cli/                   the zfc CLI: click options + error presentation (__init__.py), file output (scaffold.py)
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
└── templates/             scaffold template text as module-level strings (string.Template)
```

| Path | Responsibility |
|---|---|
| `core/master.py` | `Master` — the lifecycle entry point: load config → register Workers → start scheduling → shut down |
| `core/aop/` | The remaining decorators: `params` (resolve `ParamsPath` into literals), `event`, `configure`, `logger`, `stopwatch`. The `cage` decorator was **removed** — process-level sharing is declared through the container instead. `worker`/`worker_register`/`validation` were **retired from the public surface** (#49): the `@worker` module path stays importable for one minor with a `DeprecationWarning`, `validation` is deleted; the only registration path is `Master.register_worker`. The directory holds decorators only: there is **no** aspect-weaving machinery here (no join points, advice, or pointcut matching), despite the `aop` in the name |
| `core/waiter/` | The scheduler. `base_waiter.py` composes a `WorkerDispatchCore` (model-agnostic bookkeeping: single settlement point, timeout observation, shutdown reclaim, runtime registration) with a `SchedulerModel` (`ThreadPerTaskModel` / `ThreadPoolModel`); `waiter_factory.py` builds it from `worker:mode` |
| `core/container/` | The scoped container: `ScopedContainer` (`register` / `resolve` / `exclusive` / `release` / `replace` / `reset`), `Scope` + `ScopeKind` (process / session / prototype handles), `ThreadSafety` (the required thread-safety declaration), `Registration` + `qualified_name` (the module-qualified key), and `registry` — the framework's **own** process-level container plus `process_scoped` / `process_instance`, which register without replacing the class |
| `core/worker_registry.py` | `WorkerRegistry` — a **module-level singleton**, never reset between `Master` instances, and **not** part of the container |
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
| `cli/` | The `zfc` CLI. `__init__.py` parses options and presents errors; `scaffold.py` produces the files. **Dev-time only** — the framework does not import it at runtime |
| `templates/` | Scaffold template text as module-level strings (`string.Template`, no Jinja2), including the markers `zfc --worker` uses to wire a new Worker into the entry point |

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

### Three facts worth knowing before you touch the wiring

**Configuration resolution happens once, at first import of a params module.** `@params`
rewrites each `ParamsPath` into the resolved literal, cached under the module-qualified name
(`cls.__module__` + `cls.__qualname__` — never the bare class name, or two same-named params
classes in different modules would collide and the later one would silently reuse the
earlier one's values). That is why
`zoo_framework.params` is imported lazily (inside `Master._create_waiter`,
`BaseWaiter.__init__` and `StateMachineWorker`) — so `ParamsFactory` has read `config.json`
first. Importing a params class before constructing `Master` freezes the defaults instead.
`ParamsFactory()` with a missing path returns early and leaves the config empty, silently.

**State that outlives a test is not centrally managed — and this section deliberately contains
no inventory of it.** Clearing one carrier is not enough to isolate a test case. The useful
axis is the *mechanism*, and there are three of them:

1. **The container's process-level instances** — the managers declared process-level in
   `core/container/`, so `framework_container().reset()` reclaims them (along with any
   replacements and single-thread bindings).
2. **Class attributes on those managers** — state living on the class rather than on an
   instance, e.g. `EventReactorManager.reactor_map` and `EventChannelRegister._channel_map`;
   the container's reset does not reach it. `@event` writes here at import time.
3. **Module-level globals and registries** — everything else, e.g. `WorkerRegistry`'s instance
   cache, the channel-manager singleton, and the `@configure` / params registries.

A list of carriers written here would go stale — which is precisely why there is none. Two
**checkable** sources take its place:

- **In-tree anchors**: `grep -rn "【已知欠债】" zoo_framework/` marks every carrier currently
  recorded as known debt in the spec baseline. Grep the **bracketed** form: the bare phrase also
  occurs in a prose sentence, so matching it without the brackets reports one more hit than there
  are carriers.
- **The test helpers that actually reset them**: `tests/conftest.py`'s `_reset_registries()`,
  `tests/test_scaffold_cli_contract.py`'s scaffold cleanup, and `tests/test_config_resolution.py`'s
  `config` fixture. Their value over annotations is that they exist **independently of them** —
  resetting is a behaviour, a comment is not.

`EventWorker` is a concrete example of (3): it must remain one instance *per Worker*, so its
docstring records why declaring it process-level would move that ownership out of
`WorkerRegistry`.

**`process_scoped` registers without replacing the class, and CPython imposes three
consequences.** Read this before changing how the framework declares its own process-level
managers, or before writing your own `__new__` delegation:

1. `__new__` returns an instance of `cls`, so `type.__call__` still invokes `__init__` on it.
   `process_scoped` therefore makes `__init__` idempotent — it really runs only once. A class
   with instance state whose `__init__` ran twice would have that state reset;
   `StateMachineManager`'s `_state_scope_map` is the concrete case.
2. The container must construct instances **bypassing** `__new__` (it keeps a reference to the
   original). Otherwise "factory → `cls()` → `__new__` → resolve" recurses back into the
   container.
3. A subclass does **not** inherit process-level identity: when `subcls is not cls`, the normal
   constructor runs. Otherwise decorating a base class would collapse every subclass into one
   shared instance.

Each has a test guarding it, so breaking one fails rather than silently sharing state.

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
├── .github/workflows/   build / tests / quality / docs / release
├── pyproject.toml       元数据、依赖，以及全部工具配置
└── .env                 VERSION（版本号所在的三处之一）
```

三个需要注意的地方：

- 根目录的 `test/`（单数）里只有过期的 `__pycache__` 产物，不是源码。生效的套件是 `tests/`。
- `example/main.py` 与 `example/event/demo_event.py` **已过期，与当前 API 不符** ——
  `main.py` 调用的是 `Master(1)`，`demo_event.py` 从 `build.lib.zoo_framework` 导入。
  反映当前用法的是 `example/threads/demo_thread.py`。
- 遗留的 `setup.py` + `script/pro.{sh,bat}` 发布路径**已删除**：`setup.py` 导入 `distutils`，
  而它在 Python 3.12 已从标准库移除，因此在本项目支持的 Python 版本（`>= 3.13`）上根本
  跑不起来。发布走 `python -m build`（hatchling）与发布工作流。

### `zoo_framework/` 按关注点划分

```
zoo_framework/
├── __init__.py            __version__
├── __main__.py            `python -m zoo_framework` 的转发入口；命令行实现在 cli/
├── cli/                   zfc CLI：click 选项与错误呈现（__init__.py）、脚手架产出（scaffold.py）
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
└── templates/             脚手架模板文本（模块级字符串，string.Template 渲染）
```

| 路径 | 职责 |
|---|---|
| `core/master.py` | `Master` —— 生命周期入口：加载配置 → 注册 Worker → 启动调度 → 停机 |
| `core/aop/` | 余下的装饰器：`params`（把 `ParamsPath` 解析为字面值）、`event`、`configure`、`logger`、`stopwatch`。`cage` 装饰器**已删除** —— 进程级共享改由容器声明。`worker`/`worker_register`/`validation` 已**退出公共面**（#49）：`@worker` 模块路径保留一个 minor 周期并发弃用警告，`validation` 已整删；注册的唯一接通路径是 `Master.register_worker`。该目录只有装饰器：**没有**切面织入机制（无连接点、无通知、无切点匹配），尽管包名里有 `aop` |
| `core/waiter/` | 调度器。`base_waiter.py` 把 `WorkerDispatchCore`（模型无关的簿记：单一结算收口、超时观测、停机资源回收、运行期注册）与 `SchedulerModel`（`ThreadPerTaskModel` / `ThreadPoolModel`）组合起来；`waiter_factory.py` 按 `worker:mode` 装配 |
| `core/container/` | 按作用域解析的容器：`ScopedContainer`（`register` / `resolve` / `exclusive` / `release` / `replace` / `reset`）、`Scope` + `ScopeKind`（进程 / 会话 / 原型三种句柄）、`ThreadSafety`（必填的线程安全声明）、`Registration` + `qualified_name`（模块+限定名的键），以及 `registry` —— 框架**自身**的进程级容器与 `process_scoped` / `process_instance`（登记但**不替换类**） |
| `core/worker_registry.py` | `WorkerRegistry` —— **模块级单例**，在不同 `Master` 实例之间从不重置，且**不属于**容器 |
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
| `cli/` | zfc 命令行。`__init__.py` 解析选项并呈现错误，`scaffold.py` 负责产出文件。**只在开发期使用** —— 框架运行时不导入它 |
| `templates/` | 脚手架模板文本（模块级字符串，`string.Template` 渲染，不用 Jinja2），含 `zfc --worker` 用来把新 Worker 接入入口的插入点标记 |

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

### 改动装配逻辑前需要知道的三件事

**配置解析只发生一次，在对应 params 模块首次导入时。** `@params` 把每个 `ParamsPath`
改写为解析后的字面值，并按**模块 + 限定名**缓存（`cls.__module__` + `cls.__qualname__`，
不用裸类名——否则两个定义在不同模块的同名参数类会互相覆盖，后定义者会静默复用前者的
配置值）。这正是 `zoo_framework.params` 被惰性导入的原因
（在 `Master._create_waiter`、`BaseWaiter.__init__` 与 `StateMachineWorker` 内部）——
好让 `ParamsFactory` 先读完 `config.json`。在构造 `Master` 之前导入某个 params 类，会把
默认值**冻结**下来。`ParamsFactory()` 在路径缺失时会提前返回，并**静默**留下空配置。

**会活过单个用例的状态不是集中管理的 —— 本节刻意不含它的清单。** 只清掉一处不足以隔离用例。
有用的区分轴是**机制**，共三种：

1. **容器的进程级实例** —— 在 `core/container/` 里被**声明**为进程级的那些管理器，因此
   `framework_container().reset()` 会回收它们（顺带清掉替换与单线程绑定）。
2. **这些管理器上的类属性** —— 住在类而非实例上的状态，例如 `EventReactorManager.reactor_map`
   与 `EventChannelRegister._channel_map`；容器复位够不到它。`@event` 在导入时写入这里。
3. **模块级全局与注册表** —— 其余的，例如 `WorkerRegistry` 的实例缓存、通道管理器单例，以及
   `@configure` 与 params 的注册表。

在这里列出载体清单就会过期 —— 这正是本节不列的原因。取代它的是两个**可核对**的来源：

- **代码内锚点**：`grep -rn "【已知欠债】" zoo_framework/` 标出当前在规范基线里被记为已知欠债
  的每一处载体。请用**带括号**的写法：裸短语在正文句子里也出现过一次，不带括号匹配会比载体数
  多报一条。
- **真正执行复位的测试辅助**：`tests/conftest.py` 的 `_reset_registries()`、
  `tests/test_scaffold_cli_contract.py` 的脚手架清理、以及 `tests/test_config_resolution.py`
  的 `config` fixture。它们相对于标注的价值在于**先于标注存在** —— 复位是行为，注释不是。

`EventWorker` 是第 3 类的具体例子：它必须保持「每个 Worker 一个实例」，其 docstring 记录了
为什么把它声明为进程级会把这份归属从 `WorkerRegistry` 挪走。

**`process_scoped` 不替换类，而 CPython 给它带来三条副作用。** 改动框架自身进程级管理器的声明
方式之前、或自己手写 `__new__` 委托之前，请先看这三条：

1. `__new__` 返回的既然是 `cls` 的实例，`type.__call__` 就仍会对它调用一次 `__init__`。因此
   `process_scoped` 把 `__init__` 做成幂等的 —— 真正只跑一次。有实例状态的类若第二次
   `__init__` 真跑了，状态会被重置；具体例子是 `StateMachineManager` 的 `_state_scope_map`。
2. 容器构造实例时**必须绕过** `__new__`（它保存了原始引用）。否则
   「工厂 → `cls()` → `__new__` → 解析」会递归回容器自身。
3. 子类**不**继承进程级身份：当 `subcls is not cls` 时走正常构造。否则给基类加一次装饰器
   会把它的所有子类卷成同一个共享实例。

三条各有用例守护，破坏任何一条都会失败，而不是静默共享状态。
