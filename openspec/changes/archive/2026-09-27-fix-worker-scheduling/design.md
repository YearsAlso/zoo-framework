## Context

本设计的约束来自三处，动机见 `proposal.md · Why`，此处只列会影响技术选型的部分：

- **Worker 体是 Python 可调用对象**。框架的调度器（`core/waiter/`）只决定「谁、何时、在哪个线程上执行」，执行的内容是用户实现的 `_execute()`。任何调度层改造都无法改变这段代码的运行成本。
- **运行时是标准 GIL 构建**。`requires-python = ">=3.13"`；本机 `sys._is_gil_enabled()` 返回 True。CPU 密集的纯 Python 代码在多线程下无法并行。
- **并发模型在当前实现中有三套且互不相通**：Waiter 用裸 `threading.Thread` / `ThreadPoolExecutor`；事件管道用 `gevent`（且**未**启用 monkey patch）；`AsyncWorker` 自带 `asyncio.run()`。`proposal.md` 的 C 组正是要把第三套接进第一套。
- **待修缺陷是语义缺陷，不是性能缺陷**。`proposal.md` 的 P0/P1 全部是契约错误（登记竞态、`is_loop` 语义、上报主题不匹配、`AsyncWorker` 未接调度）。换实现语言不会修复它们。

## Goals / Non-Goals

**Goals:**

- 让 Worker 的调度生命周期（登记 → 派发 → 在飞 → 注销 → 上报）有单一且可验证的收口点，在瞬时完成与长时间运行两种极端下都表现一致
- 让「循环 / 单次」语义、超时策略、结果主题成为**可配置、可声明、可观测**的契约，而非依赖 subclass 是否恰好遮蔽了某个属性
- 让停机成为显式动作：停止调度、回收线程、触发销毁、落盘状态
- 让异步 Worker 成为调度体系中的一等公民，而不是旁挂的独立运行时

**Non-Goals:**

- 不实现进程池模式（`WORKER_MODE_PROCESS*` 本次只做「标注未实现或移出公开 API」的处置）
- 不把全局单例（`WorkerRegistry` / `reactor_map` / `_channel_map`）重构为会话作用域——本次只在必要处加约束，架构级重构另提变更
- 不引入 Rust 核心或任何原生扩展（见 Open Questions 的评估结论）
- 不为提升并发度引入 free-threaded 构建或更换 `requires-python`

## Decisions

以下四项会改变 `specs/` 的 Requirement 措辞与 `tasks.md` 的拆解，因此在此定稿，不留在 Open Questions。

### D1 · 超时语义取「观测 + 熔断」，不引入进程隔离

**选择**：超时后记录错误、标记该 Worker 不健康、**不再重派**该 Worker；已在执行的调用不强制中断。文档与代码同时声明「不支持抢占式强杀」。

**理由**：CPython 无法安全终止一个正在执行的线程（`PyThreadState_SetAsyncExc` 只能在线程回到字节码边界时注入异常，对阻塞在 C 调用或原生 I/O 上的线程无效，且可能破坏解释器状态）。任何声称"已杀死超时 Worker"的实现都会是假的。诚实地把语义限定在可验证的范围内，优于提供一个看起来能终止、实则不可靠的机制。

**已考虑的替代**：用 `ProcessPoolExecutor` 获得真正的终止能力。拒绝理由——Worker 必须可 pickle，跨进程通信需要序列化协议，且 Windows 上进程 `spawn` 实测 93 ms/次，与"高频调度"目标直接冲突。这是另一个产品尺度的工作，不属于本变更。

**承接**：`specs/worker-scheduling` 的「超时 MUST 被观测并熔断」要求；`tasks.md` 5.1–5.6。

### D2 · 结果主题统一，按 Worker 名过滤

**选择**：结果上报使用统一主题常量（沿用现有 `"waiter"` 绑定，改动面最小）；`WorkerResult` 增加 `worker_name` 字段；响应器按 `worker_name` 过滤。

**理由**：`EventReactorManager.get_reactor` 已具备按名过滤能力（`reactor_names` 形参），无需新增机制。若为每个 Worker 生成独立主题，`reactor_map` 会随 Worker 数量线性增长，且需要在运行期动态绑定响应器——这与 D4 要建立的"未实现/未知输入必须被明确拒绝"以及本次的"注册幂等"修复方向相冲突。

