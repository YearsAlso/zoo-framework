# Design: add-task-layer

## Context

见 proposal.md（Why）与 specs/task-queue/spec.md（Requirements）。实现前必须知道的现状与约束：

- **执行单元今天不是任务**：`WorkerDispatchCore.begin` 以 `worker.name` 为在飞表键（同名不可并发），**并发度被表达成"注册多少个名字"**。任务层要引入"任务身份"，但本变更**不改调度器语义**（见 Non-Goals）。
- **可复用的持久化能力已就位**：`StateMachineManager` / `StateScope` 是进程级共享（`@process_scoped(ThreadSafety.INSTANCE_GUARANTEED)`），状态随 `StateMachineWorker` 落盘（整表或增量），**重启即恢复**。任务队列落在这里即免费获得"重启不丢"。
- **可复用的并发原语已就位**（change `add-state-append-and-cas`，A1）：`StateScope` 有 scope 级 `_mutation_lock`（`set_state_node` / `append_state_node` / `compare_and_set` 的读-改-写段统一持锁），`compare_and_set(key, expected_version, value) -> bool` 提供基于节点版本的**乐观并发控制**，版本在每次成功写入后严格递增。
- **取消的诚实基线**：CPython 无法抢占运行中的线程；`WorkerDispatchCore` 在超时熔断处已明确"不声称终止了仍在运行的 Worker"。任务层 MUST 沿用同一诚实度。
- **投递语义未决**：issue #74 裁定事件只保证至少一次、"任务层要不要更强需要单独定"。故本变更**不建幂等收口**，只保证"任务身份在队列内唯一"。
- **A1/A2 未被本变更触碰**：`set_state` 整值替换、`append_state` 追加、`compare_and_set` CAS、观察者、effect、持久化布局与 TTL 的既有契约**均不改动**。

## Goals / Non-Goals

**Goals:**

- 形状 1：一个与 Worker 解耦的任务值对象，字段覆盖身份 / 载荷 / 状态 / 尝试 / 结果 / 错误 / 时间戳。
- 形状 2：一个落到既有状态机持久化作用域的可持久化队列——提交、查询、原子认领、完成 / 失败、重新排队、最小取消。
- **未使用任务层时既有行为不变**；唯一新配置键默认保持现状。
- 每条契约都有对应场景（见 spec delta），可测可验；并发正确性用真实多线程用例证明。

**Non-Goals（明确划出，做了即越界）:**

- **不改调度器并发语义**：任务身份与 Worker 解耦，但**并发度仍以"注册多少个名字"表达**——`WorkerDispatchCore.begin` 的在飞表键、单一结算收口 `settle`、超时熔断、停机幂等、线程池背压**一处不改**。任务队列**不接管派发**：它只提供"可持久化的排队 + 认领"语义，消费者（Worker）自行决定怎么把认领到的任务跑起来。这是**刻意的边界**：把"池容量 = 并发度"的表达留给形状 3。
- **不做形状 3（运行时容量）**：池 `resize`、`add_worker` / `submit` 与启动期走同一套准入、修 #233——**独立立案**，不在本变更。
- **不做形状 4（伸缩信号）**：队列深度驱动的策略、失败 / 退避次数驱动的策略、复用 `WorkerDelayManager`——不在本变更。故本变更**只提供**谓词式的状态查询，**不提供**任何自适应 / 退避策略。
- **不做形状 5（取消语义加强）**：不引入协作式取消令牌、不把取消传播进执行体、不声称能中断已开始的执行。本变更只做"取消尚未启动的"这一最小语义。
- **不做投递幂等**：不建幂等收口、不做去重投递、不承诺恰好一次（issue #74 未决）。
- **不做跨进程 / 分布式队列**：单进程内线程安全即达标。
- **不新增第三方依赖**。

## Decisions

### D1：任务值对象——`Task` dataclass，身份命名 `task_id`

`Task` 为 `@dataclass`，字段：

| 字段 | 含义 | 来源 |
|---|---|---|
| `task_id: str` | 任务身份，调用方给定 | issue 形状 1 的 `id` |
| `payload: Any` | 载荷（任务体入参） | 形状 1 的 `payload` |
| `status: TaskStatus` | 状态 | 形状 1 的 `status` |
| `attempts: int` | 尝试次数（认领时 +1） | 形状 1 的 `attempts` |
| `result: Any \| None` | 成功结果 | 形状 1 的 `result/error` |
| `error: str \| None` | 失败错误 | 形状 1 的 `result/error` |
| `created_at: float` | 创建时间（墙钟） | 形状 1 的 `timestamps` |
| `updated_at: float` | 最近更新时间 | 形状 1 的 `timestamps` |
| `started_at: float \| None` | 开始执行时间 | 时间戳细化 |
| `finished_at: float \| None` | 结束时间 | 时间戳细化 |

