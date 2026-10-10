# Proposal: optimize-event-dispatch-batching

## Why

native 阶段 0 的链路剖析（tasks 1.2）证实：`EventWorker._execute` 排空循环的每事件 Python 成本被 `ThreadPoolExecutor.submit` 的记账主导——**31.9µs/事件 vs 裸 `queue.Queue` 1.86µs**（bench/DECISION.md 已实测 17 倍差距）。逐事件地优化出队/过期/查找（µs 级）或下沉 Rust 都淹没在这项开销里。真正的杠杆是**摊薄提交记账**：把同通道同 reactor 的待投递事件成组批量提交，或绕开 executor 的簿记直派（受控线程/裸队列直派形态）。预期单事件分摊成本从 31.9µs 降到接近裸队列量级，事件管道吞吐提升一个数量级形态（本变更测量为准）。

## What Changes

- `EventWorker._execute` 排空循环的投递段：同 (channel, reactor) 的事件**批量收集后一次提交**（一个 callable 处理一批，而非每事件一个 submit）
- 可选形态：批量 callable 内部仍逐事件调 `reactor.execute`（语义不变），但簿记只发生一次
- 保留 `wait(dispatched, timeout)` 有界等待与 `_report_unfinished` 超时/异常上报语义（键 shift 到批级：一批内任一事件失败需可观测）
- 新参数键：批大小上限（`event:*` 键族，默认保守值）；关闭降级 = 现行为（逐事件提交）零变化
- **不改变**：事件去向语义（投递/回队/死信恰好其一）、优先级计算（仍按通道内弹出顺序）、重试语义、响应器查找

## Capabilities

### New Capabilities

- `event-dispatch-batching`: 事件批量投递。SHALL 把同通道同 reactor 的事件成组提交（一次簿记投递一组），SHALL 保留有界等待与超时/异常可观测（键 shift 到批级），MUST NOT 改变事件去向语义与通道内处理顺序；关闭或批大小为 1 时保持既有逐事件行为。

### Modified Capabilities

无——`event-dispatch` 既有 REQUIREMENTS 不变（批量是投递执行层的形态优化，通道/优先级/重试语义原样）。

## Impact

- **代码**：`zoo_framework/workers/event_worker.py`（排空循环投递段重组）、`zoo_framework/params/event_params.py`
- **开放项**：「批量 submit」与「绕开 executor 直派」二选一在 design 阶段以测量裁决（批量 submit 改动小、语义安全；直派上限更高但自担簿记/超时语义）
- **测试**：`tests/test_event_dispatch_batching.py`（批量提交、批内失败可观测、超时上报、关闭零影响、顺序不变）
- **风险**：批内异常聚合后丢失逐事件定位 → 上报时带批内索引/事件标识；批间公平性（大批独占 reactor 线程）→ 批大小上限
- **与 native 线的关系**：替代「排空循环下沉 Rust」成为事件管道的真实优化路径；native 阶段 0 候选重估（1.1 已剖析，结论登记 DECISION.md）