**已考虑的替代**：绕过事件管道，`worker_report` 直接调用订阅者回调。拒绝理由——会引入第二套结果投递机制，与既有的事件管道语义（重试、优先级、通道）不一致，且让"Worker 结果"成为框架里唯一不走总线的消息类型。

**承接**：`specs/worker-scheduling` 的「结果上报 MUST 沿事件管道投递且可被按名过滤」要求；`tasks.md` 4.1–4.5。

### D3 · `AsyncWorker` 补齐 `ABCMeta`，让抽象约束真正生效

**选择**：让 `AsyncWorker` 使用 `ABCMeta` 元类，使 `@abstractmethod` 真正阻止未实现 `async_execute` 的类被实例化。

**理由**：当前 `@abstractmethod` 无 `ABCMeta` 配合，是**装饰器与实际行为不一致**——正是本变更要消灭的缺陷类型（见 `proposal.md` 对 `is_loop`、`stop()`、`_destroy` 的同类问题）。移除装饰器会把这个不一致固化下来。

**兼容性核查**：`AsyncEventWorker` 与 `AsyncStateMachineWorker` 均实现了 `async_execute`，加 `ABCMeta` 不破坏二者；`BaseWorker` 不受影响（仍非 ABC）；仓库内唯一直接实例化的地方是测试里的具体子类。公开 API 影响：下游若有 `AsyncWorker` 的未实现子类，将在实例化时收到 `TypeError` —— 属 BREAKING，需写入发布说明。

**承接**：`specs/async-worker-runtime` 的「抽象约束 MUST 真正生效」要求；`tasks.md` 7.5。

### D4 · 未实现的模式常量保留，但 MUST NOT 被静默降级

**选择**：保留 `WORKER_MODE_PROCESS*` 与 `RUN_MODE_*` 常量的值不变（避免导入级 BREAKING），在 `constant/` 中按「已实现 / 未实现占位」分组标注；同时修复真正的危害——**当前对未实现模式与未知策略名存在静默降级**。

**关键事实**：`WaiterFactory.get_waiter(name)` 对任何无法识别的名称静默返回 `SimpleWaiter`；`BaseWaiter.get_worker_mode` 只读 `pool_enable` 布尔值，不存在"模式被拒绝"的路径。也就是说，用户配置写错策略名（如 `"stabel"`）会无声地拿到 simple 语义——这比常量本身更值得修。

**已考虑的替代**：直接从公开 API 移除这些常量。拒绝理由——会造成导入级 BREAKING，且完全没有解决"静默降级"这个真正的问题；常量本身的危害只是"误导"，静默降级的危害是"配置与行为不一致且无从察觉"。

**承接**：`specs/worker-scheduling` 的「未实现的调度模式 MUST NOT 被静默降级」要求；`tasks.md` 5.5。

## Risks / Trade-offs

- **结果主题变更会破坏下游订阅** → `proposal.md` 已标注 BREAKING；落地前需确认框架内无既有消费者（`tasks.md` 1.4 已列为前置校验项），下游变更写入发布说明
- **`is_loop` 由方法变属性同样是 BREAKING** → 下游若写 `worker.is_loop()` 将得到 `TypeError`；`tasks.md` 3.3 要求同步修正仓库内 4 处被旧语义锁定的断言，发布说明中单列
- **超时熔断会改变「挂死 Worker 静默占位」的现状** → 依赖旧行为（挂死 Worker 长期占住池位而不被处理）的下游会观察到 Worker 被停用；这是刻意修复的目标，需在文档中明确「不支持抢占式强杀」的边界
- **测试基础设施变更（全局状态清理）可能暴露既有用例对单例残留的隐性依赖** → `tasks.md` 10.1 与 10.3 要求在引入后全量复跑并复核用例语义

## Open Questions

### Open Question · 调度层是否 Rust 化

**问题**：用 Rust 核心（PyO3 / maturin）承载线程、协程、进程与异步操作的执行调度，是否带来明显的性能优势？

**结论**：**对当前框架的负载形态没有明显优势。** 本变更**不引入** Rust 核心；该问题连同 Server 运行时的可行性，已移入独立变更 `adopt-rust-core`（仅做测量与决策，不含实现）。存在三类边界场景值得在条件成立时重新评估（见下方「触发重新评估的条件」）。

