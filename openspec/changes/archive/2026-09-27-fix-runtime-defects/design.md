## Context

动机见 `proposal.md`。以下是塑造方案的关键现状与技术约束，均已在 Python 3.13.14 上实测确认。

**约束一：`zoo_framework/lock/` 下任何锁原语都无法被继承。** 实测：

| 基类候选 | 3.13.14 下的形态 | 继承结果 |
|---|---|---|
| `threading.Lock` | 类是 `type` | `TypeError: type '_thread.lock' is not an acceptable base type` |
| `threading.RLock` | 工厂函数 | `TypeError: function() argument 'code' must be code, not str` |
| `multiprocessing.Lock` | 绑定方法 | `TypeError: method expected 2 arguments, got 3` |

即 `class BaseLock(<任意一种>)` 在当前 Python 上**不可能工作**，组合是唯一可行路径。

**约束二：整条主执行路径从未被执行过。** 140 个单测覆盖的是对象级行为（FIFO 节点、WorkerResult、参数类），没有用例构造 `Master`、没有用例跑 `waiter.execute_service()`、没有用例走完整 `EventChannel` 分发。所以修复 `Master()` 可构造性之后，**后续可能暴露更多此前被掩盖的缺陷**——这是本次最大的不确定性来源。

**约束三：影响面已确认受限。** `EventWorker` 的引用点只有 `workers/__init__.py`（导出）与 `core/master.py:233`（注册），**没有任何调用点直接构造 `EventWorker()`**；`EventChannel(...)` 的构造点只在 `event/event_channel_register.py` 的 2 处（均经注册器）。

**约束四：框架已在 PyPI 发布 0.5.x-beta**，公开导入路径需保持可用。

## Goals / Non-Goals

**Goals**

- 让框架管理器可被构造并跑通至少一轮调度循环
- 让事件系统的每一条声明的语义都真实生效，且不再有静默丢弃或不可终止的循环
- 为每一条被修复的缺陷留下一个可复现的回归用例，并把"主路径可跑通"固化为集成用例
- 让 `lock` 包的契约自洽（可导入、可作上下文管理器、文档与行为一致）

**Non-Goals**

- 不追求类型注解完整与 CI 类型门禁（由 `establish-type-gate` 承载）
- 不做响应器登记按通道隔离的重构（见 Risks 的"残余限制"）
- 不为死代码新增未需求特性（如为 `TimeLock` 实现计时器线程）
- 不调整公开导入路径，不改 `pyproject.toml` 的依赖列表
- 不清理 `build/`、`test/`、被误提交的 `venv/`（属工程卫生，见 `establish-type-gate`）

## Decisions

### D1 · `Master()` 不可构造：移除 `EventWorker` 的 `@cage`，而非放宽注册表

`@cage` 把 `EventWorker` 从类替换成工厂函数，而注册表用 `issubclass` 做契约校验，二者不可调和。

- **选**：移除 `workers/event_worker.py:14` 的 `@cage`，让 `EventWorker` 恢复为普通类。
- **理由**：`WorkerRegistry` 本身已提供单例能力——`get_worker()` 会把首次实例化结果缓存进 `_worker_instances`。`@cage` 在此是**第二套单例机制**，两套缓存互相覆盖会形成两个真理来源；而它正是唯一让 `issubclass` 崩溃的源头。已确认无调用点依赖 `EventWorker()` 的单例性。
- **已考虑的替代**：让 `register_class` 容忍函数/工厂（`issubclass` 加 `try` 或改走 `register_factory`）。拒绝理由：注册表契约会失去静态可判定性（"什么算合法 Worker 定义"不再能靠类型判断），换来的收益只是保住一个冗余机制。
- **无行为损失**：`EventWorker.__init__` 内部构造的 `EventChannelManager()` 本身仍是 `@cage` 单例，通道管理器共享性不变。

### D2 · `lock` 包：改用组合，并按最小范围修复

