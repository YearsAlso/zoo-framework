# scheduler-model 规格变更（async-resident-event-loop delta）

## ADDED Requirements

### Requirement: event_loop 模型 MUST 只接纳协程 Worker 且 MUST NOT 声称终止仍在执行的协程

以常驻事件循环为并发原语的调度模型 SHALL 在契约中声明其并发原语、`stop_dispatch_cancel_queued` 停机语义与所支持的 Worker 类别；其支持的 Worker 类别 SHALL 只包含协程能力 Worker。对不具备协程能力的 Worker，该模型 MUST 明确拒绝并指明不兼容之处，MUST NOT 静默改用其它模型执行、MUST NOT 把同步阻塞执行体搬进循环线程、也 MUST NOT 自动改派到线程池。循环线程 MUST NOT 被同步阻塞执行体占用。超时判定 SHALL 沿用既有语义：只记录、标记不健康并停止派发；系统 MUST NOT 声称已终止或中断了仍在执行的协程——向协程投递取消请求不等价于它已经停止。

#### Scenario: 同步 Worker 被显式拒绝

- **WHEN** 向该模型提交一个不具备协程能力的 Worker
- **THEN** 该提交被拒绝并指明不兼容之处与可选模型，而非静默改用其它模型或线程池执行

#### Scenario: 契约六项可程序化查询

- **WHEN** 查询该模型的契约
- **THEN** 并发原语、支持的时间语义、背压策略、停机语义、支持的 Worker 类别与可观测指标六项均可获得且非空，其中并发原语为该模型实际使用的原语

#### Scenario: 超时不声称已终止

- **WHEN** 一个协程执行超过其期限
- **THEN** 该次超期被记录、该 Worker 被标记不健康且不再被派发，同时系统不产出任何"已终止/已中断该协程"的表述

#### Scenario: 停机丢弃未开始的协程而不中断已开始的

- **WHEN** 停机发生在一个协程已开始执行、另有已提交但尚未开始的协程时
- **THEN** 已开始的协程不被中断，尚未开始的协程不再执行，且两者都不留下未结算的在飞记录