**本问题不影响本变更**：无论结论如何，`proposal.md` 的 A/B/C/D 四组修复都按原样执行。理由见下方「为什么这不是当前缺陷的解」。

**为什么不并入本变更**：本变更的 P0 缺陷已随 `zoo-framework 0.5.3-beta` 发布到 PyPI，属"下游拿到带病版本"的紧急问题，修复窗口是数天；Rust 核心迁移需要新建构建链（`hatchling` → `maturin`）、重建发布流程（当前 `release.yml:282` 的 `python -m build` 需改为多平台 wheel 矩阵）、并承担跨平台编译风险，属数月量级。二者风险量级相差一个数量级，合并后无法独立回滚。此外，迁移需要一个**已验证正确的语义契约**作为对照基线——而当前 `is_loop` 语义与结果上报链路本身就是错的，拿错误基线对照会把错误一并搬迁。

#### 判断依据 1 · Rust 只能替掉调度层，替不掉 Worker 体

Worker 体是用户实现的 Python `_execute()`。Rust 能接管的是「把谁、何时、放到哪个执行单元上跑」，不能接管「跑什么」。

实测各环节成本（环境见文末）：

| 环节 | 实测成本 | Rust 能替掉 |
|---|---|---|
| Waiter 派发一个 Worker（线程池模式） | **13.5 µs / Worker**（10 个 Worker 时 135 µs/轮；100 个时 1464 µs/轮） | ✅ 这是收益的硬上限 |
| Waiter 派发一个 Worker（裸线程模式） | **222–230 µs / Worker**（其中 215 µs 为 `Thread` 创建+启动+回收） | ✅ 但可用池替代，无需 Rust |
| `EventReactorManager.dispatch()` 全路径 | **15.8–18.6 µs / 次** | ✅ |
| 其中 `ThreadSafeDict` 的 `multiprocessing.Lock` | 1531 ns（占该路径 8%） | ✅ 但改用 `threading.RLock` 即可 |
| `gevent.spawn` + `gevent.joinall`（每个响应器一次） | **38.1 µs / 次** | ✅ 但直接调用只需 **47.5 ns** |
| **Worker 体（业务代码）** | **通常 ms 级** | ❌ 占绝对主导 |

即使 Rust 把 13.5 µs 的派发开销降到 **零**，对一个 1 ms 的 Worker 也只快 **1.35%**，对 10 ms 的 Worker 快 **0.13%**。这是 Amdahl 意义上的天花板，与实现质量无关。

框架内最贵的调度环节（`gevent.spawn` + `joinall`，38.1 µs/响应器）**恰恰不需要 Rust**：直接调用同一函数只要 47.5 ns，相差 800 倍。

#### 判断依据 2 · 逐维度的评估

**线程** —— 无优势，且方向性错误。

```
CPU 密集的纯 Python 工作：
  单线程跑 1 份: 120 ms
  4 线程跑 4 份: 509 ms  → 加速比 0.94x（理想 4.0x）
```

Rust 线程回调 Python 函数时必须重新持有 GIL，同一瓶颈原样存在，还额外叠加跨语言调用开销。要获得真并行只有两条路：工作本身在 Rust 里（等于换产品，不是换调度层），或改用 free-threaded 构建 / 进程。后者都不需要 Rust。

**协程** —— 收益对标 uvloop，且本框架当前未使用 asyncio 作为事件管道。

CPython 的 `asyncio` 核心已是 C 实现（`_asyncio`）。Rust 在该位置的对标物是 uvloop，属成熟方案且有已知收益上限（受 Python 回调成本封顶）。实测本机协程开销：task 创建+await 6.9 µs，批量创建+gather 4.3 µs/task。Rust 侧 task 调度在 ns 量级，但在 ms 级 Worker 面前不可观测。

更关键的是：本框架的**事件模式跑的是 gevent（未打 monkey patch，实测 `threading`/`socket`/`time` 均为 stdlib 模块，即零真并发）**，`AsyncWorker` 又自带另一套 `asyncio.run()`。在此前提下谈「用 Rust 加速协程」，等于给尚未接线的部分更换更贵的线材。

**进程** —— 已经是 OS 级并行，Rust 只在编组上有优势。

```
一个空线程  start+join:  215 µs（稳态）
一个空进程  start+join:   93 ms   ← Windows 仅 spawn，无 fork
```

