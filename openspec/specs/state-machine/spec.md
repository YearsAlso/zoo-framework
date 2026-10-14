# state-machine Specification

## Purpose

定义状态作用域内状态值的读写一致性与观察者契约。该能力确保任何键路径的写入都能被后续读取观察到，且观察者在"键尚未存在"这一边界情形下不会被静默丢弃——静默无效是比抛错更难排查的失效模式。

## Requirements

### Requirement: 状态写入 MUST 对任意键路径生效

向状态作用域写入状态值时，无论键是顶层键还是含层级分隔符的嵌套键，后续读取 MUST 返回最新写入的值。键已存在时 MUST 覆盖其值；键不存在时 SHALL 自动创建。

#### Scenario: 顶层键的重复写入覆盖旧值
- **WHEN** 对同一顶层键先后写入值 1 与值 42
- **THEN** 读取该键返回 42

#### Scenario: 嵌套键的重复写入覆盖旧值
- **WHEN** 对同一嵌套键先后写入值 1 与值 2
- **THEN** 读取该键返回 2

#### Scenario: 首次写入自动创建
- **WHEN** 对一个此前不存在的键写入值
- **THEN** 读取该键返回该值

#### Scenario: 写入后删除
- **WHEN** 删除一个已存在的键，随后读取该键
- **THEN** 读取返回空值

#### Scenario: 顶层键与嵌套键的写入语义一致
- **WHEN** 对顶层键与嵌套键分别执行"写入、覆盖写入、读取"三步
- **THEN** 两条路径的读取结果都等于各自最后一次写入的值

### Requirement: 观察者注册 MUST 对任意键路径生效

向状态作用域注册观察者时，无论目标键是否已存在，注册 MUST 生效。注册生效后，该键的值每次发生变化，观察者 MUST 被通知一次，且通知载荷 MUST 包含变化后的值。

#### Scenario: 对已存在的键注册观察者
- **WHEN** 先写入键的值，再注册观察者，随后再次写入该键
- **THEN** 观察者被通知一次，且载荷中的值为最新写入的值

#### Scenario: 对尚不存在的键注册观察者
- **WHEN** 先对一个不存在的键注册观察者，再写入该键
- **THEN** 注册未被丢弃，观察者在该次写入后被通知

#### Scenario: 连续写入触发多次通知
- **WHEN** 注册观察者后连续两次写入不同的值
- **THEN** 观察者被通知两次，且两次载荷值分别为对应写入的值

#### Scenario: 多个观察者都被通知
- **WHEN** 对同一个键注册两个观察者后写入该键
- **THEN** 两个观察者都被通知一次

### Requirement: 观察者注销 MUST 停止后续通知

注销观察者后，该键的后续变化 MUST NOT 再通知该观察者。注销一个不存在的状态键时 SHALL 抛出 KeyError 以暴露调用方错误，MUST NOT 静默返回。

#### Scenario: 注销后不再通知
- **WHEN** 注册观察者、写入一次、注销该观察者、再写入一次
- **THEN** 观察者只在注销前被通知一次

#### Scenario: 注销不存在的键抛出 KeyError
- **WHEN** 对一个不存在的状态键注销观察者
- **THEN** 抛出 KeyError

#### Scenario: 注销其中一个观察者不影响其他观察者
- **WHEN** 对同一个键注册两个观察者，注销其中之一后写入该键
- **THEN** 仅未被注销的观察者收到通知

### Requirement: 状态写路径的 effect MUST 以线程原语并发执行且有界等待

状态节点的 effect（观察者）SHALL 在线程执行器上并发执行，MUST NOT 依赖 gevent / greenlet。写入操作对 effect 完成情况的等待 MUST 有界超时（当前定为 5 秒）：超时后写入 MUST 正常返回而不再阻塞，MUST NOT 永久挂起写路径。effect 抛出的异常 MUST NOT 传播给写入方，但 MUST 可观测地上报。本条款 MUST NOT 改变"写入在超时内同步等待 effect"的既有语义——改为非阻塞投递属另行裁定的行为决策。

#### Scenario: effect 正常执行各一次
- **WHEN** 一个节点挂有两个 effect，随后对该节点写入值
- **THEN** 两个 effect 各被调用一次，载荷含写入的值与版本号

#### Scenario: 慢 effect 不挂死写路径
- **WHEN** 某 effect 的执行时长超过超时上限
- **THEN** 写入在超时后返回，不抛出异常，后续写入不被该 effect 阻塞

#### Scenario: effect 异常不传播给写入方
- **WHEN** 某 effect 执行中抛出异常
- **THEN** 写入调用不抛出，该异常被记入日志

