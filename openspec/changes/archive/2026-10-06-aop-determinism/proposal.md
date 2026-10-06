## Why

AOP 层此前**没有能力规格**：`@configure` / `@logger` / `@stopwatch` 的语义无权威定义（`@params` / `@event` 已由 config-resolution / event-dispatch 覆盖），而两条导入顺序约束是**静默**的（issue #51）：

- `@params` 解析发生在首次导入；配置未就位时**静默冻结成默认值**——使用者拿到一份"看起来正常、实际全默认"的配置，无任何信号
- `@configure` 注册发生在导入时、`Master` 构造时消费一次；晚到的注册历史上静默失效

实施中核实了 issue 原文的一处**不可行点**：包根 `zoo_framework/__init__.py` 的 `from . import params` 使内建参数类的解析**必然发生在任何显式配置载入之前**——"在解析现场拦导入顺序"会打断所有合法用法（含正确使用者）。同理，"封后注册硬报错"与脚手架契约测试锁定的合法形态（同进程重复运行入口）冲突。

## What Changes

- **新增 `aop` 能力规格**：把 `@configure` / `@logger` / `@stopwatch` 的注册时机、调用约定（`@configure` 无参调用）、失败模式定下来；`@params` 的顺序契约以"载入世代"新条款覆盖；明确不提供 `@validation`（已删，#49）且不主张连接点/通知/切点等完整 AOP 语义
- **`@params` 顺序耦合从静默改为核对**：`ParamsFactory` 增配置载入**世代**计数；`@params` 解析时记录当时世代；`Master` 构造读到非零世代配置后，点名所有"在从未读到配置的世代里解析过"的类并**大声失败**。全程无配置文件（合法的全默认形态）不触发
- **`@configure` 晚注册从静默改为出声**：`Master` 消费注册表后置封；封后注册**照常登记**（供下一个 `Master()` 消费，保住脚手架重复运行契约）但 MUST 告警"当前实例不会消费它"
- 框架侧"未导入 = 未注册"的缺失在运行时**不可观测**，规格如实声明框架不承诺发现它；缓解机制是入口显式 import（脚手架契约已有测试守护）

## Capabilities

### New Capabilities

- `aop`：装饰器注册面中尚未被其它能力覆盖的部分——`@configure` 的注册/消费/封契约、`@logger` 与 `@stopwatch` 的包装语义、`@params` 的载入世代核对、明确不提供项清单

### Modified Capabilities

无（`config-resolution` 的解析算法与缓存不动；行为变更点以 `aop` 新条款承载）。

## Impact

- **代码**：`core/params_factory.py`（世代计数 + `generation()`）、`core/aop/params.py`（解析记录世代 + `stale_param_classes()`）、`core/aop/configure.py`（封位 + 晚注册告警）、`core/master.py`（构造期核对 + 消费后置封）
- **测试**：新增 `tests/test_aop_determinism.py` 7 条（冻结核对三态 + 封后告警两态 + 判据单元）；conftest 增世代/封位复位接缝
- **BREAKING（窄）**："先导入参数模块（配置不可见）、后构造 Master（配置可见）"的用法从静默默认值改为构造期报错——这正是 issue 要求的失败形态；全程无配置与正常同目录用法不受影响
- **issue**：#51 关闭；#50 的登记表新增两项进程级状态（`_generation`、`_resolved_generation`）
