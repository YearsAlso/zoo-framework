# Tasks: add-adaptive-scheduling

> **状态：已重开——bandit 方案。** 上一版 ML 任务清单（24 项：特征 schema/权重档案/导出机制）
> 已废弃，见 git 历史；本清单不包含任何训练/导出/权重任务。

## 1. 参数层与统计核心

- [x] 1.1 新建 `zoo_framework/params/adaptive_params.py`：`AdaptiveParams`（`ADAPTIVE_ENABLED("adaptive:enabled", False)` / `EXPLORATION("adaptive:exploration", 0.05)` / `STATS_PATH("adaptive:statsPath", "")`，lazy import 纪律），`params/__init__.py` 导出；验证：`test_config_resolution` 形态用例（嵌套解析、falsy 尊重、缺省保守）
- [x] 1.2 新建 `zoo_framework/core/adaptive/bandit.py`：`EpsilonGreedy`（两臂 `(n, mean)` 增量统计，`decide(ε)` O(1)、`record(arm, duration)` O(1)，单 `threading.Lock`）；验证：均值更新数学正确性（增量式与全量均值等价）、ε=0 稳定选优臂、明确的臂名族
- [x] 1.3 新建 `zoo_framework/core/adaptive/policy.py`：`BanditPolicy`（逐 worker 类名持有 `EpsilonGreedy`，模块级单例 `get_bandit_policy()`/`reset_bandit_policy()`）；验证：同名多实例共享统计（key=类名）、reset 后统计清零
- [x] 1.4 登记 `BanditPolicy` 进 `zoo_framework/core/process_state.py` CARRIERS；验证：`test_process_state_registry` 通过

## 2. DualArmWorker 基类

- [x] 2.1 新建 `zoo_framework/workers/dual_arm_worker.py`：`DualArmWorker(BaseWorker)`——props 声明 `native_task_name`（可选；无则纯 python 臂恒定），子类实现 `_execute_python()`；`_execute()` 内闭环「决策 → 原生臂可用性检查（`native:enabled` + 适配器 `ensure_ready`）→ 计时执行对应臂 → `policy.record`」；验证：构造期 props 校验（无 python 臂实现即报错）
- [x] 2.2 native 臂执行体复用 `NativeTaskWorker` 的委托形状：`NativeAdapter().execute(native_task_name, payload)`（payload 由子类钩子提供，默认 `_props.get("input")`）；验证：原生臂调用契约与 NativeTaskWorker 一致（mock 侧调用时快照）
- [x] 2.3 显式拒绝语义：声明了 `native_task_name` 但 `native:enabled=false` 或扩展缺失 → 显式报错（复用 adapter `NativeInvalidInput`），无任何一次静默 python 臂执行；验证：两 Scenario 红转绿
- [x] 2.4 fail-open：决策层异常 → 按 python 臂执行不传导；双臂执行体异常 → 照 BaseWorker 契约 `_on_error` 传播；验证：注入异常两 Scenario
- [x] 2.5 生命周期 hooks：`_on_create`/`_on_error`/`_on_done`/`_destroy_result` 照 `BaseWorker` 契约走到；验证：`test_native_task_execution.py` HookedWorker 形态复用

## 3. 接线与开关

- [x] 3.1 `adaptive:enabled=false`（默认）时 `DualArmWorker` 纯 python 臂执行、零 bandit 分支、零锁；验证：关闭开关下派发/结算与合入前等价
- [x] 3.2 `adaptive:enabled=true` 时决策生效；`native:enabled` 与 `adaptive:enabled` 独立判定（各自显式拒绝，无级联假设）；验证：四态组合矩阵用例
- [x] 3.3 统计持久化：`adaptive:statsPath` 配置时 JSONL 快照（PersistenceScheduler 原子写 + 校验和先例，~40 行）；验证：落盘/重启加载为先验、写失败 fail-open
- [x] 3.4 全量门禁：pytest 全绿（834）、ruff/mypy 零错、bandit（安全扫描）零高危（B311 ε-greedy 探索 nosec 豁免——非加密用途）、`openspec validate add-adaptive-scheduling --strict` 通过

## 4. 端到端验收

- [x] 4.1 集成场景（有真扩展的本机）：声明双臂的 worker 混合执行 → 统计收敛（大帧原生臂均值更快并稳定被选）；验证：可复现统计断言（固定种子）
- [x] 4.2 决策 μs 级验收：decide+record 单次 < 1µs（本机参考形态，bench 同次运行内对照）；验证：测量数据落档（`bench/demo_bandit_gain.py` 表3：decide 0.35µs + record 0.29µs ≈ 0.64µs/帧，收敛验证表2 双类目与包络规则同侧）
- [x] 4.3 docs/ 更新：adaptive 一节——`DualArmWorker` 使用方式、`adaptive:*` 键族、与 `native:*` 的独立关系
- [x] 4.4 `/opsx:archive` + spec-syncer 核对 `openspec/specs/adaptive-scheduling/spec.md` 与实现一致；结果回调 issue（adaptive 线归属 issue 确认后追加）
