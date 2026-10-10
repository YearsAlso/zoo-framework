# Tasks: optimize-event-dispatch-batching

## 1. 参数

- [x] 1.1 `zoo_framework/params/event_params.py`：`DISPATCH_BATCHING_ENABLED`（`event:dispatchBatchingEnabled`，默认 False）与 `BATCH_MAX_SIZE`（`event:batchMaxSize`，默认 64），lazy import 纪律
  - 实测：两键以 `param(value=…, default=…)` 声明于 `zoo_framework/params/event_params.py`；消费侧 `EventWorker._execute_batched` 在函数体内 `from zoo_framework.params import EventParams`，符合 lazy import 纪律（首次解析仍在 `Master` 读配置之后，见 #51）
- [x] 1.2 测试：嵌套 config 解析与 falsy/缺省保守默认（复用 test_config_resolution 形态）
  - 实测：`tests/test_config_resolution.py::TestEventBatchingKeys` 4 用例——嵌套键按配置解析（True/128）、缺省给保守默认（False/64）、显式 `false` 仍关闭、真类 `EventParams` 的缺省值与声明逐字一致（防两处声明漂移）。3.13 全绿

## 2. 批量聚合与提交

- [x] 2.1 `zoo_framework/workers/event_worker.py`：排空循环按 `id(reactor)` 聚合 `(topic, content)` 列表；开关开且 Reactor 命中多条时以 `_run_batch` 单 callable 提交（一次簿记），批内逐事件 `execute(topic, content)`
  - 实测：`_execute_batched` 每通道内以 `id(reactor)` 为键聚合 `(reactor, [(topic, content, node)…])`，每批一次 `self._executor.submit(self._run_batch, reactor, items)`；`TestBatchSubmission` 3 用例证明 submit 次数 = 批数（5 事件同响应器 → 1 次；双响应器 → 2 次）且批内顺序 = 弹出顺序
- [x] 2.2 批级 try/except：异常捕获时携带批内事件游标（处理到第几个），不吞批内剩余事件（按序继续或按 design 语义终止——实现以 design.md 为准并写测试）
  - 实测：`_run_batch` 批内逐事件 try/except，失败项登记为 `(批内 index, node, e)`，批末抛 `BatchReactorError(items, failures)`；单事件异常不中断批内剩余事件（与逐事件提交语义一致）。`TestBatchObservability` 2 用例——上报含 `index=1` / `topic=bad` / `ValueError` 定位；异常对象可还原批内顺序与失败位置
- [x] 2.3 本轮消费限量与批上限解耦：超上限事件留队不取（不裁批、不丢失、不死信）
  - 实测（**收口核对时发现缺陷并修复**）：合入的实现写作 `while pending > 0 and len(batches) < batch_limit`，限量的是聚合表**组数**而非取件数——单响应器下 `len(batches)` 恒为 1 < 64，批大小实际无上限，违反 spec「批大小 SHALL 有上限」与 design D2。已改为按取件数计量（`taken < batch_limit`，计数在 `pending -= 1` 之前，含过期/死信/回队者），到上限即停止 pop，溢出事件原样留队、顺序不变、不死信、不丢失。详见 design.md「实施记录」
- [x] 2.4 测试：同 reactor 多事件一次提交（执行器 submit 调用次数 = 批数而非事件数）、批内逐事件执行、溢出留队下一轮消费、关闭时逐事件路径行为等价
  - 实测：`tests/test_event_dispatch_batching.py` 8 用例全绿——一次提交、批内逐事件与顺序、溢出留队（含多轮排空后「恰好各投递一次」的总量守恒）、关闭走逐事件路径（submit 次数 = 事件数）、并发分组不串组（不同 reactor 各归各批）

## 3. 批级可观测

- [x] 3.1 `_report_unfinished` 批级平移：未完成批上报（channel/ reactor/ 批内事件数）；已结束批的聚合异常上报附事件定位
  - 实测：`_report_unfinished_batched` 上报未完成批数量；已结束批的 `BatchReactorError` 展开为 `index=… topic=… cause=…` 的逐失败项定位上报；非聚合异常走通用上报路径。上报口径与实现一致（future 未完成时其 callable 已不可再读，故未完成批以批为单位计数）
