# scaffold-worker-naming 任务清单

## 1. 命名规则实现

- [x] 1.1 `_worker_names` 类名推导 `worker_name.title() + "Worker"` →
      snake_case 分段 PascalCase + `"Worker"`（规则见 design.md D-Rules 5 条）
      （验证：`order_sync`→OrderSyncWorker、`my_task`→MyTaskWorker、
      `x__y`→XYWorker、`_private`→PrivateWorker、`v2e`→V2eWorker、
      `sample`→SampleWorker 全部实测）
- [x] 1.2 验证三处一致：`zfc --worker my_task` 产出的文件名 / 类名 / 入口注册
      元组名逐字核对（验证：临时目录实测三处 grep）

## 2. 测试

- [x] 2.1 `test_scaffold_templates.py` 5 处 `My_TaskWorker` 断言翻转 +
      docstring 标注行为意图变更（#112）（验证：grep 旧名零命中）
- [x] 2.2 边界参数表补 `x__y` / `v2e`，断言升级为逐字 PascalCase 比对
      （验证：参数化用例通过）
- [x] 2.3 新增端到端：`order_sync` → 类名 `OrderSyncWorker` 且入口注册名一致；
      `sample_worker` 输入 → `SampleWorkerWorker`（后缀不剥离）
      （验证：两个端到端用例通过）
- [x] 2.4 拒绝行为零回归：ILLEGAL_NAMES 全量参数化用例仍通过
      （验证：`pytest tests/test_scaffold_cli_contract.py::TestWorkerNameValidation`
      全绿）
- [x] 2.5 全量 `pytest` 全绿（验证：>= 849 passed）

## 3. 回归与验证

- [x] 3.1 门禁：`ruff check` / `ruff format`（仅本变更文件）/ `mypy`
      （验证：全过）
- [x] 3.2 README 双语核对：Quick Start / CLI 节无 `My_TaskWorker` 字样则零改动，
      有则双语同步（验证：grep 旧名为 0）
- [x] 3.3 `openspec validate scaffold-worker-naming --strict` 通过
      （验证：退出码 0）