- **选**：`BaseLock` 以组合持有 `threading.RLock`（与框架其余部分一致——`master.py`、`state_machine_work.py`、`persistence_scheduler.py` 均用 `threading.RLock`），`acquire`/`release` 委托给它；`__exit__` 返回 `None` 以让上下文体内的异常正常传播；`__init__.py` 补充导出全部公开类型。
- **理由**：继承被约束一证伪。选 `threading` 而非 `multiprocessing` 是因为框架定位是多线程，且现有代码一致使用 `threading`。
- **选**：`TimeLock` 的文档字符串修正为与其实际行为一致的计数闸门语义，**不**实现其声明的"超时后触发回调"。
- **理由**：该包无任何调用点（框架、测试、CI 均无）；在死代码上新增计时器线程属于新增设计而非缺陷修复，且会引入线程生命周期管理这一全新问题面。
- **已考虑的替代**：① 实现超时+回调——违反 YAGNI 且引入新设计；② 删除整个包——虽然它从未可导入因而事实上无人依赖，但删除公开导入路径不可逆，且不应夹带在"缺陷修复"变更中。
- **如实声明**：`CountLock`/`TimeLock` 覆写了 `acquire`/`release`，因此**不提供互斥、也不线程安全**（`self._count -= 1` 非原子）。这一点必须在文档字符串中写明，以满足 spec 的"声明语义 MUST 与实现一致"。

### D3 · 优先级公式：`&` 改为 `|`

`(sys_priority << 8) & user_priority` 实测恒为 0（sys=2,user=2 → 0；sys=5,user=2 → 0），所有响应器优先级不可区分。`<<8` 表明作者意图是"系统优先级占高位、用户优先级占低位"的分段编码，`|` 是表达该意图的正确算子（sys=2,user=2 → 514；sys=5,user=2 → 1282）。

- **选**：`(self.sys_priority.value << 8) | self.user_priority.value`。
- **已考虑的替代**：① `+` —— 位段不重叠时与 `|` 等价，但 user 超过 255 会进位污染系统位段，语义不如 `|` 明确；② 改用元组排序键 `(sys, user)` —— 更干净，但会波及 `__index__`（必须返回 int）的实现，改动面更大。
- **同时修正**：`sys_priority` 被赋值成 `.value`（int）却按 Enum 访问 `.value`。统一让两个字段都存 `EventPriorities` 成员，在 `get_priority()` 内取值。

### D4 · 机制二的排序方向：按优先级由高到低

`reactors.sort(key=lambda x: x.priority)` 有两处错误：属性名不存在（应为 `get_priority()`），且 `list.sort()` 返回 `None`。

- **选**：`sorted(reactors, key=lambda r: r.get_priority(), reverse=True)`。
- **理由**：方向取自 `fifo/node/event_fifo_node.py` 对 `response_mechanism` 的既有注释——"2.者优先级高的先响应"。降序是文档化意图，不是新设计。

### D5 · 五个重试策略的调用次数语义

当前 `RetryForever` 与 `RetryNever` 共用 `while True`（导致 `RetryNever` 死循环），`RetryAlways` 无分支落入 `raise` 且被 `execute()` 吞掉（回调从不执行）。枚举中 `RetryAlways`/`RetryForever`/`RetryOnce` 语义本就重叠，需要先定死语义再改代码。

| 策略 | 回调调用次数上限 | 终止条件 |
|---|---|---|
| `RetryOnce` | 1 | 成功即返回，失败即停止 |
| `RetryNever` | 1 | 成功即返回，失败即停止 |
| `RetryTimes` | `retry_times` | 成功即返回，失败重试至次数用尽 |
| `RetryForever` | 不限 | 仅在成功时返回 |
| `RetryAlways` | 不限 | 仅在成功时返回 |

- **选**：把 `RetryAlways` 与 `RetryForever` 作为**同一语义的别名**在实现与文档中一并声明；`RetryOnce` 与 `RetryNever` 同为"仅尝试一次"。
- **理由**：spec 要求的是"每种策略实现其声明语义且必须终止"，等价别名满足该要求。区分 `Always` 与 `Forever` 需要发明一个当前无人需要的差异（例如是否响应全局停止信号），那属于新设计。
- **须你确认**：若你认为 `RetryAlways` 与 `RetryForever` 必须可区分，请在进入实现前告知——这会改动 spec 的重试要求。

