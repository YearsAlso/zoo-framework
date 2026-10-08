## Why

`scoped-container`（#29）交付了容器，但进程级共享状态仍有载体在容器之外（issue #50）：`reactor_map` / `_channel_map` 类属性、`_global_registry` 模块单例标着【已知欠债】，注册面/配置面（`config_funcs`、`config_params`）与本轮新增的 effect 执行器、世代计数散落在模块命名空间。测试隔离靠 `tests/conftest.py` 手工维护三组复位清单——**新增一个进程级共享，没有机制保证它被隔离或归类**。

规格依据是 `specs/scoped-container` 的「框架自身的进程级共享 MUST 被显式归类」：它要求的是**显式归类**，不是"全部塞进容器"。本变更落地其切片一（声明 + 机制）；切片二（类属性收编方式的设计决策）单独立变更。

## What Changes

- 新增 `zoo_framework/core/process_state.py`：`CARRIERS` 登记表是进程级共享归类的**唯一真源**——每个载体一条 `Carrier` 声明（分类 ∈ {注册面, 配置面, 待收编, 执行设施, 容器本身, 常量} + 理由 + 可选复位）；`reset_process_state()` 从登记表执行复位
- `tests/conftest.py` 的硬编码复位清单（约 50 行）替换为 `reset_process_state()` 调用——清单缩短为"容器 + 登记表"这一形态，正是 #50 的验收方向
- 机制拦截：新增扫描测试，walk 全部框架模块的模块级/类级可变容器（dict/set/list/ThreadSafeDict），凡不能按对象身份或规范名匹配到登记表即失败——忘归类时红的是测试
- 扫描上线即兑现一笔收益：发现 #50 清单外的两处——`SingleFIFO.index_list`（类属性跨实例共享，文档自标欠债但未列）与 `StateEffectScheduler._response_list`（全仓库零读写的死类属性，直接删除）
- 上一轮新增的载体一并入册：`_effect_executor`（执行设施）、`_sealed` / `_generation` / `_resolved_generation`（随相关条目复位）

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `scoped-container`：新增「进程级共享 MUST 在登记表显式归类且机制可拦截」——把"显式归类"从注释约定升格为数据 + 扫描断言；复位清单 MUST 由登记表生成

## Impact

- **代码**：新增 `core/process_state.py`；`statemachine/state_effect_scheduler.py` 删死类属性；`tests/conftest.py` 复位改调用；新增 `tests/test_process_state_registry.py`（5 条）
- **行为**：仅删除零引用死状态；其余为声明/机制，运行期行为不变（700 全量测试含跨用例隔离验证）
- **issue**：#50 交付 2/验收机制项达成，交付 1（收编设计）与其切片二仍 OPEN；#49 已先行删除两个死载体（`worker_register`、`params_validate_map`）与本表一致
