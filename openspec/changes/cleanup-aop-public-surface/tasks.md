## 1. 导出面收缩与判废

- [x] 1.1 `core/aop/__init__.py`：移除 `validation`、`worker`、`worker_register` 的导入与 `__all__` 项；`core/__init__.py` 同步移除 `worker` / `worker_register`。验证：三个 `__all__` 白名单断言（任务 3.1）通过
- [x] 1.2 `core/aop/worker.py`：`worker()` 内加 `DeprecationWarning`（stacklevel 对齐装饰器调用点），文案指明 legacy 表不接通派发、迁移到 `Master.register_worker`；`worker_register` 实例保留（模块路径导入仍可达，一个 minor 周期）。验证：`pytest.warns(DeprecationWarning)` 用例通过
- [x] 1.3 `core/aop/validation.py` 整文件删除（含 `params_validate_map`）。验证：全仓库 grep 无 `from .validation` / `aop.validation` / `validation_params` 残留；`openspec/changes/align-execution-primitives` 之外无文档引用（文档更新在任务 4）
- [x] 1.4 `core/worker_registry.py`：删除 `register_worker` 装饰器函数与 `__all__` 项（`Master.register_worker` 方法不动）。验证：worker_registry 既有测试全绿；负断言含 `register_worker`

## 2. 示例如实修复

- [x] 2.1 `example/threads/demo_thread.py`：去掉 `@worker(count=20)`，类保持可被 `Master.register_worker` 注册；`example/main.py` 显式导入 `DemoThread` 并注册（真实可派发路径），注释同步改写（删掉"实际不会被调度"的坦白注）。验证：按 `example/config.json` 运行 `python example/main.py` 能在限时内观察到 TestThread 被调度（或至少在 CI 冒烟中构造不抛）；`@logger` 用法保留（#51 处理其归属）

## 3. 机制化拦截

- [x] 3.1 新增 `tests/test_no_dead_public_surface.py`：(a) `core.__all__` / `core.aop.__all__` / `worker_registry.__all__` 的精确白名单快照断言；(b) 判废名（`worker` / `worker_register` / `validation` / `validation_params` / `register_worker`）不得出现在任一 `__all__` 的负断言；(c) `@worker` 触发 `DeprecationWarning` 的用例
- [x] 3.2 全量门禁：`pytest` 只增不减、mypy 0 error、ruff/bandit 绿（含 pre-commit 钩子）

## 4. 文档与账目同步

- [x] 4.1 `docs/structure.md` 中英文两处 `core/aop/` 装饰器清单去掉 `worker` / `validation`（注明已判废与弃用周期）；`docs/DEBUGGING.md` 的 `worker_register.get_all_worker()` 排错段改指向 `WorkerRegistry` / `Master` 真实路径
- [x] 4.2 `CHANGELOG.md` 记 BREAKING：公共导出面收缩五项 + 弃用时间表（下个 minor 删 `core/aop/worker.py` 与 `workers.WorkerRegister`）
- [ ] 4.3 issue 联动（待 PR 合并后关闭）：留言 #49（附验收逐条 + PR 链接，合并后关闭）；#50 评论载体清单 -2（`worker_register`、`params_validate_map`）；#51 评论范围收窄（`@validation` 不再需要裁决去留）；#32 在办表同步
