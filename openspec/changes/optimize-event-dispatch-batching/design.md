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

## Open Questions

- 直派形态（绕开 executor）是否立项二期——待本变更验收测量后裁决
- 批内事件数与 `wait(timeout)` 的关系（大批长跑触发超时上报的噪声）——验收观察