### D6 · 包含性查询：用 `in` 替代 `index(...) != -1`

`list.index()` 未命中抛 `ValueError` 而非返回 -1，而调用方 `EventChannel.refresh_event` / `EventProvider.refresh` 的正常路径恰恰是"未命中则不处理"。

- **选**：改为 `event in self._fifo`。同类修正应用到 `base_fifo.push_values_if_null` 与 `single_fifo.push_value`（后者同样把 `index()` 当作存在性检查）。
- **理由**：直接表达意图，异常不参与控制流。
- **保持不变的既有契约**：包含性以 `EventNode.__eq__` 的 `(topic, content)` 相等为准，而非对象同一性。`replace()` 也是按此定位，本次不改变。

### D7 · 通道队列：两层类属性都要改为实例属性

队列共享发生在**两层**，只改上层不足以满足 spec 的隔离要求：

| 层 | 现状 | 实测 |
|---|---|---|
| `EventChannel` | `_event_fifo: EventFIFO = EventFIFO()` 定义在类体 | `c1._event_fifo is c2._event_fifo` → `True` |
| `BaseFIFO` | `_fifo = []` 定义在类体 | 即使 `EventFIFO` 实例不同，`a.size() == b.size() == 1` |

`BaseFIFO._fifo` 是类属性，且其方法都是类方法（`cls._fifo`），因此**两个不同的 `EventFIFO` 实例仍共享同一个列表**——这是独立于 `EventChannel` 的第二层共享。

- **选（A2）**：两层都改为实例级。`EventChannel` 的 `_event_fifo`/`_reactor_manager` 移入 `__init__`；`BaseFIFO` 的 `_fifo` 移入 `__init__`，其方法由类方法改为实例方法。`EventFIFO` 相应改为直接操作 `self._fifo`。
- **理由**：spec 的场景要求"向通道 A 入队后，通道 B 的队列为空"。只改 `EventChannel` 会让 `_event_fifo` 实例不同但底层列表仍共享，场景依然不成立。"队列隔离"这一要求只有两层都改才是真的。
- **已知代价（需明示）**：`BaseFIFO` 当前的**类级共享队列是被现有测试刻意验证的契约**——`tests/test_base_fifo.py` 的 `test_put`/`test_get` 与 `tests/test_fifo.py::TestBaseFIFO` 的三条用例都以类为单位调用 `BaseFIFO.push_value(...)`/`pop_value()`/`size()`，`tests/test_fifo.py::TestEventFIFO::test_dispatch` 更是直接依赖 `EventFIFO` 写入 `BaseFIFO._fifo`。改为实例级后这批用例需重写为实例调用。这是**对既有已测试契约的修改**，已作为 BREAKING 记入 proposal，并按用户决定采纳。
- **已考虑的替代（A1）**：只重写 `EventFIFO` 为实例级、保留 `BaseFIFO` 的类级契约（只需改 `test_fifo.py` 一行）。拒绝理由：会让 `EventFIFO` 与 `BaseFIFO` 的存储模型永久分叉，把"同一基类的两个子类语义不同"这一隐患固化下来。
- **注意**：`_reactor_manager` 指向的仍是 `@cage` 单例，所以移入 `__init__` 只是持有同一引用，行为不变——**通道隔离只对事件队列成立**，响应器登记仍是全局的，见 Risks。

### D8 · 状态写入：顶层键分支与嵌套键分支对齐

`state_scope.set_state_node` 对无点号的键走 `if node is None: register_node(...)` 后**直接 `return`**，跳过了 `node.set_value(value)`；嵌套键分支则有 `else: node.set_value(value)`。

- **选**：把顶层分支改为与嵌套分支同构（存在则 `set_value`，不存在则注册）。
- **理由**：两条路径语义应当一致，对应 spec 的"顶层键与嵌套键的写入语义一致"场景。`set_value` 同时是触发观察者的入口，所以该修正一并解决"顶层键的观察者收不到通知"。

