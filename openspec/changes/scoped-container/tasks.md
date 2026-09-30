## 1. 前置核对（硬前置，未满足不得开工 **第 2–6 组**）

- [x] 1.1 确认 `scheduler-model-seam` 引入的会话标识已落地可用；验证：运行期可取到会话标识，且在工作线程内可访问、并发下不串号。**未落地则第 2–6 组不得开工**——作用域将只能退化为进程级，等于没做。第 7 组（配置解析）不受此约束。**核对通过**：`zoo_framework/core/run_identity.py`（`RunIdentity`/`current_identity`/`carry_context`）已随该变更提交并归档，本次在提交态上跑跨线程子集 **16 passed / 0 failed**（`test_worker_thread_sees_the_dispatchers_identity` 覆盖线程与线程池两种模型、`test_concurrent_runs_do_not_cross_identities` 用栅栏强制两次运行在时间上重叠）；结果侧另有"按登记时标识盖章，不依赖工作线程上下文"与"登记项被清理时不编造值"两条兜底用例。**第 2–6 组解锁**
- [x] 1.2 复核 `scheduler-model-seam` 的 D3（显式句柄为真相来源、跨线程显式复制上下文），确认本变更的作用域传递方式与之同源；验证：本变更的设计中作用域句柄为显式传入，未依赖隐式上下文读取；若有冲突先停下对齐。**核对通过，无冲突**：本变更 D3 已直接引述并服从该决策。对照落地实现，该决策的机制是"登记时把标识**存入显式句柄**，结果按句柄盖章"——上下文变量只作登记当时的便利读法，跨线程由 `carry_context` 显式 `copy_context` 携带；`test_result_is_stamped_with_the_dispatching_run` 与 `test_result_identity_survives_a_lost_thread_context` 分别固定了"以句柄为准"和"句柄缺失时不编造"两端。本变更的作用域句柄按同一形态设计（显式传入/由已持有者注入），故同源
- [x] 1.3 清点全部 `@cage` 使用点（当前 8 处）与其共享语义；验证：清单成文，逐项注明所属作用域（预期全为进程级）与线程安全归属（实例自身保证 / 无状态 / 依赖内部锁）。**已完成并写入 `design.md`**：8/8 为进程级（与预期一致）；线程安全归属实测为**无状态 3 / 依赖内部锁 3 / 无任何保证 2**，并非清一色。清点中发现四处既有缺陷 **F1–F4** 并已记入 `design.md`：F1 `EventRegister.event_list` 为进程级单例上的裸 list（模块仅在 `event/__init__.py` 再导出、框架内无调用点，属潜在缺陷但是公开导出面）；F2 `EventChannelRegister.get_channel` 的 check-then-act 不原子（可静默丢弃一个 `EventChannel` 及其 reactor）；F3 `StateMachineManager` 的 `get_and_create_scope`/`create_scope`/`set_state` 复合操作不原子、`_local_store_loaded` 为裸 bool——**该处正落在 `scheduler-model-seam` 第 4.5 组的归属写入路径上**，因该组用例是单线程故未暴露；F4 `WaiterResultReactor`/`EventReactor` 执行期读共享可变字段（`retry_times` 等）而调用方在派发外赋值，无栅栏。**范围裁定**：F1–F4 均不在本变更修复范围内（本变更是把归属显式化、让声明必填，不是修这些 manager 的并发）；处置为迁移时如实声明（F1/F4 不得写"实例自身保证"），F2/F3 记为独立缺陷且 spec 不声称已修。据此已同步修正 `design.md` 中"8 处本就依赖内部锁或无状态"的过宽表述

## 2. 容器、作用域与标识

- [x] 2.1 实现容器与作用域表达（进程级 / 会话级 / 原型级）；验证：同作用域内同一注册项解析两次返回同一实例；两个会话作用域解析返回不同实例；进程级项跨会话返回同一实例。**已完成**：新增 `zoo_framework/core/container/`（`scope.py` / `thread_safety.py` / `registration.py` / `container.py`），公开面为 `ScopedContainer` / `Scope` / `ScopeKind` / `ThreadSafety`。三条 scenario 各有用例（`TestResolutionIsBoundedByScope`），另加会话内幂等、原型级每次新建两条。**两处刻意的明确拒绝**（不做静默降级，与 `scheduler-model-seam` 的"MUST NOT 静默降级"同调）：① 用进程句柄解析会话级项 → `ValueError`（那等于把 N 个会话合成一个）；② `Scope(ScopeKind.SESSION)` 缺会话标识 → `ValueError`（会退化成进程级），`Scope.of(None)` 同理而非退回进程级。**作用域句柄为必填参数**，不设"不传即进程级"的默认值（D3）。并发正确性单列：`test_concurrent_resolve_yields_one_instance` 用 8 线程 + 解析前栅栏断言只构造一次；**已实测该用例具备鉴别力**——把细粒度锁换成"每次一把新锁"（等于不互斥）后构造次数变为 8、结果也不再是同一实例
- [x] 2.2 注册项标识改为限定名（模块 + 限定名）并支持显式名覆盖；验证：两个同名但定义位置不同的类被识别为不同注册项，各自解析返回自身类型的实例，不出现"第二个解析到第一个实例"。**已完成**：`qualified_name(cls)` = `f"{cls.__module__}.{cls.__qualname__}"`，`name=` 覆盖。用例用两个独立函数作用域内的同名类（`_define_alpha` / `_define_beta`，限定名含所在函数）验证"不同定义位置 → 不同注册项 → 各自解析到自身类型"。**已披露的语义边界**：限定名相同但类对象不同的两类（如同一 helper 反复 `type()` 造出的同名类、或模块被重新加载）会被识别为**同一**注册项——这是限定名作键的固有语义（与 `@params` 同策略），已在 `tests/test_scoped_container.py` 的 `_service` docstring 中写明。重复登记同一项为幂等（no-op），以不同身份登记同一标识则明确拒绝并指出应改用 `replace()`——**静默覆盖正是 `@cage` 的原罪**
- [x] 2.3 保留类型契约；验证：对解析结果执行以注册类型为第二参数的 `isinstance` 正常返回布尔值；对注册类型执行 `issubclass` 亦正常——两者均不抛 TypeError。**已完成**：容器**不替换类**，单例语义由解析期缓存提供而非改写类的身份，故类型契约天然成立。`TestTypeContractIsPreserved` 四条覆盖 `isinstance` 真/假两向、`issubclass`、`type(resolved) is target`，并单列一条断言登记不改动类本身（`isinstance(target, type)` 仍成立、`type(target).__name__` 不变）——这是与 `@cage` 的分界点

