## 1. 回归与实现

- [x] 1.1 在未修改的基线新增回归用例（`tests/test_persistence_scheduler.py::TestExplicitFailureNotification`）：
  父目录缺失时 `save` 抛 `PersistenceError`、`start` 启动即失败、目录存在时照常成功；确认前两例
  在修复前失败。
- [x] 1.2 新增 `PersistenceError`；`ensure_storage_ready()` 校验目标目录；`start()` 先行校验；
  `save()` 失败抛错并保留脏标记；导出 `PersistenceError`。

## 2. 规格

- [x] 2.1 编写 proposal、design、`state-machine` delta spec 与 tasks，记录 fail-fast + 落盘报错
  的双落点与"不自动建目录"的理由。

## 3. 验证

- [x] 3.1 聚焦用例与全量 `pytest` 通过。
- [x] 3.2 `ruff check zoo_framework`、`mypy zoo_framework` 干净。
- [x] 3.3 `openspec validate fix-persistence-failure-signal --strict` 通过。
