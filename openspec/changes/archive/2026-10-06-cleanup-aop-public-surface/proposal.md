## Why

AOP 层有三个**对外导出、但语义上不生效**的公共面（issue #49 逐项核实）：

- `@worker` / `worker_register`（`core/aop/worker.py`）：注册进 legacy `WorkerRegister`，而 `Master` 调度的是 `WorkerRegistry`——**注册了但从不被派发**；键仍是裸类名（#29 为 `@cage`/`@params` 修掉的反模式在此漏网）；导入期即 `cls()` 实例化，与 `WorkerRegistry` 的延迟实例化是两套时序。文件第一行的 `# TODO` 就是这件事的原始记录
- `register_worker` 装饰器（`core/worker_registry.py:254`）：`isinstance(registry, WorkerRegistry)` 恒为 False（`worker_register` 是 `WorkerRegister` 实例）→ **if 分支是死代码**；实际走"兼容旧版本"分支注册进 legacy 表，同样从不被派发。全仓库零使用（唯一命中是它自己 docstring 的示例）
- `@validation` / `validation_params`（`core/aop/validation.py`）：全仓库 **0 处使用、0 份规格**，却从 `core/aop/__init__.__all__` 公开导出；`params_validate_map` 还是一个无人读写的模块级可变全局（#50 载体清单成员）

后果：使用者照公共导出写 `@worker` 或 `@validation` → **静默不生效、不报错**；`__all__` 的语义被稀释成"导出了不等于能用"。

## What Changes

**逐项裁定（延续 issue #49 的二选一要求，全部选删除路径）**

- `@worker` / `worker_register`：从 `core.aop.__all__` 与 `core.__all__` 移除；`worker()` 调用时发 `DeprecationWarning`（两段式：本变更出导出面，下个 minor 删模块）。**不接回 `WorkerRegistry`**——导入期实例化与延迟实例化是两套设计，接回等于重写一个零真实使用的装饰器
- `register_worker` 装饰器：**整删**（死分支与宿主一起消失；`worker_registry.__all__` 随之移除该项）。注意与 `Master.register_worker` 方法是两个东西，后者不受影响
- `@validation` / `validation_params` / `params_validate_map`：**整模块删除**（零使用、零规格；#50 的载体清单随之缩短两项）

**示例如实修复**：`example/threads/demo_thread.py` 的 `@worker(count=20)` 改为 `Master.register_worker` 的真实可派发路径；`example/main.py` 的副作用导入注释同步。

**机制化拦截**：新增对 `core.__all__`、`core.aop.__all__`、`core.worker_registry.__all__` 的逐项可用性断言测试——把"导出了但不生效"变成**测试可拦截**的形态，防止同类欠账再长回来。

**BREAKING**：公共导出面收缩（`worker` / `worker_register` / `register_worker` / `validation` / `validation_params` 不再从包根与 aop 面导出）。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `worker-lifecycle`：新增「公共导出面 MUST 与实际注册/派发路径一致」——每项公开导出 MUST 可被有效使用；已判废的注册面 MUST NOT 出现在 `__all__`，遗留导入路径 MUST 发弃用警告而非静默生效

## Impact

- **代码**：`zoo_framework/core/aop/__init__.py`、`core/aop/worker.py`（弃用警告）、`core/aop/validation.py`（删除）、`core/__init__.py`、`core/worker_registry.py`
- **示例**：`example/threads/demo_thread.py`、`example/main.py`
- **测试**：新增 `tests/test_no_dead_public_surface.py`（`__all__` 逐项断言 + 弃用警告 + 移除项负断言）
- **文档**：`docs/structure.md`（两处装饰器清单）、`docs/DEBUGGING.md`（legacy `worker_register.get_all_worker()` 排错段）、`CHANGELOG.md`（BREAKING 记录）
- **issue**：关闭 #49；#50 的载体清单缩短两项（`worker_register`、`params_validate_map`）；#51 规格范围随之收窄（`@validation` 不再需要裁决去留）
