# Tasks: fix-worker-failure-result

## 1. 复现（先红后绿）

- [x] 1.1 新增 `tests/test_worker_error_result.py`：失败 `run()` 返回带 `error` 的结果、
      成功结果无 `error`、失败不是成功空结果、钩子语义不变、经结算收口投递恰好一条
- [x] 1.2 修复前实测该文件失败（`RuntimeError: boom` 直接冒出，8 条中 5 条红：
      `test_failed_run_returns_a_result_marked_as_failure` 等）；修复后 8 条全绿

## 2. 规格（spec-first）

- [x] 2.1 `specs/worker-scheduling/spec.md` 写入 ADDED Requirement「Worker 执行失败 MUST
      产生可区分的结果事件」+ 4 条 Scenario
- [x] 2.2 `openspec validate fix-worker-failure-result --strict` 通过

## 3. 实现

- [x] 3.1 `zoo_framework/workers/worker_result.py`：新增 `error` / `registry_name` 字段与
      `success` 只读属性；docstring 写明"失败 MUST NOT 以成功空结果形态投递"
- [x] 3.2 `zoo_framework/workers/base_worker.py`：`run()` 失败分支返回失败结果
      （`content=None`、`error=类型名: 消息`、`worker_name`、`registry_name`）；
      抽出 `registry_name` 属性并让 `name` = `registry_name` + 序号（行为等价）
- [x] 3.3 失败路径不调用 `_destroy_result`、跳过 `delay_time` 等待；`_on_error` /
      `_on_done` / 错误日志保持触发

## 4. 既有用例改判（旧行为被写死为断言的两处）

- [x] 4.1 `tests/test_worker_scheduling.py::TestResultReporting`：原
      `test_failed_worker_does_not_report_a_result`（断言 `collector == []`）改判为
      `test_failed_worker_reports_a_distinguishable_result`（恰好一条、带 error、非成功）
- [x] 4.2 `tests/test_native_task_execution.py::TestNativeTaskWorker`：原
      `assert not delivered` 改判为"恰好一条失败结果、error 非空、success 为假"

## 5. 验收

- [x] 5.1 全量 `uv run pytest`：见最终汇报（唯一红项
      `test_doc_consistency::test_release_notes_...` 经 stash 对照证实为**修复前既有**的
      本机环境缺陷——无可用 WSL/bash，与本变更无关）
- [x] 5.2 `uv run ruff check zoo_framework` / `uv run mypy zoo_framework` 零错误