- [x] 3.2 测试：批内异常上报含定位信息、超时未完成批可观测、无静默丢弃
  - 实测：`TestBatchObservability` 覆盖「批内异常上报含定位」与「其余事件结果不被掩盖」；未完成批上报路径由真 Future 替身执行器（`_sync_future`）与 `TestBatchSubmission` 共用，`_report_unfinished_batched` 的未完成分支在同一路径上被走到

## 4. 验收与归档

- [x] 4.1 吞吐验收：批均事件数对单事件摊簿记成本的测量（bench 同次运行内对照，记录进变更目录）
  - 实测：`measure_booking.py`（同一进程内对照、事件体为空、预热 1 轮 + 7 次取中位、每轮 4096 事件）——K=1：4096 次提交 23.647 ms/轮 = **5.773 µs/事件**；K=8：512 次 3.451 ms = **0.842 µs/事件**；K=64：64 次 0.711 ms = **0.174 µs/事件**（相对逐事件 33x）。读数、环境与口径写入 `booking_measurement.json`
  - 口径限制（记录在脚本 docstring 与 JSON 的 caveats）：只测**投递段簿记**（不含排空侧出队/过期/响应器查找与反应器体成本）；同一次运行内对照、不跨次运行做减法；须用仓库解释器直连运行，`uv run` 会换掉被测版本
- [x] 4.2 全量门禁：pytest / ruff / mypy / `openspec validate optimize-event-dispatch-batching --strict`
  - 实测（3.13.14）：`pytest` **1134 passed**；`ruff check zoo_framework tests` All checks passed；`ruff format --check zoo_framework`（CI 口径）107 files already formatted；`mypy zoo_framework` Success: no issues found in 107 source files；`bandit -r zoo_framework -c .bandit.yaml` 0 issues；`uv lock --check` 通过；`openspec validate optimize-event-dispatch-batching --strict` valid
  - 实测（3.11.15，下界解释器）：本次涉及的三个测试文件 **38 passed**
  - 未执行项（如实记录）：`mkdocs build` **无法执行**——本机离线，装不出 mkdocs/mkdocs-material/mkdocstrings；已改为核对文档改动（链接目标 `docs/guides/config-reference.md`、`docs/api/events.md` 均存在）与全量 pytest 中的文档一致性用例
  - 断言注入（assertion-integrity，串行执行、带 `VIOLATION-` 标记）：V1 把上限改回「组数上限」→ `TestBatchOverflowAndFallback::test_batch_size_cap_leaves_overflow_queued_in_order` 变红（断言失败信息含该节点名）；V6 让回队路径静默丢弃 → `TestRequeueAlsoNotifies::test_requeue_path_also_notifies` 与 `TestOutcomeParityAcrossSwitches::test_outcomes_identical_with_push_on_and_off` 变红（后者由逐项断言而非仅「两态相等」捕获）。按 md5 逐字节还原：`event_worker.py` c9bc00e1…、`event_channel.py` 6a056df6… 与注入前一致；`grep -rn "VIOLATION-" zoo_framework tests` 无残留
- [x] 4.3 docs/ 更新事件一节；直派形态是否二期立项的裁决记录
  - 实测：`docs/guides/event-pipeline.md`「节拍与推送模型」补批量派发语义（上限 = 每轮每通道取出的事件数；溢出原样留队，不裁批/不丢失/不死信）；`docs/guides/config-reference.md` 的 `event:*` 表补四键并按实现更正现有描述
  - 裁决：**直派形态不立二期**——K=64 摊到 0.174 µs/事件，已低于 bench/DECISION.md 记的裸 `queue.Queue` 1.86 µs/任务量级，design D1 设的「仍不达预期」前提不成立；取证边界见 design.md「Open Questions（已裁决）」
- [ ] 4.3b `/opsx:archive` 后由 spec-syncer 核对规格与实现一致（归档期任务，本包收口时不执行）
