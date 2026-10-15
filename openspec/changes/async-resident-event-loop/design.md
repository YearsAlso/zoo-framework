# Design: async-resident-event-loop（issue #235）

## Context

见 proposal.md。关键既有事实（已核对代码与规格）：

1. 执行模型契约由 `scheduler-model` 规格钉死为六项可程序化查询的声明（并发原语、支持的时间语义、背压策略、停机语义、支持的 Worker 类别、可观测指标），且明确写着"新增调度模型 MUST NOT 重新实现"模型无关的五类正确性逻辑（单一结算收口、超时观测与熔断、停机回收、运行期注册、周期排期）——也就是说**规格本来就为"再增一个模型"留了位置**。
2. 模型选择是显式的、拒绝不做降级：`BaseWaiter.validate_worker_mode` 与 `WaiterFactory.get_waiter` 都以 `WaiterConstant.IMPLEMENTED_WORKER_MODES` 为唯一真相源。
3. `WorkerDispatchCore` 是模型无关的收口：`begin`（登记并捕获运行标识）→ 模型 `submit` → `run_and_settle`（`worker.run()` 取结果）→ `settle`（清登记、盖章、投递结果）。`worker.run()` 是全仓唯一构造 `WorkerResult` 的地方（#228 之后失败也由它构造）。
4. `AsyncWorker._execute` 目前 `asyncio.run(self._execute_async())`；`_get_semaphore` 按当前 loop 惰性重建（规格「并发控制 MUST 归属于当前事件循环」）。
5. `Master.run()` 在**主线程**上 `new_event_loop()` + `run_forever()` 驱动 1 秒节拍的 `perform()`；调度轮次发生在那个主线程循环里。

## Goals / Non-Goals

**Goals**

- 常驻一个事件循环（创建/复用/关闭有明确归属），消除"每次派发建一个 loop"；
- 让"同一个 Worker 同时推进 N 个等待中的调用"成为可表达的形态，且**工作线程数不随 N 增长**；
- 与既有契约完全对齐：单一结算收口、结果主题与 `WorkerResult` 不变、在飞表与超时熔断不变、停机幂等不变、超时"不声称终止"的诚实性不变；
- 把"同步/CPU 工作不得进入循环线程"变成**可拒绝的契约**，而不是一句口号。

**Non-Goals**

- 不追求 CPU 吞吐（常驻循环解决的是**等待**，不是计算）；
- 不把同步阻塞 Worker（含 `subprocess`）"自动搬运"到线程池——静默搬运会掩盖"这段代码正在饿死循环"，且与"MUST NOT 静默降级"冲突；
- 不动 `thread` / `thread_pool` 的既有行为（`AsyncWorker` 在它们下面继续 `asyncio.run`）；
- 不与 #88（原生 CPU 任务脱离解释器）合并，两者正交；
- 不做任务层语义（Task / 队列 / 容量，属 #234）。

## ① 常驻事件循环的生命周期

| 阶段 | 归属与动作 |
|---|---|
| 创建 | `EventLoopModel.start(core)`：新建 `asyncio.new_event_loop()`，在**独立守护线程**（建议命名 `zoo-event-loop`）上 `run_forever()`。不在 `__init__` 建——容器生命周期归模型的 `start`，与 `ThreadPoolModel.start` 建池同形 |
| 复用 | 整个模型实例（一个 Waiter = 一个 Master）存活期内**同一个** loop；派发用 `asyncio.run_coroutine_threadsafe(coro, loop)`（该 API 本身即跨线程安全） |
| 关闭 | `teardown(core, wait, timeout)`：① 先置"未启动"，使 `submit` 按既有契约拒绝新派发；② 在界内等待在飞协程结算（`wait` 为真时，口径同 `ThreadPoolModel._join_threads` 的**总预算**语义而非每任务一份）；③ `loop.call_soon_threadsafe(loop.stop)`；④ join 循环线程；⑤ `loop.close()`；⑥ 标记未启动 |
| 停机幂等 | `BaseWaiter.shutdown()` 已由 `core.mark_stopped()` 保证"只有第一次生效"，模型 `teardown` 再自行保证"重复调用安全"——两层幂等，与规格「停机 MUST 可重复调用」一致 |
| 与 Master 启停 | `Master.__init__` → `_create_waiter` 构造 Waiter（模型只构造、未启动）；`waiter.call_workers(...)` → `prepare_workers` + `start`（循环线程在此起来）；`Master.shutdown()` → `waiter.shutdown()` → 模型 `teardown` |
| 次序硬约束 | 必须先等在飞协程结算完再停循环：否则结算回调永不执行，结果不投递、在飞表残留 |
| 与主线程循环的关系 | 两者是**不同线程上的两个 loop**，MUST NOT 混用：`Master.run()` 的 loop 只服务 1 秒节拍，常驻 loop 只服务协程 Worker。派发发生在主线程循环里，故 `run_coroutine_threadsafe` 的线程安全是这条设计成立的前提 |

