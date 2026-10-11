# Design: optimize-event-dispatch-batching

## Context

见 proposal.md。`EventWorker._execute` 的每事件成本被 `ThreadPoolExecutor.submit` 簿记主导（31.9µs vs 裸 queue.Queue 1.86µs，bench/DECISION.md 实测）。排空循环其余环节（出队/过期/查找）µs 级，native 下沉与单点优化都被此项淹没。

## Goals / Non-Goals

**Goals**
- 同 (channel, reactor) 的事件成批一次提交，摊薄簿记
- 批级可观测（超时/异常上报带定位信息）
- 关闭（或批大小=1）时行为与合入前一致

**Non-Goals**
- 不改响应器执行语义（批内仍逐个 `execute(topic, content)`）
- 不改事件去向/优先级/重试语义
- 不动 executor 实例级生命周期（align-execution-primitives 决策）

## Decisions

### D1: 首选「批量收集 + 单 callable 提交」，直派形态留作测 afterthought

**选择**：排空循环按 `(channel_name, reactor_name)` 聚合 `(topic, content)` 列表，提交 `partial(_run_batch, reactor, items)` 一次；`_run_batch` 内逐事件调用 `reactor.execute`。
**理由**：一次簿记 amortize 到整批；`_run_batch` 内逐事件 try/except 可在批级上报时保留事件定位（闭包记住 items 顺序）；对 executor 的超时/上游 `_report_unfinished` 语义最小迁移（future 语义不变，只是粒度变批）。
**备选**：绕开 executor 直派（裸 queue + 自管线程）——上限更高（1.86µs vs 批量后约 31.9µs/批），但自担簿记、超时语义、销毁路径，alignment 风险大。**裁决方式**：先实施批量形态并测量；若批级摊簿记后仍不达预期（批均事件数小时退化），直派作为二期候选立项。

### D2: 批聚合键 = (channel, reactor)，上限 = `event:batchMaxSize`

**选择**：聚合 dict 按 `id(reactor)` 分组（同通道同 reactor 即同执行体）；批上限新参数默认保守值（如 64），溢出事件**留在队列**（`pending -= 1` 前的限量扫描天然支持：本轮少收不裁批）。
**理由**：裁批丢失或死信都违反语义；限量扫描溢出留队是零成本零风险形态。
注意本轮消费量的计数（`pending = channel.size()` 快照）与聚合上限须解耦——超出上限的事件本轮不取。

### D3: 批级可观测

`_report_unfinished` 平移：一批未完成 → 上报批（含 channel/ reactor 与批内事件数）；批已结束 → executor future 的 exception() 是 `_run_batch` 抛出的聚合异常时，上报附批内事件标识列表（`_run_batch` 在 finally 里登记已处理游标，异常携带「处理到第 i 个事件」信息）。
**理由**：spec 要求定位信息；游标登记是低成本高定位价值的形态。

### D4: 参数与门控

`event:dispatchBatchingEnabled`（默认 false）与 `event:batchMaxSize`（默认 64）。关闭时排空循环走既有逐事件路径（分支一个 bool 检查）。

## Risks / Trade-offs

- [批内单事件异常延迟其他事件的结果] → `execute` 异常被 per-event 捕获上报，批内继续（语义与既有逐事件提交一致——executor future 里 reactor 异常本来就静默到 exception()）
- [大批独占 reactor 线程] → 批上限兜底
- [聚合 dict 在通道多时开销] → 每轮新建局部 dict，无共享状态

## Migration Plan

1. 默认关闭合入
2. 开启验证批级摊簿记吞吐提升（验收测量批均事件数对单事件成本曲线）
3. 回滚 = 关开关

## Open Questions（已裁决，2026-10-10）

- **直派形态（绕开 executor）是否立项二期** → **不立项**。任务 4.1 实测（同一进程内对照、事件体为空、K=1 与批量在同一次运行中测得、取 7 次中位）：K=1 逐事件提交 **5.773 µs/事件**；K=8 **0.842 µs/事件**；K=64 **0.174 µs/事件**（33x）。批级摊簿记后单事件成本已低于 bench/DECISION.md 所记裸 `queue.Queue` 1.86 µs/任务量级，D1 设的「批级摊簿记后仍不达预期（批均事件数小时退化）」前提不成立。取证边界：该读数只覆盖**投递段簿记**（不含排空侧出队/响应器查找与反应器体），若日后出现事件体极短且批均大小长期为 1 的负载，应重新取证。
- **批内事件数与 `wait(timeout)` 的关系（大批长跑触发超时上报的噪声）** → 由批上限兜住：单批事件数 ≤ `event:batchMaxSize`（默认 64）；超时上报粒度由「每事件一个 future」变为「每批一个 future」，噪声下降，事件级定位改由 `BatchReactorError` 的批内索引承担。

## 实施记录（收口核对，2026-10-10）

- **批上限语义修正（收口核对时发现并修复）**：合入的实现写作 `while pending > 0 and len(batches) < batch_limit`——限量的是**聚合表的组数**（去重后的响应器个数），而非本轮取出的事件数。单响应器场景下 `len(batches)` 恒为 1 < 64，批大小实际**无上限**，与 spec「批大小 SHALL 有上限（可配置，保守默认）」及本设计 D2「本轮消费量的计数与聚合上限须解耦——超出上限的事件本轮不取」不符。已改为按**取件数**计量（`taken < batch_limit`，计数在 `pending -= 1` 之前，含过期/死信/回队者），到上限即停止 pop，溢出事件**原样留在队列**（不裁批、不丢失、不死信、不改顺序）。测量脚本 `measure_booking.py` 的批量段同样按取件数切块，与此语义一致。
- **既有测试为何没发现**：修正前的溢出用例在「10 个事件 / 默认上限 64」下断言，上限远大于事件数，用「组数上限」的错误实现同样全绿。修正后该用例改为「显式把上限调到 3、断言第一轮恰好投递 3 个且队列剩 7 个」，并逐字节注入旧写法验证其变红（见 tasks 4.2）。
- **批级超时上报粒度**：`_execute_batched` 仍以 `EVENT_JOIN_TIMEOUT` 等待本轮的批 future；超时上报以**批**为单位（比逐事件粗）。
- **与本变更引用的 bench 读数之差（口径说明）**：proposal 引 bench/DECISION.md 的「31.9 µs/事件 vs 裸 `queue.Queue` 1.86 µs/任务」，那是**含逐任务 `result()` 取回**的提交-回收对成本；本变更 4.1 的逐事件读数 5.773 µs/事件对应「提交 + 本轮统一 `wait`」形态（不含逐任务回收）。两者同为本机实测、形态不同，不互相证伪。按 proposal 的约定（「本变更测量为准」），4.1 的读数为本变更的验收口径；无论取哪个口径，K=64 的摊薄结论与「直派不立项」的裁决方向不变。

## 开放项（不擅自改行为，留待决策）

- **`event:batchMaxSize: 0` 会让批量路径停摆**：`ParamsPath` 对**已配置的假值**按值尊重（0 不会被默认值 64 兜住），而 `taken < 0` 恒假 ⇒ 每轮一件都不取，事件只积压、不消费、无死信、无日志。`docs/guides/config-reference.md` 已注明「必须 ≥ 1」；是否加显式守卫（解析期 `max(1, v)` 或启动告警）属行为决策，本变更未实施。
