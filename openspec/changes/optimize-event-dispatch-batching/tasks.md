# Tasks: optimize-event-dispatch-batching

## 1. 参数

- [ ] 1.1 `zoo_framework/params/event_params.py`：`DISPATCH_BATCHING_ENABLED`（`event:dispatchBatchingEnabled`，默认 False）与 `BATCH_MAX_SIZE`（`event:batchMaxSize`，默认 64），lazy import 纪律
- [ ] 1.2 测试：嵌套 config 解析与 falsy/缺省保守默认（复用 test_config_resolution 形态）

## 2. 批量聚合与提交

- [ ] 2.1 `zoo_framework/workers/event_worker.py`：排空循环按 `id(reactor)` 聚合 `(topic, content)` 列表；开关开且 Reactor 命中多条时以 `_run_batch` 单 callable 提交（一次簿记），批内逐事件 `execute(topic, content)`
- [ ] 2.2 批级 try/except：异常捕获时携带批内事件游标（处理到第几个），不吞批内剩余事件（按序继续或按 design 语义终止——实现以 design.md 为准并写测试）
- [ ] 2.3 本轮消费限量与批上限解耦：超上限事件留队不取（不裁批、不丢失、不死信）
- [ ] 2.4 测试：同 reactor 多事件一次提交（执行器 submit 调用次数 = 批数而非事件数）、批内逐事件执行、溢出留队下一轮消费、关闭时逐事件路径行为等价

## 3. 批级可观测

- [ ] 3.1 `_report_unfinished` 批级平移：未完成批上报（channel/ reactor/ 批内事件数）；已结束批的聚合异常上报附事件定位
- [ ] 3.2 测试：批内异常上报含定位信息、超时未完成批可观测、无静默丢弃

## 4. 验收与归档

- [ ] 4.1 吞吐验收：批均事件数对单事件摊簿记成本的测量（bench 同次运行内对照，记录进变更目录）
- [ ] 4.2 全量门禁：pytest / ruff / mypy / `openspec validate optimize-event-dispatch-batching --strict`
- [ ] 4.3 docs/ 更新事件一节；`/opsx:archive` 后 spec-syncer 核对；直派形态是否二期立项的裁决记录