93 ms 由 CPython 的 `spawn` 语义（重新 import 主模块）与 Windows 无 `fork` 共同决定，**Rust 不会让它变便宜**。Rust 在进程维度唯一真实的优势是编组（serde / Arrow / 共享内存替代 `pickle`），但当前 `WorkerResult` 只传一个 `content` 字段，多数路径甚至传 `None` —— 没有大 payload 可优化。

**异步** —— 仅在「I/O 在 Rust 侧完成并释放 GIL」时成立。

Rust + tokio 的价值在于耗时操作整个发生在 Rust 内、期间释放 GIL。若 Worker 体是 `requests.get()` 或 `await` 一个 Python 协程，Rust 帮不上忙。

#### 判断依据 3 · 阻塞 Rust 化的纯 Python 优化（成本对比）

把「把一个任务交给工作线程」这件事拆到最底层，可以看出当前派发开销的构成：

| 实现层次 | 单次成本 | 说明 |
|---|---|---|
| 当前 `ThreadPoolExecutor.submit().result()` | **31.9 µs** | 含 `Future` 记账与阻塞往返 |
| `queue.Queue.put` + 工作线程消费（**无 `Future`**） | **1.86 µs** | 纯 Python 的"线程池下限" |
| 仅创建闭包 | 0.07 µs | 绝对下限 |
| ctypes 回调 Python（PyO3 更快，此为**上界**） | 0.33 µs | 跨语言调用成本量级 |

**当前 13.5 µs 的派发开销中，约 95% 是 `concurrent.futures` 的 Python 记账，不是线程机制本身。** 因此：

```
当前实现             13.5 µs
纯 Python 优化后     ~2 µs      ← 弃用 concurrent.futures 即可达到
Rust 实现            ~0.5–1 µs  ← 相对优化后的 Python 仅快 2–3x
```

**Rust 相对"优化后的纯 Python"的边际收益是 2–3 倍、绝对值 1–2 µs，而非直觉上的 20 倍。** 20 倍是拿 Rust 对比"未优化的现实现"得出的，而后者本来就是免费的 Python 修复。

同一结论在其余热点上重复出现：

| 组件 | 当前 | 纯 Python 修复后 | 差值归属 |
|---|---|---|---|
| `ThreadSafeDict` set + get | **4.62 µs** | ~0.3 µs（换 `threading.RLock`） | Python 可修 |
| `EventFIFO` push + pop | 0.59 µs | ~0.3 µs（换 `deque`） | Python 可修 |
| `gevent.spawn` + `joinall` | 38.1 µs | 0.05 µs（直接调用） | Python 可修 |

也就是说，当前框架 90% 以上的"性能问题"是 Python 层的实现选择问题，而非语言问题。修完之后 Rust 在该层能再拿的只剩零头。

| 优化项 | 实测差距 | 改动成本 |
|---|---|---|
| `ThreadSafeDict` 的 `multiprocessing.Lock` → `threading.RLock` | 2056 ns vs 155 ns vs 无锁 26 ns（**13x**） | 数行 |
| `BaseFIFO` 的 `list.pop(0)` → `deque.popleft` | 队列 10k 时 524 ns vs 42 ns（**12.4x**） | 1 行 |
| 事件管道去 `gevent`，直接调用响应器 | 38.1 µs vs 47.5 ns（**800x**） | 十余行 |
| `Master.run()` 的调度循环改用线程池而非裸 `Thread` | 13.5 µs vs 222 µs（**16x**） | 配置项即可（`worker:pool:enable`） |

这四项合计能拿到的收益**远超**「Rust 化调度层」在该层的上限，且全部可在纯 Python 内完成。

#### 触发重新评估的条件

仅在以下条件**成立时**才值得重新评估本问题：

| 场景 | 成立条件 | 当前是否成立 |
|---|---|---|
| 工作本身用 Rust 实现，Python 只做配置与编排 | 唯一能绕开 GIL 的真并行路径 | ❌ 与框架「decorator 驱动的 Python Worker」的产品定位冲突 |
| 大 payload 的跨 Worker / 跨进程编组 | 序列化开销可被观测 | ❌ 当前 payload 为 `None` 或小对象 |
| 高频、小消息、多 Worker 的消息总线 | 队列与编组确实是瓶颈 | ⚠️ 有潜力，但当前瓶颈是 gevent 与全局锁，纯 Python 可修 |

#### 决策规则

