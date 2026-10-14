# Tasks: fix-reactor-timeout

## 1. 反应器侧声明语义

- [x] 1.1 `zoo_framework/reactor/event_reactor.py`：`event_timout` 默认值 `1` → `0`（0 = 未声明，跟随全局）；docstring 写明语义「join 等待豁免线，长等待 MUST NOT 放在反应器内」（#232 诉求 1 文档项）
- [x] 1.2 `zoo_framework/core/aop/event.py`：注释澄清 `timeout` 现为真正生效的声明入口；默认 `None` 语义不变
- [x] 1.3 测试：默认值 0、`@event(timeout=N)` 写入 `event_timout`、负值/None 亦视为未声明（tests/test_reactor_timeout.py）

## 2. 生效超时解析与等待

- [x] 2.1 `zoo_framework/workers/event_worker.py`：解析函数 `_effective_timeout(reactor)`（自报 > 0 取自报，否则全局 `EVENT_JOIN_TIMEOUT`）；逐事件与批量两路径共用
- [x] 2.2 dispatch 收集 `(future, reactor_name, topic, effective_timeout)` 定位条目（批量路径 topic 用批内 events 集合）；等待时长取本轮 `max(生效超时)`
- [x] 2.3 全部未声明时 wait 时长 = 全局默认，行为锚定测试（与合入前等价）

## 3. 带定位的未完成/异常上报

- [x] 3.1 `_report_unfinished` / `_report_unfinished_batched`：未完成告警带 reactor_name + topic（批量带主题集合）；异常上报带 reactor_name + topic
- [x] 3.2 批量路径：`BatchReactorError.failures` 定位信息并入上报（已有，补 reactor 名）
- [x] 3.3 测试：慢反应器超时告警含定位、声明大于耗时的生效超时不告警、异常上报含定位、`wait` 取 max 生效值（tests/test_reactor_timeout.py，side_effect 现场录制快照）

## 4. 文档与验收

- [x] 4.1 `docs/` 事件一节（advanced/reactor.md 中英）+ `CLAUDE.md`：硬约束「反应器 MUST 在生效超时内返回」、`@event(timeout=)` 为合法慢声明入口、长等待架构指引（引 zoo-code-agent#31）
- [x] 4.2 全量门禁：pytest（857 passed，test_doc_consistency 32 失败对照 stash 证实为 docs 站迁移遗留、与本变更无关）/ ruff / ruff format / mypy 零错误 / `openspec validate fix-reactor-timeout --strict` 通过
- [x] 4.3 GitHub issue #232 回调（评论修改落地情况）；`/opsx:archive` 后 spec-syncer 核对

> 实施补充（design 未预见）：`bind_topic_reactor` 与 `EventReactorManager.__init__` 原以
> 全局值对 `event_timout` **盖章**（absorb-debt-carriers 引入，当时该字段无读取方故无害）。
> 字段激活后盖章会抹掉「未声明」语义（所有反应器都变成"已声明=全局值"），已随本变更移除，
> 全局兜底移到 `EventWorker._effective_timeout` 读取现场。受影响的既有测试
> （test_worker_scheduling 两条）已按新规格更新断言并增加定位断言。
