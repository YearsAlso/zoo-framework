## Context

`StateNodeIndex` 是 `StateEffectScheduler` 持有的 effect 索引（经 `StateNodeIndexFactory` 创建）。
它初始化时同时建立 `state_effect_map`（状态 → effect 集合）与 `state_effect_set`（全部 effect
的合集），却从未实现任何写入 / 移除方法；而调度器一直调用 `add_state_effect` /
`remove_state_effect`。该路径全仓无构造点（属死代码上的潜伏缺陷），因此在 type-annotation-gate
补齐注解、逐行标注 `# type: ignore[attr-defined]` 时才被 mypy 显式指出。

## Decision

选择「**补齐接口**」而不是「改调用方」：

- 索引侧的 `state_effect_map` / `state_effect_set` 是既有设计意图的产物；只删调用会留下两个永远
  空的死容器。补齐方法是让既有结构真正生效的最小且语义正确的修法。
- 语义：`add_state_effect` 按 `state_effect.state` 分组写入 map 并并入 set；`remove_state_effect`
  从两处移除，且**幂等**（`discard`）——索引是调度器记账的**副本**，重复移除不应让调用方的簿记
  路径中断。
- 移除时清理空分组：某状态下的 effect 清空后删除该 key，避免索引里堆积空集合。
- 调度器自身的 `state_effect_map` 保持原样（不做去重复的重构），故 `get_state_effect` /
  `execute_state_effect` 语义不变。

## Non-goals

- 不合并调度器与索引两份记账结构（去重复属另行重构，不在本 issue 范围）。
- 不改变 `StateEffectScheduler.remove_state_effect` 自身的严格性：其内部 map 的 `set.remove`
  在目标缺失时仍抛 `KeyError`，与"索引侧幂等"分属两层不同契约，改动它超出本 issue。
- 不改变 effect 的并发执行与有界等待语义（`state-machine` 既有条款）。

## Language

中文注释 / 文档；docstring 保持 Google 风格（`Args:` / `Returns:` / `Raises:`）。