- **命名**：属性取 `task_id` 而非 `id`——`id` 与内建 `id()` 同名易误读，且框架既有日志词表已用 `task_id`（`utils/structured_log.py` 的示例）。issue 的字段清单是"建议"，此处**显式改名**并在 proposal/design 说明。
- **构造入口**：`Task.new(payload, task_id=None)` 类方法，`task_id` 为 `None` 时用 `uuid4().hex` 生成；`created_at` / `updated_at` 用 `time.time()`。直接构造需显式给时间戳（测试可注入）。提供 `to_dict()` / `from_dict()` 做持久化编解码。
- **时间基**：任务时间戳是**墙钟** `time.time()`——因为它们要**跨重启**表达"何时创建 / 何时开始"，`time.monotonic()` 跨进程无意义。`WorkerDispatchCore` 的 `time.monotonic()` 契约不受影响（任务层不碰它）。

### D2：状态用 `StrEnum`，迁移合法性集中在队列

`TaskStatus(StrEnum)`：`PENDING="pending"` / `RUNNING="running"` / `SUCCEEDED="succeeded"` / `FAILED="failed"` / `CANCELLED="cancelled"`。用 `StrEnum`（Python 3.11+，与下界一致）使 `TaskStatus.PENDING == "pending"` 为真、`str()` 即字面值，持久化后仍可 `TaskStatus(value)` 还原。

合法迁移表（`_ALLOWED`）集中在队列模块，非法迁移**显式失败**（认领 / 完成返回"未生效"，不抛错的部分见下）：

```
pending   -> running（认领）｜ cancelled（取消）
running   -> succeeded（完成）｜ failed（失败）｜ pending（重新排队）
failed    -> pending（重新排队）
succeeded/cancelled -> （终态）
```

- **为什么迁移合法性放队列而非 `Task`**：`Task` 是纯值对象（可构造、可序列化、无副作用），迁移的原子性与合法性判定必须与"读-改-写"同处一个临界区；放在 `Task` 上会诱使调用方在临界区外改状态。
- **失败信号形式**：认领 / 完成 / 失败 / 重新排队**返回迁移后的 `Task`**，不满足前置条件（任务不存在、状态不允许）时返回 `None`；取消返回 `bool`。这与 A1 的 CAS"冲突用返回值表达、参数非法才抛错"一致；重复身份提交是**调用方错误**故抛错。

### D3：持久化形态——每个队列一个**列表节点**，存任务字典

队列在状态机上只用一个**顶层节点**承载（键 `"tasks"`，无点分、不触发状态机的树构造），节点值是一个**按提交顺序排列的任务字典列表**。任务以 `Task.to_dict()` 落进去，读回时 `Task.from_dict()`。

- **为什么"单节点 + 列表"而不是"一个任务一个节点"**：(a) 提交顺序天然由列表顺序承载，无需另设顺序索引；(b) 查询 / 过滤在一个节点上完成；(c) 迁移只需对一个节点做 CAS，无需先按前缀枚举再逐个比较；(d) 键不引入用户可控的点分串（任务身份可能含点，若做节点键会被状态机的 `key.split(".")` 误当树路径）。代价是**状态迁移的成本是 O(n)（整列表重写）**——在本能力的定位（首个可持久化队列、单进程）下可接受，且已在此处显式记为取舍。
- **为什么不用 A1 的 `append_state` 做提交**：`append_state` 是无条件追加，无法原子地拒绝重复身份（D6）。故提交与迁移**统一走 `compare_and_set` 的乐观读-改-写**（`_mutate`），使"唯一性检查 + 追加"处于同一 CAS 内。

### D4：原子性——复用 scope 级锁 + CAS，仅新增一把"节点引导锁"

所有变更走 `_mutate`：读节点值与版本 → 在内存里构造新列表 → `scope.compare_and_set(key, 版本, 新列表)`；CAS 返回 `False`（并发写入了）则**重试**，重试耗尽抛错而非静默丢更新。