## ② 与既有 SchedulerModel 共存：新执行模型，不是 Worker 级行为

**结论：新增 `EventLoopModel`（执行模型），而不是把它做成 `AsyncWorker` 的私有行为。** 理由：

1. issue 的核心收益（"同一 Worker 同时推进 N 个在飞请求"、线程不随并发线性增长）是**派发与容器**的性质——`scheduler-model` 规格把"并发原语与容器生命周期"明确划归模型；写成 Worker 级行为则派发仍按线程进行，一条线程仍被一次等待占满，收益落空。
2. 规格已为新增模型写好契约（六项声明 + 复用五类共享逻辑），新模型是**既有契约内的扩展**，不是例外。
3. 共存方式是"按 `worker:mode` 选择"：`event_loop` 与 `thread` / `thread_pool` 并列，`process` / `process_pool` 继续被显式拒绝；未显式配置时仍由 `worker:pool:enable` 推导，现有部署零变化。
4. 回退路径天然存在：`AsyncWorker` 在 thread / thread_pool 下继续 `asyncio.run`，使用者不改配置就完全维持既有形态。

### D2（**分歧点**）：协程 Worker 的驱动路径与结果契约缝合点

模型托管协程后，`submit` 不再有线程调用 `worker.run()`，而结果契约（`WorkerResult` 构造、#228 的失败标记、运行标识盖章）今天只在 `BaseWorker.run()` 与 `settle` 两处。三种候选形态：

| 形态 | 做法 | 收益 | 代价 |
|---|---|---|---|
| **P1** 模型托管 + 模型侧重塑结果契约 | `submit` = `run_coroutine_threadsafe(...)`，完成回调在循环线程上结算；模型侧自行构造 `WorkerResult`（含失败标记） | 不占工作线程（达成 issue 目标） | 结果契约出现**第二份实现**，#228 的失败语义必须逐条镜像，否则两种模型下"失败结果"不一致——长期漂移风险高 |
| **P2** 循环复用 + 仍按线程派发 | 模型仍是线程模型，`AsyncWorker._execute` 在常驻循环上 `run_coroutine_threadsafe(...).result()` | 仅"不再每次建/关循环" | N 个在飞仍占 N 条线程，issue 的核心诉求**未达成** |
| **P3** 模型托管 + `base_worker.py` 开缝 | 同 P1，但把"由已得值产出结果"抽成 `BaseWorker` 上的入口，`run()` 与模型托管路径共用同一份契约 | 契约唯一、无漂移 | 需改 `workers/base_worker.py`（**已授权**，见下方裁决）|

**裁决（已完成）**：**P3**。维护者裁定，允许改 `workers/base_worker.py`——原"明确禁止改动"的约束解除。理由：P1 会让结果契约出现第二份实现、#228 的失败语义须逐条镜像，两种模型下"失败结果"可能不一致，长期漂移风险高；P3 以"纯抽取"消除该风险，且要求 `run()` 行为**逐字节不变**。P2 不满足 issue 目标（N 个在飞仍占 N 条线程），仅作对照，不选。

## ③ `event_loop` 原语：实现，不从公开面移除

**选择：实现**（新增声明该原语的模型）。理由：