### D9 · 观察者注册：键不存在时创建占位节点，注销仍抛 KeyError

`observe_state_node` 在节点不存在时直接 `return`，观察者被静默丢弃——而"先声明观察者、等数据到达"恰恰是观察者的主要用法。

- **选**：注册时若键不存在，先以 `None` 创建占位节点再登记观察者。**保留** `unobserve_state_node` 对不存在键抛 `KeyError` 的行为。
- **理由**：这处不对称是刻意的——注销一个从未存在的观察者几乎总是调用方 bug，应当暴露；而注册一个尚未有值的键是正常流程，不应报错。

### D10 · `AsyncWorker`：保留 `name` 构造签名，内部转属性字典

两处缺陷：`super().__init__(name)` 把字符串当成 props 字典传给 `BaseWorker`；四处 `self._worker_name` 引用了不存在的属性（`BaseWorker` 提供的是 `name`）。

- **选**：保留公开签名 `AsyncWorker(name: str | None = None)`，在内部构造 `{"is_loop": False, "delay_time": 1, "name": name}` 后再调 `super().__init__(props)`；`self._worker_name` 全部改为 `self.name`。`AsyncEventWorker`（`async_worker.py:169`）、`AsyncStateMachineWorker` 同样处理。
- **已考虑的替代**：把构造签名改成 `props: dict` 与 `BaseWorker` 一致。拒绝理由：`AsyncWorker` 是公开类，改签名会让"以名称构造"这一 spec 场景不再可用，属于无必要的破坏性变更。

### D11 · 事件分发：修正参数错位，并明确默认值语义

`EventReactorManager.dispatch` 里 `cls.get_reactor(reactor_name)` 把**响应器名当作 topic** 传入，返回值是 `list`，随后 `reactor.execute(...)` 抛 `AttributeError`。开启 `worker.pool.enable=true` 后，每个 worker 的结果事件都在 future 回调里被静默吞掉。

- **选**：`dispatch` 解析出 topic 下、通过通道校验的响应器**列表**并逐个执行，单个响应器失败不阻断其余响应器（对应 spec 的"同一主题的多个响应器均被投递"）。
- **默认值处理**：`reactor_name` 的默认值 `"default"` 与 `get_reactor` 的"按名称过滤"参数语义冲突（过滤一个名为 default 的响应器必然匹配不到）。改为以 `None` 表示"不过滤"，并把 `"default"` 作为历史哨兵值一并视为不过滤，以兼容既有调用点。
- **影响面**：框架内唯一调用点是 `base_waiter.worker_report`，走的是默认值路径。

### D12 · 事件消费路径：调用存在的入口，并修正实参顺序

`workers/event_worker.py` 的消费循环对每个选中响应器执行 `gevent.spawn(reactor.perform, (event_node.content, event_node.topic))`，但 `EventReactor` **没有 `perform` 方法**（只有 `execute(topic, content)`）。属性访问即在当前栈抛 `AttributeError`，异常被 `BaseWorker.run` 的 `except` 吞掉——事件被从队列弹出后即丢失，**端到端投递从未真正发生过**。此外实参顺序与 `execute` 的签名相反。

- **选**：改为 `gevent.spawn(reactor.execute, event_node.topic, event_node.content)`。
- **理由**：`execute` 是 `EventReactor` 的公开入口（`@event` 装饰器、`EventReactorManager.dispatch` 都走它）；实参顺序按签名修正，对应 spec 新增的"响应器收到的主题与内容不互换"场景。
- **范围说明**：这条缺陷是我在规划期报告过、但**未写入本变更原始 spec** 的第 13 条。它阻断的是"事件通道消费路径"这一核心功能，属于同一族"声明了但从不生效"。经与用户确认后纳入本次修复，并在 `event-dispatch` spec 中补上对应要求与场景。

### D13 · 回归测试：先复现为红，再修复为绿

