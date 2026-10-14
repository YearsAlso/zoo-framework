# Design: fix-reactor-timeout

## Context

见 proposal.md。现状：`EventWorker` 的等待与未完成判定线是一把全局的 `event:timeout`（`EVENT_JOIN_TIMEOUT`，默认 5s）；`_report_unfinished` / `_report_unfinished_batched` 只报数量；dispatch 循环现场持有 reactor 但 future→(reactor, topic) 关系不留存。`EventReactor.event_timout` 字段（`@event(timeout=...)` / `bind_topic_reactor` 写入）无读取方（实例默认值 1，写入方都会覆盖它）。

## Goals / Non-Goals

**Goals**
- 告警可定位：未完成与异常上报携带 reactor / topic
- 按反应器生效超时：声明慢的反应器豁免于告警，全局超时对其它反应器的卡死发现不被削弱
- 两条消费路径（逐事件 / 批量）行为等价地获得同样语义
- 未声明时行为与合入前一致

**Non-Goals**
- 不做 per-name / per-topic 配置侧覆盖（`event:timeoutOverrides` 之类）——按反应器声明已有 `@event(timeout=...)` 入口，不引入第二入口
- 不做运行期取消（反应器照常跑完；超时只是不再"守株收取结果"）
- 不动执行器生命周期、事件去向/优先级/重试语义

## Decisions

### D1: 生效超时两级解析，不做三级

`effective = reactor.event_timout if reactor.event_timout > 0 else EventParams.EVENT_JOIN_TIMEOUT`。`0`/`None`/负值统一视为未声明（跟随全局）——与 worker 侧 `resolve_run_timeout` 的「自报 → 覆盖 → 全局默认」同型，但**去掉配置覆盖中间层**：声明入口已在 `@event(timeout=...)`，第二入口只会制造同一语义两个真相源的漂移（`event_timout` 死字段的教训）。
**代价**：`EventReactor.__init__` 的 `self.event_timout = 1` 语义修正为 `0`（现行值 1 意为"未声明时只等 1s"，但该值从未被读取、无行为影响，修正无兼容风险；写入方 `aop/event.py` 默认 None、`bind_topic_reactor` 恒写全局值，都不落 1）。

### D2: 等待时长 = max(生效超时的最大值, 0) 兜底全局

本轮 `wait(dispatched, timeout=T)` 的 T 取本轮派发集中各 reactor 生效超时的最大值；全为未声明时 T = 全局 `EVENT_JOIN_TIMEOUT`，行为与合入前一致。理由：等待短于某 reactor 的生效超时会让豁免失效（_DEFINED-自报值小于轮询节拍时每拍必超时），取 max 是唯一保证「自报值 = 承诺等待时限」的聚合。

### D3: 未完成判定按 future 自身生效超时

`wait` 超时后，逐 future 检查：`f.done()` → 正常处理（异常上报带定位）；未 done 且 `该轮实际等待时长 >= 其生效超时` → 保留上报告警；未 done 但实际等待 < 生效超时（不可能发生，因 T >= 全部生效值）→ 仍上报（防御分支，按超时处理）。批量路径以批首事件的生效值为批生效值（同 reactor 必同生效值，因 key 为 id(reactor)）。

### D4: 映射表 = 局部 list of (future, reactor_name, topic)，不用 dict

逐事件路径天然逐条 append；批量路径 append `(f, reactor.reactor_name, None)` + 批内 events 由 `BatchReactorError.items` 承载 topic。每轮新建局部结构，无共享状态（同 design 既有惯例）。

### D5: 文档定位与措辞

- `EventReactor` docstring / `docs/` 事件一节写明：反应器 MUST 在自身生效超时内返回；`@event(timeout=...)` 是声明合法慢的入口；长等待工作（交互式审批）MUST NOT 放在反应器内。
- 告警文案改为携带 reactor 名称与 topic，措辞从「results were not collected」保留（语义仍是"结果没人收"）但后续紧跟定位。

## Risks / Trade-offs

- [自报超大超时者被豁免于卡死发现] → 文档明说打守则；该豁免是使用者显式声明，与 worker 侧自报 run_timeout 同责
- [T 取 max 使本轮等待变长] → 仅在显式声明慢时发生，且 `_run_batch`/reactor 线程照常执行；EventWorker 主节拍（waiter 调度间隔）不变
- [`event_timout` 改默认值] → 已核实全仓库无读取方，现行 1 无行为意义；兼容风险为零
- [批量路径批生效值取首事件] → 同 reactor 同生效值恒成立（key=id(reactor)），非近似

## Migration Plan

1. 合入即生效（无需开关）：默认路径全未声明 → T=全局、告警语义不变，等价性有测试锚定
2. 消费方按需 `@event(timeout=N)` 声明合法慢
3. 回滚 = revert 单个变更提交串

## Open Questions

无——issue 评论中提到的配置侧 per-name override 已裁定不做（D1）；zoo-code-agent 侧的架构迁移不在本变更范围。
