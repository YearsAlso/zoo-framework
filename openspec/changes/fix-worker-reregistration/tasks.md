## 1. 回归与实现

- [x] 1.1 在未修改的基线新增同名重注册回归用例（新类 / 新工厂 / 实例替换 / 同一类幂等），确认
  「新类」与「新工厂」两例在修复前失败。
- [x] 1.2 `WorkerRegistry` 新增 `_lazy_instances`；`register_class` / `register_factory` 在定义
  变化时作废延迟实例化缓存；`get_worker` 标记缓存来源；`register_instance` / `unregister` 维护
  该标记。

## 2. 规格

- [x] 2.1 编写 proposal、design、`worker-lifecycle` delta spec 与 tasks，记录选择「替换缓存实例」
  而非「显式报错」的理由。

## 3. 验证

- [x] 3.1 聚焦用例与全量 `pytest` 通过。
- [x] 3.2 `ruff check zoo_framework`、`mypy zoo_framework` 干净。
- [x] 3.3 `openspec validate fix-worker-reregistration --strict` 通过。