- **选**：每条缺陷先写一个在**当前代码上失败**的用例（复现脚本已在设计阶段验证过可复现），再修复使其转绿。此外新增集成用例：构造 `Master()`、跑若干轮 `waiter.execute_service()`、走一遍 `EventChannel` 端到端分发。
- **理由**：这批缺陷能长期潜伏正是因为缺少这条路径的覆盖——既有 140 个用例无一触及通道消费路径、`Master` 构造或调度循环。没有集成用例，同类问题会再次溜进主路径。
- **实测基线**：用例文件写就后，在修复前测得 **41 failed / 23 passed / 2 errors**。那 23 个通过的是本就正确的契约守护（`RetryOnce`/`RetryForever`/`RetryTimes`、嵌套键写入、机制一/三/四、观察者注销等）。"每条缺陷用例都应失败"这一初始预期并不准确，已据实修正 tasks 中 1.1 的验收描述。

## Risks / Trade-offs

**[修复 `Master()` 后暴露更多被掩盖的缺陷] → ** 主执行路径从未被执行过，修好入口后可能连锁暴露新问题。缓解：任务按"可构造 → 单轮 loop → 事件端到端"递进，每一步先跑通再进入下一步；若中途发现新缺陷且不在本次范围内，暂停并单独提变更，不就地扩大范围。

**[通道隔离的残余限制] → ** 本次只隔离事件队列；响应器的登记仍是全局的（`EventReactorManager.reactor_map` 是 `@cage` 单例上的类属性，按 topic 索引，不区分通道）。所以"通道 A 的事件不会流入通道 B"成立，但"通道 A 注册的响应器不会响应通道 B 的事件"**不成立**。这是刻意不纳入本次范围的结构性改动，spec 已按此收窄（`event-dispatch` 的要求只声明队列隔离）。

**[移除 `@cage` 后 `EventWorker` 不再是单例] → ** 已确认无调用点依赖；若未来有代码直接 `EventWorker()` 期望拿到同一实例，会静默拿到新实例。缓解：由注册表统一提供实例缓存，并在 D1 中记录该约定。

**[优先级开始真正生效会改变响应器执行顺序] → ** 修正前综合优先级恒为 0，修正后按系统/用户优先级排序，依赖旧顺序的调用方会观察到变化。缓解：这正是缺陷的修复目标，已在 proposal 中标注 BREAKING。

**[`CountLock`/`TimeLock` 名为锁但不提供互斥] → ** 二者覆写 `acquire`/`release` 为计数闸门，且计数操作非原子。缓解：按 D2 在文档字符串中如实声明"计数闸门、非线程安全、不提供互斥"，满足 spec 的一致性要求；不改变其行为。

**[修改既有已测试契约（`BaseFIFO` 的类级共享队列）] → ** D7 选择 A2 之后，`tests/test_base_fifo.py` 与 `tests/test_fifo.py` 共 7 个用例需从类级调用改写为实例调用，等于推翻一批现有测试所验证的契约。风险在于"为了让新代码通过而改测试"这一动作本身可能掩盖真实回归。缓解：重写时保持每条用例的**断言语义不变**（仍验证入队、出队、顺序、包含性），只把调用主体由类改为实例；并在提交说明中逐条列出被重写的用例及理由。该代价已由用户明确认可。

**[`EventWorker` 消费路径修正后事件开始真正投递] → ** 此前事件被弹出即丢失，下游从未收到过任何事件。修正后通道消费者会开始真正调用响应器，任何此前"靠事件丢失而侥幸不出错"的用法都会暴露。缓解：这正是本次修复目标；对应 spec 已补上"响应器收到的主题与内容不互换"场景以防止实参顺序再次写反。

**[行为修正导致下游观察到差异] → ** 多条修复会让此前"静默失败/静默丢弃"的路径开始真正生效（顶层状态更新、观察者通知、事件包含性查询、重试策略、worker 结果分发、通道队列隔离、事件真正投递）。这些已在 proposal 中逐条标注 **BREAKING**。缓解：变更本身不引入新 API，回滚方式为回退本次提交序列。

**[`RetryAlways` 与 `RetryForever` 被声明为等价] → ** 若下游期望二者可区分，将观察到行为与预期不符。缓解：见 D5，此为需你确认的决策点。
