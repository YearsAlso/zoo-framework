## 1. 前置：基线与影响面确认

- [x] 1.1 记录改动前的测试基线；验证：`pytest -q` 全绿且用例数不少于 208，耗时记录在提交说明中（本机使用 `.venv/Scripts/python.exe -m pytest`，裸 `python` 指向仓库内 3.9 的 `venv/`，不可用）
- [x] 1.2 穷举 `is_loop` 的读点与写点，区分"作为方法调用"与"作为属性读取"；验证：`grep -rn "is_loop" zoo_framework/ tests/ example/` 的结果已逐条归类，且清单覆盖 `core/waiter/base_waiter.py:70`、`core/waiter/safe_waiter.py:33`、`workers/event_worker.py:24`、`workers/state_machine_work.py:28`、`workers/base_worker.py:20`
- [x] 1.3 确认 `run_timeout` 当前无任何写入点，证明超时逻辑恒不可达；验证：`grep -rn "run_timeout" zoo_framework/` 的结果只出现在 `workers/base_worker.py` 与 `core/waiter/base_waiter.py` 的**读取**侧
- [x] 1.4 确认框架内无任何响应器订阅 `<类名>_result` 主题，证明主题变更为安全改动；验证：`grep -rn "_result\"" zoo_framework/` 无消费者，且 `EventReactorManager().reactor_map` 中不存在该主题
- [x] 1.5 列出所有会被 `shutdown()` 影响的存活资源（Waiter 线程池、在飞线程、asyncio 调度任务、SVM 监控线程）；验证：清单与 `core/master.py:293-313` 的实际停机范围逐条对应，缺项即为待修项

## 2. 调度器派发与在飞状态管理

- [x] 2.1 重排 `core/waiter/base_waiter.py:_dispatch_worker` 的登记时序，使登记动作先于任务提交；验证：瞬时返回的 Worker（`delay_time=0`、`_execute` 立即返回）连续调用 `execute_service()` 5 次后 `worker.count == 5`，且 `worker_props` 中无残留条目
- [x] 2.2 把"注销 + 上报"收敛为单一收口函数，由任务完成回调触发，删除 `_dispatch_worker` 中先挂回调后登记的顺序依赖；验证：收口函数在 `grep -n "add_done_callback" zoo_framework/core/waiter/` 中只有一个调用点，且 `_dispatch_worker` 内不再出现 `register_worker(worker, t)` 这种"提交后登记"的写法
- [x] 2.3 从 `worker_running` 上移除 `callback` 形参，使其只负责执行并返回结果；验证：`grep -rn "worker_running" zoo_framework/ tests/` 的所有调用点均为单参形式，且 `pytest -q tests/test_runtime_defects.py` 仍全绿
- [x] 2.4 让线程模式复用同一收口路径（此前线程模式的 `WorkerResult` 被直接丢弃）；验证：`worker.pool.enable=false` 时，订阅结果主题的响应器在 Worker 完成后收到恰好 1 次事件
- [x] 2.5 把在飞计时由 `time.time()` 改为 `time.monotonic()`；验证：`grep -n "time.time()" zoo_framework/core/waiter/base_waiter.py` 不再命中在飞时长计算处
- [x] 2.6 修复 `execute_service` 中 `worker_band(worker.name)` 先于 `if worker is None` 导致的判空不可达；验证：向 `waiter.workers` 注入 `None` 后调用 `execute_service()` 不抛 `AttributeError`，并新增该断言到回归用例
- [x] 2.7 补齐 2.1-2.6 的回归用例（瞬时 Worker、慢 Worker、双模式各一条）；验证：新用例在改动前的代码上失败、改动后通过（用 `git stash` 交叉验证至少一次）

## 3. `is_loop` 语义收敛

