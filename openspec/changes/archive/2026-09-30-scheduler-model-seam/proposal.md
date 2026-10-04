## Why

项目声明了两个方向（`ROADMAP.md` 把 IoT/嵌入式开发者列为第一目标用户；用户新提出 Agent 开发），但**它们对执行模型的要求方向相反**，而项目现在只有一个执行模型：

| | Agent 线 | 设备线 |
|---|---|---|
| 负载 | I/O 密集、长跑、海量会话 | 时序敏感、短周期、少量回路 |
| 需要 | 能挂起、能恢复、并发高 | 绝不停顿、抖动有界 |
| 投递语义 | 恰好一次（涉及付费工具调用） | 控制至多一次；报警至少一次 |

差异目前只落在三个近乎相同的策略类里：`StableWaiter` 只覆写了 `__init__`，`SimpleWaiter` 与 `SafeWaiter` 只覆写 `call_workers`，其余全部继承 `BaseWaiter`。也就是说"运行策略"这个公开概念实际上**没有承载任何模型差异**。

同时框架缺两个横切原语：

- **时间**。`delay_time` 的语义是"执行完再 sleep"（`BaseWorker.run` 末尾），周期因此**逐轮累积漂移**；没有周期/相位/抖动/截止期传播的概念。`fix-worker-scheduling` 已把 `time.monotonic()` 用于在飞计时与停机期限，但那只服务于内部审计，没有对外的时间契约。
- **运行标识**。事件、状态作用域、日志三者之间**没有任何关联键**——一次运行跨了多少 Worker、改了哪些状态、产生了哪些事件，事后无法串联，也无法按会话隔离与回放。

`fix-worker-scheduling` 已把调度层的正确性修好（`is_loop` 语义、派发登记竞态、单一收口、超时观测熔断、停机回收、运行期注册生效），这给了本变更一个可信地基。本变更在此之上**提取模型接缝并补上这两个原语**，让两条目标线能在同一地基上分岔，而不必各自重写调度。

## What Changes

**1. 调度模型接缝（`scheduler-model`）**

- 引入显式的调度模型接口，每个模型 MUST 声明：并发原语、时间语义（周期驱动或事件驱动）、背压策略、停机语义、支持的 Worker 类别、可观测指标
- 把 `BaseWaiter` 中**与模型无关**的正确性逻辑下沉为共享实现：单一结算收口、超时观测与熔断、停机资源回收、运行期注册生效
- `Simple`/`Stable`/`Safe` 三个策略映射到模型实现，**`worker-scheduling` 已生效的 8 条要求 MUST 全部继续成立**（这是本变更最硬的约束）
- 选择 MUST 显式：模型不支持请求的 Worker 类别或时间语义时 MUST 明确拒绝，MUST NOT 降级（延续 `worker-scheduling` 的"不可静默降级"）

**2. 时间语义（`execution-time`）**

- **单调基准**：所有区间、期限、抖动计算 MUST 以单调时钟为基准；墙钟 MUST NOT 参与区间运算（沿用已落地的 `time.monotonic()` 用法并将其固化为契约）
- **声明式周期与相位**：Worker SHALL 可声明执行周期与相位；调度 MUST 以**周期为基准**排期，而非"上一轮执行完再 sleep"——后者会累积漂移
- **抖动可观测**：周期调度 MUST 记录实际抖动（实际触发时刻与理论触发时刻之差），并提供查询入口。设备线的验收依赖这个数字，MUST NOT 只给平均值而无分布
- **截止期传播**：调用方 SHALL 可给一次执行附带截止期，该截止期 MUST 能随事件传递到 Worker；超期后 MUST 被观测并熔断。延续既有语义：**MUST NOT 声称已终止**（Python 无法安全终止线程）

**3. 运行标识（`run-identity`）**

- 引入两级标识：`run_id`（一次逻辑运行）与 `session_id`（会话/上下文归属）
- 标识 MUST 贯穿事件（事件入队时记录）、状态（状态作用域归属可查）、日志（结构化字段），使一次运行可被完整串联与回放
- 标识 MUST 可跨线程与跨调度模型传播，MUST NOT 因序列化或线程切换丢失

## Capabilities

### New Capabilities

- `scheduler-model`:调度模型的显式契约、选择、能力声明与不做降级的拒绝语义，以及模型无关的正确性逻辑的归属
- `execution-time`:单调时间基准、声明式周期与相位、抖动观测、截止期传播与超期熔断
- `run-identity`:运行与会话标识的生成、跨线程/跨模型传播，以及在事件、状态、日志三处的贯穿

### Modified Capabilities

- `worker-scheduling`:调度器由"三个策略类"重构为"模型接缝 + 模型实现"。既有 8 条要求（循环/单次语义、单一收口、超时观测熔断、异常不中断调度、结果沿事件管道投递、停机回收、运行期注册生效、不可静默降级）MUST 全部继续成立；并新增"模型 MUST 声明能力，不支持时必须明确拒绝"

## Impact

**受影响代码**

| 模块 | 文件 |
|---|---|
| core/waiter | `base_waiter.py`（模型无关逻辑下沉）、`waiter_factory.py`（策略 → 模型映射）、`simple_waiter.py`/`stable_waiter.py`/`safe_waiter.py`（映射或退场） |
| workers | `base_worker.py`（周期/相位/截止期的声明入口）、`worker_result.py`（结果携带标识） |
| event / fifo | `fifo/node/event_fifo_node.py`（事件携带标识）、`event/event_channel.py` |
| params | `worker_params.py`（周期/相位的配置入口） |
| utils | `log_utils.py`（结构化字段承载标识） |
| tests | 新增模型契约、周期/抖动、标识贯穿的用例；`worker-scheduling` 已生效的 8 条要求的回归用例 MUST 全绿 |

**公开 API 影响（BREAKING）**

- `SimpleWaiter`/`StableWaiter`/`SafeWaiter` 若退场，直接构造它们的下游需改用模型名（`WaiterFactory` 已对未知策略明确拒绝，退场会走这条路径）
- 周期语义变更：声明了周期的 Worker 触发时刻将不再受上一轮执行时长影响——依赖旧漂移行为的下游会观察到差异
- `WorkerResult` 增加标识字段；按位置解包的下游需调整

**不涉及的边界**

- **不引入进程隔离**。`fix-worker-scheduling` 的 D1 明确取"超时观测 + 熔断，不引入进程隔离"，本变更不反转该决定；进程宿主属设备线的独立变更
- 不实现设备线特化（协议适配、看门狗、失效安全、告警语义）
- 不实现 Agent 线特化（context/state 层、工具调用协议、流式、预算策略、HITL）
- 不引入 Rust，不改 `pyproject.toml` 的依赖列表
- 不做 gevent 移除与 `ThreadSafeDict` 换锁等性能优化——`bench/DECISION.md` 已把它们量化为 12x–800x 并记录为**尚未分配到任何变更**，本变更只要求模型声明其并发原语，不承担替换
- 不追求硬实时。本变更只提供抖动**可观测**与周期**不漂移**，是否达到硬实时属设备线的技术选型决定
