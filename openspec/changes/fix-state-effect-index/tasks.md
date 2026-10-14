## 1. 回归与实现

- [x] 1.1 在未修改的基线新增回归用例（`tests/test_statemachine.py::TestStateEffectIndex`）：经
  调度器登记 / 移除 effect 后索引按状态与全集可查，且查询 / 执行语义不变；确认三例在修复前因
  `AttributeError` 失败。
- [x] 1.2 `StateNodeIndex` 补齐 `add_state_effect` / `remove_state_effect`（分组 + 全集，移除
  幂等并清理空分组）；删除 `state_effect_scheduler.py` 中两处 `# type: ignore[attr-defined]`
  与遗留说明注释。

## 2. 规格

- [x] 2.1 编写 proposal、design、`state-machine` delta spec 与 tasks，记录选择「补齐接口」而非
  「改调用方」的理由。

## 3. 验证

- [x] 3.1 聚焦用例与全量 `pytest` 通过。
- [x] 3.2 `ruff check zoo_framework`、`mypy zoo_framework` 干净。
- [x] 3.3 `openspec validate fix-state-effect-index --strict` 通过。