## 3. 生命周期与线程安全

- [ ] 3.1 实现显式释放与销毁钩子；验证：释放作用域触发已声明钩子且只触发一次；释放后查询该作用域不再保有此前实例；重复释放不抛异常且钩子不重复调用
- [ ] 3.2 使构造阶段的异常不留下半构造实例；验证：令某注册项实例化抛异常，该次解析不残留实例，且后续释放不影响其他实例
- [ ] 3.3 把线程安全归属实现为注册必填声明；验证：未声明者被拒绝注册并指明缺少该声明；容器保证串行的项在并发解析与使用时被串行化；仅限单线程的项在不符的线程上被拒绝或显式告警而非静默返回。**部分前置披露**：本条的第一个 scenario（未声明即拒绝）已在**第 2 组**落地——注册 API 的形参表在那里定型，`thread_safety` 若不给默认值就会抛裸签名 `TypeError`（`DID NOT RAISE ValueError` 实测），而 spec 要求"注册被拒绝并**指明缺少该声明**"，故 `thread_safety` 默认 `None` 并由领域校验拒绝，`TestThreadSafetyDeclarationIsRequired` 四条已覆盖（含显式传 `None` 与未知取值）。剩下一项待做：**串行化与单线程校验这两个行为**

## 4. 测试接缝

- [ ] 4.1 实现按作用域替换实现与重置；验证：注入假实现后解析返回假实现；在一个作用域替换后另一作用域仍解析到原实现；重置后解析回原实现

## 5. 迁移现有使用点

- [ ] 5.1 把 8 处 `@cage` 使用点逐个改为显式进程级注册，每处补线程安全归属声明；验证：逐点改造后既有 `test_event.py`、`test_reactor.py`、`test_zoo_framework.py`、`test_state_machine.py` 全绿；任一点转红即回退该点
- [ ] 5.2 处置 `@cage` 本身（退场，或保留为"只登记不替换类"的语法糖）；验证：`tests/test_aop.py` 的两条 `cage` 断言按新语义改写后通过，且断言语义（可实例化、单例语义成立）保持不变
- [ ] 5.3 留下约束使"用装饰器替换类"不再蔓延；验证：新增的检查或用例能拦住该模式（例如对新增的类替换型装饰器报错）

## 6. 收尾验证

- [ ] 6.1 全量回归；验证：`pytest -q` 全绿，用例总数高于本变更开始时
- [ ] 6.2 确认未夹带范围外改动；验证：`git diff --stat` 限于容器、8 处使用点与测试；不含 `aop/` 其他装饰器的重构、不含 AOP 织入机制、不含 `@params` 改造、不含依赖变更
- [ ] 6.3 核对文档与接口表述未越界；验证：不出现"已实现 AOP 织入 / 自动装配 / 循环依赖检测 / 配置驱动 bean"这类超出实现的表述
- [ ] 6.4 确认本变更与 `scheduler-model-seam` 在作用域传递上的一致性有可核对的依据；验证：两处文档对"显式句柄为真相来源"的表述一致，且实现的传递路径不依赖隐式上下文

## 7. 配置解析（**不依赖会话标识，可与第 2–6 组并行**）

- [x] 7.1 把 `core/aop/params.py` 的解析缓存键由裸类名改为限定名；验证：两个定义位置不同的同名参数类各自解析到自己的配置路径对应的值，不出现第二个类被跳过解析。**披露**：同时改写了 `tests/test_scaffold_cli_contract.py` 的两处——其清理辅助原先按裸类名 `pop("DemoParams")`，且 docstring 明确把"按裸类名索引"记为已知问题（该测试是被迫绕开本缺陷的第三处痕迹）
- [x] 7.2 为该改动补回归用例；验证：新增 `tests/test_config_resolution.py`，其同名类两条用例在改动前失败（`beta.KEY == 'from-alpha'`、`beta is alpha`）、改动后通过；同一参数类重复导入仍只解析一次。实测红基线 2 failed / 9 passed → 修后 11 passed
- [x] 7.3 把别名回退顺序固定为可验证契约；验证：首选存在不取别名、首选缺失取别名、多别名按声明顺序取首个已配置者、全部缺失取默认值——四条各有用例（改动前即绿，属契约守护）
- [x] 7.4 把"已配置的假值"与"缺失"的区分固定为可验证契约；验证：布尔项配 `False` 得 `False`、数值项配 `0` 得 `0`、字符串项配空串得空串，均不落回默认值（改动前即绿，属契约守护）
- [x] 7.5 确认该组改动未改变既有配置读取行为；验证：全量 `pytest -q` **367 passed / 0 failed**，且 `Master()` 在默认配置下仍正常构造并注册两个默认 Worker
