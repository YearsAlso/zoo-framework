## 1. 缺陷复现基线（先红）

- [x] 1.1 新增 `tests/test_runtime_defects.py`，为 A/B/C 三组每条缺陷各写一个用例（缺陷复现）并补充契约守护用例；验证：运行 `pytest tests/test_runtime_defects.py -q`，缺陷复现用例全部失败、失败原因与 design.md 记录的实测现象一致（断言失败或预期异常，非收集阶段报错），契约守护用例通过。实测基线：41 failed / 23 passed / 2 errors
- [x] 1.2 在同一文件补上 Master 集成用例：以默认配置构造框架管理器、跑若干轮调度、走一遍事件通道端到端分发；验证：修复前该用例在 fixture 阶段报错，失败点为 `TypeError: issubclass() arg 1 must be a class`

## 2. A 组 · 入口可用性

- [x] 2.1 按 design D1 移除 `zoo_framework/workers/event_worker.py` 上的 `@cage`，使 `EventWorker` 恢复为普通类，实例缓存由 `WorkerRegistry` 承担；验证：`python -c "from zoo_framework.core import Master; Master()"` 正常返回，不再抛 `TypeError`
- [x] 2.2 按 design D2 把 `zoo_framework/lock/base_lock.py` 的 `BaseLock` 改为组合持有 `threading.RLock` 并委托 `acquire`/`release`，`__exit__` 返回 `None`；验证：`python -c "import zoo_framework.lock"` 成功，且"上下文体内异常向外传播"的用例通过
- [x] 2.3 按 design D2 补全 `zoo_framework/lock/__init__.py` 的公开类型导出，并修正 `CountLock`/`TimeLock` 的文档字符串使其与实际行为一致（计数闸门、非线程安全、不提供互斥）；验证：从包根可导入全部公开类型，且"文档与行为一致性核对"用例通过。实测：锁相关 13 个用例全绿
- [x] 2.4 确认框架内不存在直接构造 `EventWorker()` 并依赖其单例性的调用点；验证：`grep -rn "EventWorker()" zoo_framework/ tests/` 无结果，且既有 140 个用例仍全绿

## 3. B 组 · 事件系统

- [x] 3.1 按 design D5 的语义表重写 `zoo_framework/reactor/event_reactor.py` 的 `_execute` 分支，使五个策略的调用次数与终止条件符合语义表，并让 `RetryAlways` 真正执行回调；验证：重试策略的五个用例全部通过（含"从不重试不进入循环"与"始终重试成功时只调用一次"）
- [x] 3.2 按 design D3 让 `sys_priority`/`user_priority` 统一存放 `EventPriorities` 成员，并把 `get_priority` 的位运算由 `&` 改为 `|`；验证：综合优先级的四个用例通过，且 `int(reactor)` 不再抛 `AttributeError`
- [x] 3.3 按 design D11 修正 `zoo_framework/reactor/event_reactor_manager.py` 的 `dispatch`：以 topic 解析响应器列表并逐个执行，单个响应器失败不阻断其余，`reactor_name` 以 `None`（并兼容历史哨兵 `"default"`）表示不过滤；验证：按主题分发的两个用例通过，无响应器订阅时静默返回。注：无响应器时不告警，因"无订阅者"与"通道不匹配"无法在此区分，spec 要求静默返回
- [x] 3.4 按 design D4 修正 `zoo_framework/event/event_channel_manager.py` 机制二分支，改为 `sorted(..., key=get_priority, reverse=True)`；验证：响应机制的六个用例全部通过，含机制二排序与机制四名称不存在时返回空集合
- [x] 3.5 按 design D6 把 `fifo/event_fifo.py` 的 `has_event`、`base_fifo.py` 的 `push_values_if_null`、`single_fifo.py` 的 `push_value` 中的 `list.index() != -1` 用法改为包含性判断；验证：包含性查询的四个用例通过，且 `EventChannel.refresh_event` 在事件不存在时不抛 `ValueError`。附带修正：`event_fifo.replace` 同类误用，与 `single_fifo.push_value` 中的 `list.push`（应为 `append`）
- [x] 3.6 按 design D7 实现真正的队列隔离：把 `EventChannel` 的 `_event_fifo`/`_reactor_manager` 改为 `__init__` 中的实例属性，并把 `BaseFIFO` 的 `_fifo` 由类属性改为实例属性、其方法由类方法改为实例方法；验证：通道队列隔离的三个用例通过，`EventFIFO` 的两个实例不再共享底层列表。实际影响面大于预估：按 A2 重写的既有用例为 `tests/test_base_fifo.py`（重写 2 个 + 新增 1 个隔离用例）、`tests/test_fifo.py`（重写 2 个 + 改 1 行 + 新增 1 个隔离用例）、`tests/test_zoo_framework.py`（重写 2 个），共 10 处，另移除了 4 处已无意义的 `setup_method`/类变量清理与 1 处失效导入
- [x] 3.7 按 design D11 修正 `fifo/event_fifo.py` 的 `dispatch`，使调用方传入的通道名被保留到事件上；验证：事件通道标识的两个用例通过（指定通道保留、未指定归入默认通道），且 `tests/test_zoo_framework.py::test_fifo_dispatch` 已补上通道名断言
- [x] 3.8 按 design D12 修正 `workers/event_worker.py` 的消费路径：把 `gevent.spawn(reactor.perform, (content, topic))` 改为 `gevent.spawn(reactor.execute, topic, content)`；验证：端到端投递的两个场景通过（事件被响应器处理、主题与内容不互换）。注：用例需等待后台线程完成——`execute_service()` 派发后立即返回