> **只有当 profiler 显示某个纯计算环节占用 > 20% 的总时间，且该环节不含 Python 回调时，Rust 化才值得。** 任一条件不满足，收益都会被 GIL 或跨语言回调成本吃掉。

对应的执行顺序：

1. **阶段 0（必做）**：按本变更修语义缺陷；并行完成上表四项纯 Python 优化
2. **阶段 1（决策前置）**：以真实业务负载做 profile，回答「Worker 体执行时间中位数是多少、调度开销占比多少」
   - 中位数 > 1 ms → Rust 化调度层的收益在 2% 以内，直接否决
   - 中位数 < 100 µs → 调度开销才进入值得优化的量级，继续阶段 2
3. **阶段 2（仅在被证明是瓶颈时）**：把 profile 指认的热点 Rust 化。大概率结论是编组/队列层，而非调度语义层

若目标确实是「真并行」，当前的廉价杠杆是 **free-threaded Python（3.13t / 3.14t）** 与 **进程池**，两者都不需要引入 Rust。

#### 选择 Rust 的确定成本

| 项 | 代价 |
|---|---|
| 构建链 | maturin / PyO3，每平台 × 每 Python 版本出 wheel（abi3 可缓解，但 `requires-python = ">=3.13"` 抬高门槛） |
| CI | 三平台（ubuntu / windows / macos）的 Rust 工具链与编译时间；当前 CI 的 ruff 与 pytest 已是硬门禁 |
| 产品属性 | 失去「纯 Python、pip 可装、可热改」——这是 decorator 驱动 + 插件系统的核心卖点，也是当前能直接发布到 PyPI 的前提 |
| 可调试性 | 混合堆栈（Python frame + Rust frame）；Rust 侧 panic 配置不当会 abort 整个进程，对调度器而言是最坏的失败模式 |
| API 表达力 | `@cage` / `@params` 依赖 import 期改写类属性，无法廉价跨 FFI 边界，要么放弃要么在 Rust 内重建等价物 |
| 与本变更的关系 | `tasks.md` 的 56 条任务全部作废重来 |

#### 为什么这不是当前缺陷的解

`proposal.md` 记录的缺陷全部是**契约错误**，不是性能问题：

- P0-1 的登记/注销竞态
- P0-2 的 `is_loop` 方法被当属性读
- P0-3 的上报主题与响应器绑定不匹配
- P0-4 的 `AsyncWorker` 未接入调度路径

用 Rust 重写调度器，只是把这些语义缺陷换一种语言重新实现一遍，而且因为跨语言调试更难，发现它们的成本更高。因此**无论本问题最终结论如何，阶段 0 都必须执行**——它是唯一不依赖任何后续决策就能立即产生价值的动作。

#### 实测环境与方法

Python 3.13.14（`.venv/Scripts/python.exe`）/ Windows 11 Pro for Workstations / 单机空载。计时使用 `time.perf_counter()`，取多轮最优值以排除调度抖动。`sys._is_gil_enabled()` 为 True，即标准（非 free-threaded）构建。相关依赖版本：gevent 26.9.0。所有数字为量级参考，绝对值随机器与负载变化，但各项之间的数量级关系稳定。

**平台适用性说明（重要）**：本节数字**全部来自 Windows**。后续在 Linux（WSL2, Debian / Python 3.13.5）补测后发现两处数量级差异：

| 项 | Windows | Linux | 倍率 |
|---|---|---|---|
| `multiprocessing.Lock` | 2063 ns | 181 ns | 11.4x |
| `multiprocessing.Lock` ÷ `RLock` | 13.3x | 1.6x | — |
| 进程启动 | 93 ms（spawn） | 12 ms（fork） | 7.75x |

结论不变但**依据需按平台限定**：本文以 `ThreadSafeDict` 的 `multiprocessing.Lock` 为最大热点（依据 4.62 µs 的 set+get），这在 Windows 上是 13.3x 的病灶，在 Linux 上只是 1.6x 的优化项；修复本身（改用 `threading.RLock`）在两个平台都正确且都必须做，但**收益量级具有平台依赖性**。同理，D1 以"Windows 上进程 spawn 93 ms"为由拒绝的"进程隔离获得真超时"方案，在 Linux 上（`fork` 12 ms）可行性显著更高。跨平台的完整方案与对既有决策的修正见 `adopt-rust-core · design.md` 的 D0 与 D6。
