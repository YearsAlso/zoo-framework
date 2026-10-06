## Purpose（本变更新增条款）

状态写路径 effect 的执行原语（线程化、不依赖 greenlet）与其有界等待语义。

## ADDED Requirements

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
