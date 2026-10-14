# Proposal: fix-worker-reregistration

## Why

issue #227 实锤：`WorkerRegistry.register_class` 在同名再次注册一个**新类**时被实例缓存吞掉。
`get_worker` 的查找顺序是「实例 → 工厂 → 类」，而 `_worker_instances` 只按**名称**键控：一旦某
名称的实例被延迟实例化并写回缓存，后续以同名注册新类只更新 `_worker_classes`，缓存实例仍然
命中——注册表继续返回旧实例，新类**永不被实例化**，而且全程静默、无任何告警。以同名注册一个
新**工厂**时是同一缺陷（缓存同样只按名称键控）。调用方以为替换生效，实际旧实例在继续跑。

`WorkerDispatchCore.add_worker` 的注释「同名重注册（如 `Master.register_worker` 覆盖旧实例）
时旧解析作废」，已经按「同名重注册 = 覆盖」的语义书写——即仓库既有的预期语义是替换，而不是
保留旧实例。

## What Changes

- `WorkerRegistry` 区分「**延迟实例化缓存**」与「**显式登记实例**」：新增 `_lazy_instances` 记录
  由类 / 工厂实例化出来的缓存项。
- 同名重注册**不同**的类或工厂时，作废该名称的延迟实例化缓存，使新定义真正生效（「替换缓存
  实例」方案）。
- 同名重注册**同一个**定义是幂等的：保留已实例化的对象、只更新元数据——保证 `Master` 可重复
  构造（每次都会重新注册同一批默认 Worker 类）而不会凭空重建实例。
- `register_instance` 同名重注册以新实例替换旧实例，并把该名称移出延迟实例化缓存。
- 不改查找优先级（实例 → 工厂 → 类）；不销毁被替换的旧实例（不调用 `_destroy`）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-lifecycle`：新增「Worker 同名重注册 MUST NOT 被实例缓存吞掉」——同名重注册新类 / 新
  工厂后取用 MUST 返回新定义的实例；重注册同一个类 SHALL 幂等。

## Impact

- **代码**：`zoo_framework/core/worker_registry.py`（`_lazy_instances` + 三个注册入口 +
  `get_worker` + `unregister`）。
- **测试**：`tests/test_worker_registry.py` 新增 `TestSameNameReregistration`（4 例）：新类生效、
  新工厂生效、实例替换、同一类幂等。
- **规格**：`openspec/changes/fix-worker-reregistration/specs/worker-lifecycle/spec.md`。
- **无新增依赖**；不改变公有导入面。
- **相邻现象（不在本变更范围）**：`WorkerDispatchCore.add_worker` 只作废策略解析缓存、不把同名
  旧实例移出**调度列表**——在 `Master` 层重注册同名 Worker 仍会在调度列表留下旧条目。本变更只修
  注册表侧的「返回旧实例」，调度列表的替换语义另行评估。