- [x] 3.1 把 `workers/base_worker.py:20-23` 的 `is_loop` 由方法改为只读属性，`_props` 为唯一真源；验证：`isinstance(worker.is_loop, bool)` 为真，且 `props={"is_loop": False}` 的 Worker 在 5 个 tick 内只执行 1 次
- [x] 3.2 删除 `workers/event_worker.py:24` 与 `workers/state_machine_work.py:28` 中遮蔽属性的实例赋值；验证：两个默认 Worker 在 5 个 tick 内各执行 5 次（props 已声明 `is_loop: True`），行为与删除前一致
- [x] 3.3 同步修正被旧语义锁定的既有用例 `tests/test_worker.py:23`、`tests/test_worker.py:30`、`tests/test_zoo_framework.py:52`、`tests/test_zoo_framework.py:59`；验证：`grep -rn "is_loop()" tests/` 无结果，且 `pytest -q tests/test_worker.py tests/test_zoo_framework.py` 全绿
- [x] 3.4 复核 `core/waiter/safe_waiter.py:33` 的过滤表达式在属性化后仍表达正确语义；验证：`SafeWaiter` 下声明 `is_loop: False` 的 Worker 在一次调度轮次后不再出现在 `waiter.workers` 中

## 4. 结果上报链路

- [x] 4.1 按 design D2 扩展 `workers/worker_result.py`，使结果携带统一主题常量（沿用现有 `"waiter"` 绑定）与产生它的 Worker 名称；验证：构造的 `WorkerResult` 上可读到非空的主题与 Worker 名，且默认主题不再是"类名小写 + `_result`"的隐式拼接
- [x] 4.2 调整 `workers/base_worker.py:60-62`，使 `run()` 产出使用 4.1 的主题；验证：对任意 Worker 子类调用 `run()`，其 `topic` 等于统一主题常量，与 `cls_name` 无关
- [x] 4.3 让 `reactor/waiter_result_reactor.py` 绑定到统一主题，并支持按 Worker 名过滤（复用 `EventReactorManager.get_reactor` 既有的按名过滤能力）；验证：注册两个 Worker 结果响应器后，只投递给指定 Worker 的那一个
- [x] 4.4 修复 `WaiterResultReactor` 的构造方式，使其不再依赖"同名对象重复绑定"的路径；验证：连续构造 3 次 `Master()` 后 `EventReactorManager().reactor_map[<统一主题>]` 的长度恒为 1
- [x] 4.5 补齐结果上报回归用例（线程模式、线程池模式、模式切换后各一条）；验证：池模式用例断言响应器恰好被触发 1 次（同时覆盖"丢失"与"重复"两种退化）

## 5. 超时控制与配置入口

- [x] 5.1 在 `params/worker_params.py` 中补齐 Worker 调度相关配置入口（默认超时、默认循环标志、默认延迟时间、按 Worker 名覆盖），并为旧键 `worker:pool:enable` 与脚手架产出的 `worker:pool:enabled` 给出兼容或迁移方案；验证：以 `__main__.DEFAULT_CONF` 写出的 `config.json` 能被 `ParamsFactory` 读出非默认的 `WORKER_POOL_ENABLE` 值
- [x] 5.2 删除 `core/waiter/base_waiter.py:97-126` 中无副作用的 `worker_band`，按 5.1 的配置实现超时判定；验证：`grep -n "worker_band" zoo_framework/` 无结果，且配置 `run_timeout` 后超时 Worker 被识别
- [x] 5.3 落实超时的处理动作：记录错误、标记不健康、不再重派该 Worker，且**不阻塞** `execute_service` 的调度轮次；验证：`run_timeout=0.2` 且 Worker 睡 1s 时，连续 3 个 tick 的间隔仍约为配置的调度间隔而非被挂死 Worker 拖住
- [x] 5.4 在代码注释与文档中明确超时语义为"观测 + 熔断，不支持抢占式强杀"；验证：`grep -rn "超时" docs/API_REFERENCE.md zoo_framework/core/waiter/` 的表述与 5.3 的实际行为一致，不含"终止/杀死线程"一类承诺
- [x] 5.5 按 design D4 处置未实现的模式常量（`constant/waiter_constant.py:4-5`、`constant/worker_constant.py:3-12`）：**保留常量值不变（避免导入级 BREAKING），按「已实现 / 未实现占位」分组标注**；验证：`grep -rn "WORKER_MODE_PROCESS\|RUN_MODE_" zoo_framework/` 的每一处都有明确的未实现标注，且已实现与未实现可被区分
- [x] 5.6 按 design D4 修复静默降级（D4 指出的真正危害）：`core/waiter/waiter_factory.py:9-16` 的 `get_waiter` 对无法识别的策略名静默返回 `SimpleWaiter`，`BaseWaiter.get_worker_mode` 也不存在"模式被拒绝"的路径；验证：以无法识别的运行策略名构造调度器时被明确拒绝并指明该策略不可用，且该行为进入回归用例
- [x] 5.7 补齐超时与模式相关回归用例；验证：无 `run_timeout` 配置时超时判定不误伤（长任务正常完成），配置后超时 Worker 被熔断且其余 Worker 不受影响；无法识别的策略名被拒绝；未实现的模式请求被拒绝

