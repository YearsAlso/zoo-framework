## Why

`declare-debt-carriers`（#50 切片一）把"显式归类"变成了登记表 + 扫描拦截，但三处【已知欠债】仍停在"待收编"：`EventReactorManager.reactor_map` 与 `EventChannelRegister._channel_map` 是**类属性**——容器持有本类的实例、够不到类属性；`get_worker_registry()` 是**模块级隐式单例**。测试复位因此仍有三处不走容器的路径（conftest/登记表手工复位），"新增进程级共享没有机制保证被隔离"只解决了一半（发现靠扫描，复位仍靠手抄条目）。

经评审拍板按**方案 A** 收编：状态归实例、由框架进程级容器承载（issue #50 的铁证——三组手工复位清单——就此消失）。

## What Changes

- **`reactor_map` / `_channel_map` 降为进程级实例属性**：两类已 `@process_scoped`，`__init__` 建实例 map；**元类 property 代理**保持类级读写写法兼容（`EventReactorManager.reactor_map` 读、旧复位写法的整表替换均转发到进程级实例）——实例属性查找不经元类，`self.reactor_map` 是普通实例属性，既有 classmethod 零改动
- **`bind_topic_reactor` 在登记现场设置响应器 join 超时**：注册表降为实例态后首次构造必为空表，原"`__init__` 遍历刷新"兜底只剩空转；超时设置随之前移到注册点，语义等价覆盖原有时序洞
- **`EventChannelRegister` 死属性删除**：`_single` / `_instance` 全仓库零读写
- **`WorkerRegistry` 进程级入口收编进容器**：`register_process_instance(WorkerRegistry, INSTANCE_GUARANTEED)` + `get_worker_registry()` 改 `process_instance()`；模块全局 `_global_registry` 退役。**直接 `WorkerRegistry()` 构造语义不变**（可建私有实例，未加 `@process_scoped` 正是为了这条区分）
- **`WorkerRegistry` 补实例内 RLock**（收编前提）：四张表此前的裸 dict 在运行期注册与派发并发下并无自保；补齐后 `INSTANCE_GUARANTEED` 声明与实现一致
- **登记表同步**：三条目分类"待收编"→"容器本身"、reset 函数退役（容器 reset 覆盖）；`SingleFIFO.index_list` 仍为待收编（本变更不动其复位语义，收编在后续）

无公共 API 变化、无 BREAKING。

## Capabilities

### New Capabilities

无。

### Modified Capabilities

- `scoped-container`：新增「登记于容器的进程级管理器 MUST 由容器复位统一承载」——实例化的进程级状态经容器 reset 全量复位；类级读取入口（若为兼容保留）MUST 转发到容器实例，MUST NOT 另存一份状态

## Impact

- **代码**：`reactor/event_reactor_manager.py`、`event/event_channel_register.py`、`core/worker_registry.py`、`core/process_state.py`（条目分类与 reset 退役）
- **测试**：`tests/test_process_state_registry.py` 收编断言（待收编→容器本身）；`tests/test_worker_scheduling.py`、`tests/test_run_identity.py`、`tests/test_scoped_container.py` 等 705 条全量回归；复位隔离由 conftest 的容器 reset 单一路径承载
- **文档**：CHANGELOG 记 Changed；`reactor_map`/`_channel_map` 处【已知欠债】注释改写为归属说明
- **issue**：#50 交付 1 达成、可关闭（`SingleFIFO.index_list` 收编作为登记表在册项转后续小变更，不再阻塞 #50 主诉求）
