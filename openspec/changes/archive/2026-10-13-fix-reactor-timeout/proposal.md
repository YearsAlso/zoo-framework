# Proposal: fix-reactor-timeout

## Why

#232 实锤：合法地慢的反应器每拍触发「N reactors were still running after the join timeout; their results were not collected」告警，与真卡死无法区分，且告警无定位信息（只有数量），使用者被迫调大全局 `event:timeout` 而削弱框架对真卡死的发现能力。另有加重发现：`EventReactor.event_timout`（由 `@event(timeout=...)` 与 `bind_topic_reactor` 写入）**全仓库无读取方**——按反应器声明超时的入口今天已存在但静默无操作，`@event(timeout=8)` 看似生效实为 no-op。两个问题同源：全局唯一超时同时承担「有界等待」与「未完成判定线」，慢没有合法出口。

## What Changes

- **A（可观测前置）**：`EventWorker` dispatch 时记录 future → (reactor_name, topic) 映射；逐事件与批量两条路径的未完成/异常上报均携带 reactor 与 topic 定位信息。
- **B（按反应器超时生效）**：生效超时按「反应器自报 `event_timout` → 全局 `event:timeout`」两级解析（与 worker 侧 `resolve_run_timeout` 同型）；等待时长取本轮派发集中生效超时的最大值；未完成上报只对「实际耗时超过自身生效超时」的 future 发出——声明了合法慢的反应器不再触发告警。
- `@event(timeout=...)` 从静默无操作变为真正生效；默认 `None`（`EventReactor.__init__` 现值 1 的语义修正为 0=未声明），未声明 = 跟随全局，向后兼容。
- 文档写明硬约束：反应器 MUST 在自身生效超时内返回；长等待（如交互式审批）不要放在反应器里（引 zoo-code-agent#31 方向）。
- **不改变**：事件去向语义（投递/回队/死信恰好其一）、优先级、重试、响应器查找、执行器生命周期。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `event-dispatch`：修改「事件投递的并发原语 MUST 独立于 greenlet 且超时与异常可观测」——等待时长与未完成判定从单一全局值变为按反应器生效值；新增定位 SHALL（超时/异常上报携带 reactor 与 topic）与按反应器超时声明的 SHALL（未声明跟随全局）。「循环 Worker 的运行节拍 MUST 可配置」中「死键 MUST NOT 保留」由本变更顺带成立（`event_timout` 从死字段变为有消费点）。

## Impact

- **代码**：`zoo_framework/workers/event_worker.py`（映射表 + 两级超时解析 + 上报定位）、`zoo_framework/reactor/event_reactor.py`（`event_timout` 默认语义修正、暴露读取口）、`zoo_framework/core/aop/event.py`（注释澄清 timeout 语义为 join 等待豁免线）
- **文档**：`docs/` 事件一节、`CLAUDE.md` 架构注释、`EventReactor` docstring
- **测试**：`tests/test_reactor_timeout.py`（自报超时生效、全局回退、告警定位、批量路径、向后兼容）
- **风险**：自报超大超时者被豁免于卡死发现（文档明说）；等待时长取最大值使本轮等待变长——仅发生在显式声明慢的场景，属使用者明示选择。