#### Scenario: 无 greenlet 的构建上状态模块照常工作
- **WHEN** 在不安装 gevent 的 Python 构建上导入状态机模块并执行写入
- **THEN** 上述各场景行为一致，不出现 ImportError

### Requirement: 状态机持久化恢复 MUST 真正生效

`StateMachineManager.load_state_machines` MUST 能恢复框架自身落盘的形态（`get_state_machines()` 返回并经 pickle 写出的 `ThreadSafeDict`）——读回后按作用域查询 MUST 取回落盘时的状态值。为兼容旧文件与手工注入，普通 `dict` 入参 MUST 被接受并包装为 `ThreadSafeDict`；无法识别的入参 MUST 明确失败（`TypeError`）而非静默空操作。`have_loaded()` MUST 只在恢复流程真正完成后为真——MUST NOT 出现"声称已加载但状态从未恢复"的形态，该假象会同时误导日志与短路后续重试。恢复语义为**整表替换**：进程首次解析后从盘载入时当前实例必为空表（替换与合并等价）；在非空状态上显式重载是使用者的有意动作。

#### Scenario: 自家落盘形态读回即恢复
- **WHEN** 状态经落盘（deepcopy + pickle）后在新进程语境读回并调用 `load_state_machines`
- **THEN** 按作用域与键查询取回落盘时的值；`have_loaded()` 为真

#### Scenario: 备份恢复路径同样真正生效
- **WHEN** 主文件损坏，管理器经备份文件恢复
- **THEN** 备份中的状态被真实恢复，而非仅置"已加载"标志

#### Scenario: 无法识别的入参明确失败
- **WHEN** 以既非 None、也非 dict/ThreadSafeDict 的对象调用 `load_state_machines`
- **THEN** 抛出 `TypeError` 且"已加载"标志保持为假，由调用方的异常路径决定后续行为

### Requirement: 状态 effect 调度器 MUST 能把 effect 登记到索引且二者一致

`StateEffectScheduler` 向索引登记 / 移除状态 effect 时，被调用的索引方法 MUST 真实存在，MUST NOT
在运行期以 `AttributeError` 失败。登记后，索引 MUST 能按状态（分组）与全集两处查到该 effect；
移除后 MUST 在两处都不再包含它。移除 MUST 幂等：目标不存在时 MUST NOT 抛错。本补齐 MUST NOT 改变
调度器既有的查询（`get_state_effect`）与执行（`execute_state_effect`）语义。

#### Scenario: 登记 effect 后索引可查

- **WHEN** 经 `StateEffectScheduler.add_state_effect` 登记一个 effect
- **THEN** 索引的按状态分组与全集都能查到它，且调用不抛 `AttributeError`

#### Scenario: 移除 effect 后索引不再包含

- **WHEN** 登记一个 effect 后再经 `StateEffectScheduler.remove_state_effect` 移除它
- **THEN** 索引的按状态分组与全集都不再包含该 effect

#### Scenario: 查询与执行语义不变

- **WHEN** 登记一个 effect 后按状态查询并执行
- **THEN** 查询返回该 effect，执行调用到该 effect 的回调

### Requirement: 持久化失败 MUST 显式可感知

持久化无法完成时，系统 MUST 明确报错，MUST NOT 只记录一条日志、把失败留给被忽略的返回值。目标目录
不存在或不可写这类**必然且持续**的失败 MUST 在启动时被校验并当场失败（`start()`）；落盘失败时
`save()` MUST 抛出 `PersistenceError`，且 MUST NOT 清除脏标记（数据仍未落盘，须可重试）。成功的
落盘 MUST 返回成功信号；读盘在文件缺失时 MUST 仍优雅返回空值——读盘缺失是正常态，与写盘不可完成
分属不同语义。校验失败的错误信息 MUST 指明不可用的目录与配置键 `stateMachine:picklePath`。

#### Scenario: 目标目录不存在时落盘明确报错

- **WHEN** 目标文件的父目录不存在，且持久化调度器已有待落盘数据
- **THEN** `save()` 抛出 `PersistenceError`，错误信息含该目录，且脏标记仍为真、不留下半成品文件

#### Scenario: 启动时校验目标目录

- **WHEN** 以父目录不存在的路径启动持久化调度器
- **THEN** 启动当场失败并抛出 `PersistenceError`，而非进入后续每拍失败

#### Scenario: 目录可用时落盘照常成功

- **WHEN** 目标目录存在且可写
- **THEN** `save()` 返回成功信号、脏标记清零、文件落盘

#### Scenario: 读盘缺失文件仍优雅

- **WHEN** 目标文件不存在
- **THEN** `load()` 返回空值而不抛出异常