## 6. 停机与调度任务异常

- [x] 6.1 为 `BaseWaiter` 增加显式停机入口（停止资源池、等待在飞 Worker、超时后放弃），并由 `Master.shutdown()` 调用；验证：`Master.shutdown()` 后线程数回落至构造前的基线
- [x] 6.2 让 `Master.shutdown()` 触发已注册 Worker 的销毁钩子，使 `StateMachineWorker` 的状态机在退出前落盘；验证：构造 `Master` → 写入一个状态 → `shutdown()` → 断言 pickle 文件已生成且可反序列化出该状态
- [x] 6.3 让 `Master.run()` 为调度任务挂异常回调，`perform()` 抛异常时记录并停止而非让 `run_forever()` 空转；验证：向 `waiter.execute_service` 注入抛异常的替身后运行 `run()`，日志出现错误且循环退出，`task.exception()` 不为 `None` 时被消费
- [x] 6.4 消除 `core/master.py:297` 的 `asyncio.get_event_loop()` 弃用路径；验证：以 `-W error::DeprecationWarning` 运行构造与运行入口不抛出 `DeprecationWarning`
- [x] 6.5 让运行期注册的 Worker 进入调度：`Master.register_worker` 注册后必须刷新调度列表；验证：注册后下一轮 `execute_service()` 中该 Worker 被实际调度（`grep` 之外以执行计数断言）
- [x] 6.6 补齐停机与动态注册的回归用例；验证：新用例在改动前失败、改动后通过

## 7. 异步 Worker 与调度体系接合

- [x] 7.1 覆写 `AsyncWorker._execute`，使其在调度线程内驱动一次协程并返回业务结果；验证：`AsyncWorker` 子类经 `execute_service()` 调度后，其内部计数器为 1，且 `WorkerResult.content` 等于协程返回值而非 `None`
- [x] 7.2 移除在调度路径上永不命中的事件循环分支（`workers/async_worker.py:90-96`），并确保不产生"协程从未被 await"的告警；验证：以 `-W error::RuntimeWarning` 运行 7.1 的用例不报错
- [x] 7.3 让 `run_in_background` 的兜底线程成为 daemon，并把协程异常保存下来由 `result()` 重抛；验证：后台协程抛异常时 `result()` 抛出该异常而非返回 `None`；进程在存在后台任务时仍能正常退出
- [x] 7.4 把 `AsyncWorkerPool` 的信号量与队列改为按当前事件循环惰性创建；验证：先后在两个不同的事件循环中使用同一池实例，不出现"绑定到已关闭循环"的错误
- [x] 7.5 按 design D3 让异步抽象约束真正生效：**为 `AsyncWorker` 引入 `ABCMeta`**，使 `@abstractmethod` 阻止未实现 `async_execute` 的类被实例化；验证：`AsyncWorker("x")` 抛出 `TypeError`，且 `AsyncEventWorker`、`AsyncStateMachineWorker`（二者均已实现 `async_execute`）不受影响，该断言进入回归用例
- [x] 7.6 补齐异步 Worker 回归用例；验证：调度路径执行、异常传播、后台线程 daemon 三项各有独立用例，且在改动前失败

## 8. 事件管道的可靠性

