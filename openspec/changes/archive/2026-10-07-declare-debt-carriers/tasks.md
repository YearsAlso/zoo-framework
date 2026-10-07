## 1. 登记表与机制

- [x] 1.1 新增 `core/process_state.py`：`Carrier` 声明 + `CARRIERS` 登记表（分类/理由/watch/names/reset）+ `reset_process_state()`（异常汇总不互相掩盖）
- [x] 1.2 `tests/conftest.py` 的硬编码复位改为 `reset_process_state()` 单点调用（原三组手工清单入表：容器、类属性重绑定、WorkerRegistry 四表、通道配置，另 #51 的封位/世代）
- [x] 1.3 新增 `tests/test_process_state_registry.py`：全模块可变容器扫描按身份/规范名认领；每条声明完整性（分类 ∈ 允许集、理由非空）；复位幂等；待收编项在册断言

## 2. 扫描收益（上线即修的两处）

- [x] 2.1 `StateEffectScheduler._response_list`：全仓库零读写的死类属性，删除（就地注释记录来源）
- [x] 2.2 `SingleFIFO.index_list`：#50 清单未列的类属性共享欠债，登记为【待收编】（不复位，改复位语义超本切片范围）

## 3. 验证与联动

- [x] 3.1 全量 pytest 700 绿（含跨用例隔离回归）、mypy 0 error、ruff/bandit 绿；openspec validate 全绿
- [x] 3.2 已完成（#50 已关闭；其交付 1 由 absorb-debt-carriers 承接、#32 同步随归档 PR）：PR 合并后：#50 留言——交付 2（归类声明）与验收机制项达成，issue 保持 OPEN 待切片二（类属性收编设计决策，单独立变更）；#32 在办表同步
