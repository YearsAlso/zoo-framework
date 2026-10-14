# Tasks: document-event-ordering

## 1. 判定与复现

- [x] 1.1 判定 FIFO 完成顺序**不是**框架承诺（依据：共享线程池并发提交、既有规格用词含糊、
      优先级计算本就会改写相互顺序）；结论：文档缺陷，不改行为
- [x] 1.2 新增 `tests/test_event_ordering.py`：出队顺序 = 入队顺序、缺省路径完成顺序由
      完成时刻决定（入队 A 慢 / B 快 → 完成 B、A）、批量路径串行（完成 A、B）、
      类说明写明顺序语义
- [x] 1.3 实测：3 条行为断点在修复前即绿（现状行为，非缺陷）；文档断点在修复前为红
      （"未文档化的惊喜"本尊），补文档后转绿

## 2. 规格（spec-first）

- [x] 2.1 `specs/event-dispatch/spec.md` MODIFIED「事件通道的消费路径 MUST 真正投递到
      响应器」：补入顺序语义 SHALL（只承诺投递顺序 / 不承诺完成顺序 / 须写明）+ 3 条 Scenario
- [x] 2.2 `specs/event-dispatch-batching/spec.md` MODIFIED「语义与顺序不变」：澄清批内
      串行完成语义、进程级开关属性、关闭时不承诺完成顺序 + 2 条 Scenario
- [x] 2.3 `openspec validate document-event-ordering --strict` 通过

## 3. 实现（仅说明性注释与 docstring）

- [x] 3.1 `zoo_framework/workers/event_worker.py`：类说明新增 Ordering 段（delivery 保证
      ≠ execution-order 保证；需要顺序者自行串行化或启用批量投递，后者为进程级开关）
- [x] 3.2 同文件提交现场的并发语义行注释（中文）
- [x] 3.3 确认零运行时行为变化（用例与既有事件管道用例全绿）

## 4. 验收

- [x] 4.1 全量 `uv run pytest`（见最终汇报；唯一红项为本机既有的无 WSL/bash 环境缺陷）
- [x] 4.2 `uv run ruff check zoo_framework` / `uv run mypy zoo_framework` 零错误
- [x] 4.3 待确认项写入 design.md 的 Open Questions（不做自行拍板）：按响应器声明串行的
      配置入口是否需要
