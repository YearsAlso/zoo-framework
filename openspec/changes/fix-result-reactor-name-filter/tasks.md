# Tasks: fix-result-reactor-name-filter

## 1. 复现（先红后绿）

- [x] 1.1 新增 `tests/test_result_reactor_filter.py`：按注册名筛选命中带序号实例、仍拒绝
      其他 Worker、不是前缀匹配、`None` 全收、精确实例名仍接受、经结果主题端到端筛选
- [x] 1.2 修复前实测 3 条红（`worker_names=['ok']` 收不到 `ok_1`），修复后 8 条全绿

## 2. 规格（spec-first）

- [x] 2.1 `specs/worker-scheduling/spec.md` MODIFIED Requirement「Worker 结果 MUST 沿事件
      管道投递且可被按名过滤」：补入双身份、按注册名匹配、精确匹配（禁前缀）+ 2 条新 Scenario
- [x] 2.2 `openspec validate fix-result-reactor-name-filter --strict` 通过

## 3. 实现

- [x] 3.1 `zoo_framework/workers/worker_result.py`：新增 `registry_name` 字段（不带序号
      的身份）并在 docstring 写明"按 Worker 筛选 SHOULD 匹配 registry_name"
- [x] 3.2 `zoo_framework/workers/base_worker.py`：抽出 `registry_name` 属性，
      `name` 改为 `registry_name` + 序号（行为等价），成功与失败结果都带上它
- [x] 3.3 `zoo_framework/reactor/waiter_result_reactor.py`：`accepts` 改为身份候选集
      **精确**匹配；类说明与 docstring 写明筛选语义与"非前缀匹配"

## 4. 验收

- [x] 4.1 全量 `uv run pytest`（见最终汇报；唯一红项为本机既有的无 WSL/bash 环境缺陷）
- [x] 4.2 `uv run ruff check zoo_framework` / `uv run mypy zoo_framework` 零错误
