# Proposal: fix-state-effect-index

## Why

issue #208：`StateEffectScheduler.add_state_effect` / `remove_state_effect` 调用
`StateNodeIndex.add_state_effect` / `remove_state_effect`，而 `StateNodeIndex` 上并无这两个
方法——该路径一旦被构造即运行期 `AttributeError`。该缺陷在变更 `type-annotation-gate` 中被
发现，以逐行 `# type: ignore[attr-defined]` 如实标注并另立 issue 跟踪（其 tasks 3.1），本变更
把它修掉。

根因是**接口没补齐**：`StateNodeIndex` 自建立起就带有 `state_effect_map`（状态 → effect 集合）
与 `state_effect_set`（全集）两个容器，却没有任何写入 / 移除方法——两个容器此前都是死状态，
调度器却一直按"它们有对应方法"来调用。

## What Changes

- `StateNodeIndex` 补齐 `add_state_effect` / `remove_state_effect`：按 `state_effect.state` 分组
  登记进 `state_effect_map`，同时并入全集 `state_effect_set`；移除为**幂等**（`discard`）。
- 移除 `state_effect_scheduler.py` 中两处 `# type: ignore[attr-defined]` 及其说明注释——它们所
  标注的前提（方法不存在）已不成立。
- MUST NOT 改变 `StateEffectScheduler` 既有的查询（`get_state_effect`）与执行
  （`execute_state_effect`）语义。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `state-machine`：新增「状态 effect 调度器 MUST 能把 effect 登记到索引且二者一致」——被调用的
  索引方法 MUST 真实存在；登记 / 移除后索引 MUST 与调度器记账一致。

## Impact

- **代码**：`zoo_framework/statemachine/state_node_index.py`（补齐方法）、
  `zoo_framework/statemachine/state_effect_scheduler.py`（去掉 ignore 与遗留注释）。
- **测试**：`tests/test_statemachine.py` 新增 `TestStateEffectIndex`（3 例）。
- **规格**：`openspec/changes/fix-state-effect-index/specs/state-machine/spec.md`。
- **无新增依赖**；不改变公有导入面。