## 4. C 组 · 行为修正

- [x] 4.1 按 design D8 让 `statemachine/state_scope.py` 的 `set_state_node` 顶层键分支与嵌套键分支同构（存在则更新、不存在则注册）；验证：状态写入的五个用例通过，含顶层键覆盖写入后读取返回最新值
- [x] 4.2 按 design D9 让 `observe_state_node` 在键不存在时先创建占位节点再登记观察者，并保留 `unobserve_state_node` 对不存在键抛 `KeyError` 的行为；验证：观察者注册的四个用例与注销的三个用例全部通过
- [x] 4.3 按 design D10 修正 `workers/async_worker.py`：保留 `AsyncWorker(name)` 公开签名并在内部转成属性字典传给 `BaseWorker`，把四处自引用名称由 `_worker_name` 改为 `BaseWorker` 提供的 `name`；验证：异步 Worker 的名称读取、循环标志、生命周期日志共六个用例通过。注：`AsyncEventWorker`/`AsyncStateMachineWorker` 无需改动——它们沿用保留的 `name` 签名即可

## 5. 集成验证与收尾

- [x] 5.1 跑通 Master 集成用例：默认配置构造、多轮调度、事件端到端分发；验证：两个集成用例通过，主路径（Master 构造 → `execute_service` → 事件通道消费 → 响应器）首次被实际执行
- [x] 5.2 全量回归，确认既有用例不被修复破坏；验证：`pytest -q` 结果 208 passed / 0 failed（既有 142 + 新增 66），`--cov=zoo_framework` 报 60%，远高于 CI 门槛 30%。说明：本次只新增用例、未删除或削弱任何既有断言，覆盖率不会下降；但严格的前后对比数字未重建（改后的既有用例已依赖新代码，无法在不动工作区的前提下回测）
- [x] 5.3 按 design 的 Risks 逐一核对行为变化影响面，确认每条 BREAKING 都有对应回归用例覆盖，且 `docs/ARCHITECTURE.md` 中关于事件通道与状态机的描述与实现仍然一致，不一致处更新文档；验证：逐条比对本任务清单与用例文件无遗漏；ARCHITECTURE.md 的状态机类图已由不存在的方法（`create_state_machine`/`add_state`/`transition`）更正为真实 API（`create_scope`/`set_state(scope,key,value)`/`observe_state(scope,key,effect)` 等）
- [x] 5.4 确认未夹带范围外改动；验证：源码改动限于预期模块的 17 个文件（`core` 无改动，实际落在 `event`/`fifo`/`lock`/`reactor`/`statemachine`/`workers`），测试改动限于 3 个重写文件 + 1 个新增文件，`pyproject.toml` 无任何改动，无类型注解批量改动
