## Purpose

定义调度器在派发、在飞状态维护、执行模式判定、超时处理、结果投递、停机回收与运行期注册各环节的语义。该能力使 Worker 在"瞬时完成"与"长时间运行"两种极端下都表现一致，且任一环节的失败都有明确且可验证的去向，而非静默停摆或静默丢弃。

## ADDED Requirements

### Requirement: 调度 MUST 使循环 Worker 持续执行、单次 Worker 恰好执行一次

系统 SHALL 依据 Worker 声明的循环标志决定其在调度轮次之间是否保留。声明循环的 Worker MUST 在每一轮调度中被重新派发；声明单次的 Worker 在完成一次执行后 MUST NOT 被再次派发。该判定 MUST 只依赖声明的配置值，MUST NOT 因执行耗时长短、MUST NOT 因该配置键是否曾被某处赋值而改变。

#### Scenario: 瞬时完成的循环 Worker 跨多轮持续执行
- **WHEN** 一个执行立即返回的循环 Worker 被连续调度多轮
- **THEN** 每一轮它都被派发一次，总执行次数等于调度轮次数

#### Scenario: 声明单次的 Worker 只执行一次
- **WHEN** 一个声明非循环的 Worker 被连续调度多轮
- **THEN** 它只被派发一次，总执行次数为一

#### Scenario: 执行耗时长短不改变循环语义
- **WHEN** 同一个循环 Worker 先后以"立即返回"与"明显慢于调度间隔"两种耗时各运行多轮
- **THEN** 两种情况下它都在每一轮被派发

#### Scenario: 循环标志不是可调用对象
- **WHEN** 读取任一 Worker 的循环标志
- **THEN** 返回一个布尔值而非可调用对象，且取值与配置声明的值一致

### Requirement: Worker 的执行状态 MUST 由单一收口维护

系统 SHALL 以单一位置维护 Worker 的"在飞"状态。登记 MUST 在派发之前完成，注销 MUST 在本次执行结束时发生。系统 MUST NOT 留下"执行已结束但状态未清除"的记录，MUST NOT 在清除状态后仍认为任务在运行。同一 Worker 的同一轮执行 MUST NOT 被登记两次。

#### Scenario: 执行结束后无残留
- **WHEN** 一个 Worker 完成一次执行
- **THEN** 其执行状态被清除，且下一轮调度会重新派发它

#### Scenario: 执行抛异常时仍被清除状态
- **WHEN** Worker 的执行抛出异常
- **THEN** 其执行状态仍被清除，下一轮调度会重新派发它

#### Scenario: 登记与派发之间无时序依赖
- **WHEN** 一个执行立即返回的 Worker 在资源池模式下被派发
- **THEN** 调度器不会因"执行先于登记结束"而永久停止派发该 Worker

#### Scenario: 长时间运行的 Worker 不被重复派发
- **WHEN** 一个执行时长远超调度间隔的 Worker 正在运行
- **THEN** 在它结束之前不会被再次派发

### Requirement: 超时 MUST 被观测并熔断，MUST NOT 声称已终止

系统 SHALL 支持为 Worker 声明执行超时，且 MUST NOT 要求执行体自身配合判定。判定为超时后，系统 MUST 记录该事件、MUST 将该 Worker 标记为不健康、MUST NOT 再次派发该 Worker。系统 MUST NOT 声称已终止或中断了仍在执行的 Worker。

#### Scenario: 未声明超时时长任务不被误伤
- **WHEN** Worker 未声明执行超时，其执行耗时较长
- **THEN** 该 Worker 正常完成，不被标记为超时

#### Scenario: 声明超时后按声明熔断
- **WHEN** Worker 声明了执行超时且实际耗时超过该值
- **THEN** 该事件被记录，该 Worker 被标记为不健康

#### Scenario: 熔断不阻塞后续调度轮次
- **WHEN** 一个 Worker 挂死不返回
- **THEN** 调度循环仍按声明间隔推进，其余 Worker 照常被派发

#### Scenario: 超时的 Worker 不再被派发
- **WHEN** 一个 Worker 已被判定为超时
- **THEN** 后续调度轮次不再派发它

### Requirement: 单个 Worker 的异常 MUST NOT 中断调度