- **正确性来源**：`compare_and_set` 与 `append_state` 都持同一个 scope 级 `_mutation_lock` 且比较版本，任何并发写入都会推高版本使 CAS 失败 → 重试。因此"先检查再写"的两步窗口被版本检查兜住，**不丢更新**。
- **唯一新增的锁——队列节点的"引导锁"**：节点首次创建需要"存在则跳过、不存在才建空列表"。`StateScope` 没有原子的"create-if-absent"，故用一个**模块级 `threading.Lock` + 双重检查**完成"建一次空列表"（与 `state_node.py` 中 `_effect_executor` 的双重检查懒建同形）。它只守护**创建那一步**，创建之后全部走 CAS；这样"两个并发提交者都观察到节点不存在、其中一个建了空列表又被另一个覆盖"的窗口被消除。该锁是 `threading.Lock`（非可变容器），不触发 `process_state` 的载体扫描；不进容器（它守护的是临界的**创建动作**，不是进程级共享状态）。
- **替代方案**：per-queue 实例锁包裹全部操作——更简单但把并发退化为串行，且与"复用既有 CAS"矛盾；不做。

### D5：`TaskQueue` 不是 `@process_scoped`，只是 `StateMachineManager` 的薄门面

队列由一个**作用域名**参数化（默认取配置键，见 D6）：`TaskQueue(scope=..., manager=None)`。它不 `@process_scoped`——因为进程级单例会把"不同名字的多个队列"折叠成同一个；也把 `TaskQueue()` 的构造语义改成"总是同一个实例"，与"按作用域区分队列"冲突。它内部经进程级 `StateMachineManager()` 读写，故多实例共享同一份持久化真源。

- **测试注入点**：构造参数 `manager` 允许传入 `StateMachineManager`（测试用）或省缺取进程级单例。

### D6：唯一新增配置键 `task:queue:scope`（默认保持现状），运行期读取

`TaskParams.QUEUE_SCOPE = param(value="task:queue:scope", default="zoo.tasks")`。`TaskQueue` 在**构造期**（运行期）惰性导入并读取它——与 `StateMachineManager.create_scope` / `StateMachineWorker.__init__` 同法，避免 `@params` 在模块导入期冻结默认值。`aliases` 机制此处不需要（无历史键名要吸收），故只给一个正路径。

- **默认保持现状**：不配置该键时默认作用域是 `"zoo.tasks"`；不计入任何既有作用域，不产生任何副作用。不使用任务层的应用行为逐字节不变。
- **不新增其它键**：队列不引入容量 / 并发 / 重试 / 退避配置——那些属于形状 3/4（Non-Goals）。

### D7：模块布局 `zoo_framework/tasks/`

新增包：`task.py`（`TaskStatus` + `Task`）、`task_queue.py`（`TaskQueue`）、`__init__.py`（导出三者为公共 API）。放在顶层独立包而非塞进 `statemachine/`，因为任务层是**新能力**（有自己的身份与生命周期语义），只在**存储**上依赖状态机；反过来让 `statemachine` 依赖任务语义会污染稳定层的边界。依赖方向：`tasks -> statemachine`（单向），`statemachine` 不反向依赖 `tasks`。

## Risks / Trade-offs

- [迁移成本 O(n)（整列表 CAS 重写）] → 首个版本按"简单正确优先"取舍，并在本文件显式记录；若日后成为瓶颈，可改为"一名一节点 + 顺序索引"，属追加而非改契约。
- [`Task` 可 pickle 性依赖 `payload` 可 pickle] → 状态机持久化本就是 pickle；不可 pickle 的载荷会在落盘时报错（既有日志），属既有边界，文档注明。
- [引导锁是模块级设施] → 与 `_effect_executor_lock` 同形，已在此说明其守护范围仅"建一次空列表"，不承载业务状态；`process_state` 扫描只覆盖可变容器，锁不在其列。
- [取消被误解为"能中断"] → 用 spec 的 MUST NOT 条文 + 专门用例把"只能阻止尚未启动的"钉死。
- [唯一性拒绝被误解为幂等承诺] → spec 明写"不含投递幂等承诺"，并有用例固定。

## Migration Plan

- **无数据 / 配置迁移**：任务层是纯新增入口，不使用即零变化。回滚即还原代码；队列数据落在状态机作用域里，回滚后旧数据成为普通状态作用域内容（合法整数 / 列表），无残留故障态。
- 下游衔接：形状 3（#233）可在本变更合入后，把"容量 = 并发度"的表达建在任务层之上，而无需改本变更定义的队列契约。