1. 它正是本 issue 要兑现的能力；移除等于把"框架有能力做异步调度模型"这一声明删掉，与 issue 方向相反，且删一个公开常量属 BREAKING。
2. **移除并不减少任何含糊**：`IMPLEMENTED_WORKER_MODES` 是唯一真相源，`validate_worker_mode` / `get_waiter` 对未登记模式**明确拒绝**（不是静默降级），所以"常量已声明但无模型"今天不构成失真承诺——规格要求的是"未实现的常量 SHALL 显式标注其状态"，`CONCURRENCY_PROCESS` 已是同类先例（占位 + 显式拒绝）。
3. 实现后三处一致：`CONCURRENCY_EVENT_LOOP` 有声明它的模型、模式进 `IMPLEMENTED_WORKER_MODES`、`describe()` 六项可查——正好把"名不副实"的疑点清零。

**代价（即阻塞项 1）**：登记模式必须改 `zoo_framework/constant/waiter_constant.py`，该文件原不在允许范围，**已获维护者授权**（见「裁决结果」4.2）。

## ④ 同步/原生 CPU 工作绝不放进事件循环线程

三层处置，缺一不可：

1. **准入拒绝（硬契约）**：`EventLoopModel.supported_worker_kinds = (WORKER_KIND_ASYNC,)`；`prepare_workers` 对非协程能力 Worker（`isinstance(worker, AsyncWorker)` 为假）**明确拒绝**，错误信息列出可选模型，MUST NOT 静默改用别的模型、MUST NOT 自动改派线程池。依据 `scheduler-model` 规格「模型选择 MUST 显式且不做降级」。这也顺手堵住"CPU 密集 Worker 误配 event_loop"这一事故形态。
2. **Worker 级硬约束（文档 + 检查）**：`async_execute` 内 MUST NOT 直接写阻塞调用（同步 I/O、CPU 密集计算、`subprocess.run`、`time.sleep`）；需要时 MUST 用 `loop.run_in_executor(...)`（或 `asyncio.to_thread`）把阻塞段**显式**移出循环线程。理由：循环线程被占住会让**所有**协程与取消一起停摆——那不是"这一个 Worker 慢"，而是整条事件管道的等待侧停摆。
3. **不说反话**：文档 MUST NOT 宣称常驻循环能提升 CPU 吞吐；与 #88 的分工要写明——那里换执行体（脱离解释器），这里让等待不占线程。

## ⑤ 取消/超时的既有语义如何适用

- **超时**：`WorkerDispatchCore.reap_timeout` 一行不改，仍是"记录 + 标记不健康 + 停止派发"。常驻循环让"超时后真的停掉它"显得更可能，但 `asyncio.Task.cancel()` 只是向协程投递 `CancelledError`，协程若停在同步阻塞段（或等待不可取消的原语）就不会响应——系统 MUST NOT 因此声称已终止，规格里"MUST NOT 声称已终止或中断了仍在执行的 Worker"原样适用。
- **停机取消**：`stop_semantics = STOP_CANCEL_QUEUED`。已提交但**尚未开始**的协程在停机时被丢弃（等价于线程池的"丢弃未开始的排队任务"）；**已开始**的协程不被中断。理由：常驻循环里"已排队未开始"是可判定的（尚未拿到执行权的回调/协程），这使"取消"有一个诚实、可验证的边界，且与 thread_pool 的对外语义同形。
- **可选加强项（已裁决：不做）**：是否允许调用方显式声明"停机时取消已开始的协程"——这是新增语义（会与"不声称终止"的诚实性表述发生张力）。维护者裁定**默认不做**：停机 MUST NOT 取消已开始的协程，只丢弃尚未开始的协程（`stop_semantics = STOP_CANCEL_QUEUED`）。
- **时间基准**：仍 `time.monotonic()`；常驻循环的等待时长一律以单调时钟计算。
- **措辞纪律**：`describe()` 的 `stop_semantics` 必须与实际行为逐字一致（同规格「声明的并发原语与执行位置一致」的要求：声明与行为不得背离）。

## ⑥ 性能验收口径

拒绝"感觉更快"，四条可复现口径：

