## 1. 收编三处已知欠债（方案 A）

- [x] 1.1 `EventReactorManager`：`reactor_map` 降实例属性（`__init__` 建表）；元类 `_ReactorMapProxyMeta` 提供类级读/写转发；`bind_topic_reactor` 在登记现场设置响应器 join 超时（取代构造期遍历兜底）
- [x] 1.2 `EventChannelRegister`：`_channel_map` 同形态降实例属性 + 元类代理；删除零读写的 `_single` / `_instance` 死属性
- [x] 1.3 `WorkerRegistry`：`register_process_instance(…, INSTANCE_GUARANTEED)` + `get_worker_registry()` 走 `process_instance`；`_global_registry` 退役；实例内补 `RLock`（public 方法全程持锁、查询走快照），声明自此如实；直接构造私有实例语义不变

## 2. 账目同步

- [x] 2.1 `process_state.CARRIERS`：三条目分类改"容器本身"、手工 reset 函数退役（容器条目覆盖）；`SingleFIFO.index_list` 保持"待收编"在册（后续小变更承接）
- [x] 2.2 `tests/test_process_state_registry.py`：收编断言从"待收编"改为"容器本身"
- [x] 2.3 源码内【已知欠债】注释改写为归属说明（两处 + worker_registry）

## 3. 验证

- [x] 3.1 全量 pytest 705 绿（扫描认领、conftest 单一路径复位、run-identity / worker-scheduling / scoped-container 回归全过）、mypy 0 error、ruff/bandit 绿；openspec validate 全绿
- [ ] 3.2 PR 合并后：#50 关闭留言（交付 1 + 交付 2 + 验收两项全达成；`SingleFIFO.index_list` 作为登记表在册项转后续，不阻塞）；#32 在办表同步
