## Purpose

定义本仓库 AOP 装饰器注册面中尚未被其它能力覆盖的契约：`@configure` 的注册/消费/封语义、`@logger` 与 `@stopwatch` 的包装语义、`@params` 的配置载入顺序核对，以及明确不提供项。本仓库的 AOP 只是**装饰器注册面**——没有连接点、通知或切点匹配，本规格也不主张引入。

## ADDED Requirements

### Requirement: `@configure` MUST 按"导入期注册、构造期一次消费"的契约工作

`@configure(topic)` MUST 在装饰发生时（导入期副作用）把函数登记进 `config_funcs[topic]`；同一 topic 重复注册以最后登记者覆盖。`Master` 构造时 MUST 遍历注册表并**无参调用**每个注册函数——被注册函数 MUST 可在无参下调用成功（无参或全部参数带默认值），否则构造失败应归因于该函数。注册发生在 `Master` 已消费注册表之后（"封后"）时，系统 MUST 照常登记（供后续 `Master()` 消费）并 MUST 发出可观测告警，说明当前实例不会执行它；MUST NOT 静默丢弃。模块"从未被导入"导致的注册缺失在运行时不可观测，框架 MUST NOT 承诺发现它——入口显式 import 是唯一缓解。

#### Scenario: 无参调用契约
- **WHEN** 一个无参函数经 `@configure` 注册，随后构造 `Master`
- **THEN** 该函数在构造期被调用恰好一次

#### Scenario: 带必选参数的注册函数大声失败
- **WHEN** 注册的函数存在无默认值的必选参数，随后构造 `Master`
- **THEN** 构造抛出 `TypeError` 且调用点可归因到该函数，而非静默跳过

#### Scenario: 封后注册出声但仍可被下一个 Master 消费
- **WHEN** `Master` 已构造（注册表已消费），代码再次经 `@configure` 注册一个函数，随后再构造一个 `Master`
- **THEN** 第二次注册产生一条指明"当前实例不会消费"的告警；该函数仍被登记，并在第二个 `Master` 构造时被调用

### Requirement: `@params` 的载入顺序 MUST 在 Master 构造时核对

`ParamsFactory` MUST 维护配置载入**世代**计数（每次成功读入配置文件 +1）；`@params` MUST 在解析每个参数类时记录当时的世代。`Master` 构造在成功读到非零世代配置后，MUST 核对所有在"从未读到配置"（世代 0）状态下解析过的参数类，存在则**大声失败**并点名其限定名——因为这些类的取值已冻结在默认值，而运行期有真配置可用。全程不存在配置文件时（世代恒为 0），解析取默认值 MUST 作为合法形态放行，核对 MUST NOT 触发。参数类在配置可见（同目录 config.json 存在）时首次解析的常规形态 MUST NOT 被误报。

#### Scenario: 冻结在默认值的类被点名
- **WHEN** 某参数类在配置文件不可见时被首次导入解析，随后以可见的配置文件构造 `Master`
- **THEN** `Master` 构造抛出 `RuntimeError`，错误信息点名该参数类并给出可操作的修正指引

#### Scenario: 无配置文件时全默认合法
- **WHEN** 进程内始终不存在配置文件，参数类解析全部落到默认值，随后构造 `Master`
- **THEN** 构造成功，不触发核对

#### Scenario: 正常同目录用法不被误伤
- **WHEN** 参数类首次解析时同目录 config.json 已可读（解析顺带载入配置）
- **THEN** 该类记录的世代非 0，后续 `Master` 构造不报错，且取值为配置值

### Requirement: `@logger` MUST 保留类的可用性与返回值透传

`@logger` 作用于类时 MUST 返回**同一个类**（不替换类身份），MUST 为类挂上 `_logger`（按类名取 logging logger 并经框架日志配置装配），并把类字典中的可调用成员包装为"进入与退出各记一条 debug 日志、返回值与参数原样透传"的形态。包装 MUST NOT 改变方法经实例或类访问时的绑定语义（被装饰类 MUST 可正常构造、调用与作为 Worker 注册）。

#### Scenario: 被装饰类照常可用
- **WHEN** 一个 `BaseWorker` 子类经 `@logger` 装饰后被实例化并执行
- **THEN** 构造与执行行为与未装饰时一致（返回值透传），且进入/退出有 debug 日志可观察

#### Scenario: _logger 可用
- **WHEN** 读取被 `@logger` 装饰类的 `_logger`
- **THEN** 得到 logging Logger 实例，可直接记录日志

### Requirement: `@stopwatch` MUST 保留元数据并外报耗时

`@stopwatch` MUST 以 `functools.wraps` 保留被包装函数的元数据（`__name__`、`__doc__`），MUST 原样透传返回值，并 MUST 在被包装函数返回后外报一次耗时。当前实现输出至 stdout；迁移到框架日志面属行为变更，需另立变更裁定。

#### Scenario: 元数据与返回值不受影响
- **WHEN** 用 `@stopwatch` 包装一个有返回值与 docstring 的函数并调用
- **THEN** 返回值与未装饰时一致，`__name__`/`__doc__` 保持原值，且产生一条耗时输出

### Requirement: AOP 面 MUST 明确声明不提供项

框架 MUST NOT 从任何公共面导出 `@validation` / `validation_params`（已随 #49 删除）；`@worker` / `worker_register` 处于弃用周期（模块路径保留一个 minor，使用即告警）。`core/aop` 包 MUST 只包含装饰器注册面，MUST NOT 引入连接点、通知或切点匹配机制。

#### Scenario: 不提供项不可被导出使用
- **WHEN** 检查 `zoo_framework.core.aop` 的 `__all__`
- **THEN** 不含 `validation` / `validation_params`；`worker` / `worker_register` 不在导出中，从模块路径使用时得到弃用告警