1. **循环创建次数（本 issue 的最小判据）**：修复前 = 每次派发 1 次 `asyncio.run`（即 1 次建 + 1 次关）；修复后 = 整段运行期内**恰好 1 次**创建。口径：对 `asyncio.new_event_loop` 注入计数器（或探针）后跑 N 次派发。**阈值：1（等于）**。
2. **工作线程占用不随并发增长**：N 个同时处于等待态的协程调用下，模型占用的工作线程数与 N 无关（thread 模型下为 N）。口径：N 取 8 / 32 两档，读进程内工作线程数增量。**阈值：N=32 时的线程数不高于 N=8 时**。
3. **并发推进能力**：同一 Worker 上 N 个各 sleep 0.2s 的等待型调用，总耗时落在"约 0.2s × ceil(N / max_concurrent)"量级，而非 N × 0.2s；这条同时证明 `asyncio.Semaphore(max_concurrent)` 真正生效（修复前它形同虚设）。**阈值：N ≤ max_concurrent 时总耗时 < 0.6s**。
4. **不退化既有边界**：沿用 `bench/` 已建立的方法学（测量 → 决策，见 `bench/DECISION.md`），对比"单次派出记账开销"与 thread 模型。**CPU 密集吞吐 MUST NOT 被列为验收指标**（本变更不解决计算）。倍率阈值**建议** ≤ 2×，最终数值待维护者确认。

口径纪律：固定机器与解释器版本、重复次数 ≥ 5、取中位数、剔除首次预热；读数与命令写入变更目录（沿用 `bench/` 的"可复核"惯例）。

## Risks / Trade-offs

- [两份结果契约漂移（P1）] → 这是本变更最需要裁决的点；P3 可消除，但要求动 `workers/base_worker.py`。
- [循环线程被同步阻塞饿死] → 准入拒绝（非协程 Worker 不进模型）+ Worker 级硬约束 + 必要时 `run_in_executor`；三者各配 Scenario 或硬约束条文。
- [停机顺序写错导致结果不投递] → 把"先等在飞结算、后停循环、再关循环"写成次序硬约束，并要求回归用例覆盖"停机后不再接收新任务"与"在飞结果仍被投递"。
- [新公开模式的配置面扩张] → 属公开契约变更，需在 `worker-scheduling` / `scheduler-model` 规格同步声明；本次已把模式登记面列为授权项。
- [常驻循环掩盖背压缺口（#233）] → 本变更不引入自己的背压档位；`describe()` 仍须给出 `backpressure_policy`，与 #233 对齐时再评估是否需要新档位（列为待观察项）。

## Migration Plan（裁决通过后）

1. 合入即生效但**需显式选择**：`worker:mode=event_loop`（缺省仍 thread / thread_pool）；
2. `AsyncWorker` 子类改配置即可切入；`async_execute` 内的阻塞段按 ④ 的硬约束自查；
3. 回滚 = 改回 `worker:mode`（或 revert 单个变更提交）。

## 裁决结果（维护者已拍板）

| 项 | 裁决 | 落点 |
|---|---|---|
| 4.1 结果契约缝合点 | **P3**——`base_worker.py` 抽"由已得值产出结果"共用缝；`run()` 行为**逐字节不变** | design D2 / ⑤ |
| 4.2 模式登记面授权 | **授权**改 `zoo_framework/constant/waiter_constant.py`（`WORKER_MODE_EVENT_LOOP` + 加入 `IMPLEMENTED_WORKER_MODES`） | design ③ |
| 4.3 停机是否取消"已开始"协程 | **不做**——`stop_semantics = STOP_CANCEL_QUEUED`（丢弃未开始，已开始不中断） | design ⑤ |
| 4.4 性能阈值 | 读数已按 ⑥ 采集写入变更目录；第 4 条倍率阈值仍**待维护者确认**（见下） | design ⑥ |
| 4.5 背压档位 | **不引入自有档位**；`describe()` 仍返回 `backpressure_policy`（`unbounded`）；与 #233 对齐列为**待观察项** | design Risks |

## Open Questions（剩余待维护者裁决）

1. **验收阈值确认（4.4）**：⑥ 第 4 条的倍率阈值仍建议 ≤ 2×，本次采集的读数已落盘待确认，**不按已确认事实对待**；基准机待定。
2. **背压档位（4.5）**：常驻循环模型对运行时注册是否需要新档位——与 #233 对齐时再评估（待观察，不在本变更范围）。
