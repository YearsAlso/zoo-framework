# worker-scheduling 规格变更（fix-result-reactor-name-filter delta）

## MODIFIED Requirements

### Requirement: Worker 结果 MUST 沿事件管道投递且可被按名过滤

系统 SHALL 在 Worker 执行结束后把结果投递到事件管道。结果 MUST 携带产生它的 Worker 标识，
该标识 MUST 可用于筛选接收方。结果上的 Worker 标识 SHALL 同时给出两个身份：**带实例序号的
实例名**与**不带序号的注册名**；筛选入口 SHALL 按注册名匹配（调用方声明筛选时无法预知实例
序号），并 SHALL 继续接受精确的实例名。匹配 MUST 为**精确匹配**，MUST NOT 退化为前缀匹配
——以某个注册名筛选时，MUST NOT 收下仅以该名为前缀的其它 Worker 的结果。投递 MUST 在资源池
模式与线程模式下都发生，且同一次执行的结果 MUST 恰好被投递一次。

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

#### Scenario: 按注册名筛选命中带序号的实例

- **WHEN** 接收方以注册名（不带实例序号）筛选，且该 Worker 产生了带序号的结果
- **THEN** 接收方收到该结果

#### Scenario: 筛选不因前缀而误收

- **WHEN** 接收方以某个注册名筛选，另有一个以该注册名为前缀的 Worker 完成执行
- **THEN** 该前缀 Worker 的结果不被该接收方收到

#### Scenario: 不设筛选时收到全部结果

- **WHEN** 接收方未声明筛选条件
- **THEN** 它收到每一个 Worker 的结果