- [x] 8.1 修复 `workers/event_worker.py:40-53` 中 `size()` 与 `pop_value()` 之间的竞态空档（空元素不得引发 `AttributeError`）；验证：在 `size() > 0` 与 `pop_value()` 之间插入并发清空后，`EventWorker._execute` 不抛异常
- [x] 8.2 修复"无响应器即丢弃"：让 `EventNode` 真正携带并递减重试次数，或在次数耗尽后进入可观测的死信路径；验证：入队一个无响应器且声明重试次数的事件后，重试次数按声明递减，最终丢弃时留下可断言的记录
- [x] 8.3 修复响应器执行/通道查询抛异常时"节点已弹出即丢失"的路径：要么回队要么进死信；验证：响应器抛异常后 `channel.size()` 可断言地反映节点去向，不再出现弹出即消失
- [x] 8.4 复核 `gevent.spawn` 的超时语义：`joinall` 超时后仍在运行的响应器不得被静默丢弃结果；验证：人为构造超时的响应器后，有可断言的错误记录或"仍在运行"的可观测状态
- [x] 8.5 补齐事件可靠性回归用例；验证：8.1-8.4 各一条，且在改动前失败

## 9. 响应器注册的幂等性与通道约束

- [x] 9.1 让 `reactor/event_reactor_manager.py:134-154` 的 `bind_topic_reactor` 具备幂等语义：同一对象在同一主题下重复绑定不得重命名、不得重复追加；验证：连续 3 次构造 `Master()` 后该主题下的响应器数量恒为 1
- [x] 9.2 让 `@event(topic, channel=...)` 声明的通道约束在 `dispatch` 路径真正生效；验证：仅声明 `business` 通道的响应器不被默认通道的 `dispatch` 触发
- [x] 9.3 复核通道隔离变更未破坏既有的按主题投递语义；验证：`pytest -q tests/test_reactor.py tests/test_event.py tests/test_runtime_defects.py` 全绿
- [x] 9.4 补齐幂等性与通道隔离回归用例；验证：9.1 与 9.2 各一条，且在改动前失败

## 10. 测试基础设施

- [x] 10.1 在 `tests/conftest.py` 增加自动使用的全局状态清理 fixture，复位单例注册表（Worker 实例缓存、响应器表、通道表、cage 单例）；验证：连续运行两条依赖同名 Worker 的用例，后者不因前者的残留实例而受影响
- [x] 10.2 让 `BaseWorker.run()` 中的延迟等待可注入，使调度用例不必真实等待；验证：涉及 `EventWorker` 的端到端用例耗时显著下降，全量 `pytest -q` 总耗时较基线（1.1 记录值）下降
- [x] 10.3 复核新 fixture 未改变用例语义；验证：`pytest -q` 全绿，用例数不少于基线

## 11. 收尾验证

- [x] 11.1 端到端验证调度可靠性：以默认线程模式运行 20 个 tick，断言事件端到端投递与 Worker 执行次数符合各自声明；验证：用例稳定通过，重复运行 5 次无随机失败（针对浮动的竞态类缺陷）
- [x] 11.2 全量回归确认未破坏既有契约；验证：`pytest -q` 全绿，用例数不少于基线（1.1）
- [x] 11.3 确认公开 API 变更已同步到文档；验证：`grep -rn "is_loop()" docs/` 无结果，`docs/API_REFERENCE.md` 不再承诺不存在的 `BaseWorker.stop()` 与 `_destroy(result)` 销毁回调
- [x] 11.4 确认未夹带范围外改动；验证：`git diff --stat` 共 27 个文件，均属本次范围，不含新增运行时依赖与 `pyproject.toml` 改动。实际范围比原列举多出 4 个文件，各有对应依据：`core/params_path.py` 与 `core/aop/params.py`（配置项别名，D4 的键名兼容需要）、`fifo/node/event_fifo_node.py`（`set_retry_times`，8.2 需要）、`utils/thread_safe_dict.py`（`clear()`，10.1 需要）
- [x] 11.5 复跑 OpenSpec 校验；验证：`openspec validate fix-worker-scheduling` 通过且无 INFO 级警告（MODIFIED 的 Requirement 标题须与 `openspec/specs/` 下既有标题逐字一致，否则归档会被拒绝）