系统 SHALL 隔离每个 Worker 的异常。任一 Worker 在执行或结果投递过程中抛出异常时，其余 Worker MUST 仍被正常调度，调度循环 MUST NOT 终止。

#### Scenario: Worker 抛异常时其余 Worker 仍被调度
- **WHEN** 调度列表中的一个 Worker 执行抛出异常
- **THEN** 其余 Worker 在同一轮及后续轮次中仍被正常派发

#### Scenario: 结果投递抛异常不终止调度
- **WHEN** Worker 结果的投递过程抛出异常
- **THEN** 调度循环继续推进，不因该异常终止

#### Scenario: 非法调度项被忽略而非抛出
- **WHEN** 调度列表中存在空项
- **THEN** 该轮调度正常完成，不抛出属性访问异常

### Requirement: Worker 结果 MUST 沿事件管道投递且可被按名过滤

系统 SHALL 在 Worker 执行结束后把结果投递到事件管道。结果 MUST 携带产生它的 Worker 标识，该标识 MUST 可用于筛选接收方。投递 MUST 在资源池模式与线程模式下都发生，且同一次执行的结果 MUST 恰好被投递一次。

#### Scenario: 资源池模式下结果被投递
- **WHEN** 以资源池模式调度一个 Worker，其执行返回结果
- **THEN** 订阅结果主题的接收方收到该结果

#### Scenario: 线程模式下结果被投递
- **WHEN** 以线程模式调度一个 Worker，其执行返回结果
- **THEN** 订阅结果主题的接收方收到该结果

#### Scenario: 同一次执行的结果恰好投递一次
- **WHEN** 一个 Worker 完成一次执行
- **THEN** 订阅结果主题的接收方恰好收到一次该结果

#### Scenario: 按 Worker 名筛选接收方
- **WHEN** 两个 Worker 各自完成执行，接收方按其中一个的名称筛选
- **THEN** 接收方只收到被筛选的那个 Worker 的结果

### Requirement: 停机 MUST 回收调度资源

系统 SHALL 提供显式停机入口。停机后 MUST NOT 再派发新的 Worker，MUST 回收调度所占用的线程资源，MUST 触发已注册 Worker 的销毁钩子。停机 MUST 可重复调用而不抛出异常。

#### Scenario: 停机后不再派发
- **WHEN** 停机入口被调用后再触发调度轮次
- **THEN** 没有 Worker 被执行

#### Scenario: 停机后线程资源被回收
- **WHEN** 停机入口被调用
- **THEN** 框架占用的工作线程被回收，线程数回落至构造前的水平

#### Scenario: 停机触发销毁钩子
- **WHEN** 停机入口被调用，且某 Worker 定义了销毁钩子
- **THEN** 该钩子被调用一次

#### Scenario: 停机可重复调用
- **WHEN** 停机入口被连续调用两次
- **THEN** 两次均不抛出异常

### Requirement: 运行期注册的 Worker MUST 进入调度

系统 SHALL 使在调度器启动之后注册的 Worker 参与后续调度轮次。

#### Scenario: 注册后下一轮被调度
- **WHEN** 调度器启动后注册一个 Worker，随后触发调度轮次
- **THEN** 该新增的 Worker 被执行

### Requirement: 未实现的调度模式 MUST NOT 被静默降级

系统 SHALL 区分已实现的与未实现的调度模式及运行策略。请求未实现的模式、或传入无法识别的策略名时，系统 MUST 明确拒绝并指明该输入不可用，MUST NOT 静默改用其他模式执行。未实现的模式常量 SHALL 在代码中显式标注其状态。

#### Scenario: 无法识别的运行策略被明确拒绝
- **WHEN** 以无法识别的运行策略名构造调度器
- **THEN** 构造被拒绝并指明该策略不可用，而非静默返回默认策略

#### Scenario: 请求未实现的调度模式被明确拒绝
- **WHEN** 请求一个尚未实现的调度模式
- **THEN** 该请求被拒绝并指明该模式不可用，而非静默按其他模式执行

#### Scenario: 未实现的常量被显式标注
- **WHEN** 查阅模式与运行策略常量的定义
- **THEN** 未实现的常量有显式的状态标注，已实现与未实现可被区分
