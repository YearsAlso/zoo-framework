# state-machine 规格变更（add-state-query-index-and-incremental-persistence delta）

## ADDED Requirements

### Requirement: 状态索引 MUST 提供带查询能力的默认实现

状态索引工厂 SHALL 内置一个默认实现，除既有的键前缀查找外，还支持**按节点值查询**（对节点值做谓词 / 关键词过滤），并 SHALL 可通过既有索引注册接缝按名选取。索引类型 SHALL 可由配置键 `stateMachine:indexType` 选择；该键未配置时 MUST 使用现状默认值 `"dict"`，选择行为与合入前一致；配置为未知类型名时 MUST 沿用既有的显式失败（`ValueError`）。查询在无匹配或索引为空时 MUST 返回空结果，MUST NOT 抛错。查询 MUST NOT 因并发写入而崩溃；其返回结果不要求强一致快照（弱一致可接受），此点 SHALL 在实现文档中明示。内核提供的该默认实现 MUST NOT 内置语义 / 向量检索——语义检索属上层或插件职责。该实现为纯 Python 数据结构，Windows / Linux / macOS 行为 MUST 一致。

#### Scenario: 内置索引可按节点值查询
- **WHEN** 向索引写入若干节点，其中部分节点值满足给定谓词，随后按该谓词查询
- **THEN** 返回的节点集合恰好是满足谓词的那些节点

#### Scenario: 未配置索引类型时为现状默认
- **WHEN** 未配置 `stateMachine:indexType` 并创建索引
- **THEN** 使用默认索引类型，键前缀查找等既有行为与合入前一致

#### Scenario: 未知索引类型显式失败
- **WHEN** 将 `stateMachine:indexType` 配置为未注册的类型名
- **THEN** 创建索引时抛出显式错误（`ValueError`），MUST NOT 静默回退到默认类型

#### Scenario: 无匹配返回空结果
- **WHEN** 在一个空索引或没有节点满足谓词的索引上执行查询
- **THEN** 返回空结果且不抛错

#### Scenario: 并发写入下查询不崩溃
- **WHEN** 在一个持续被并发写入的索引上执行查询
- **THEN** 查询调用返回结果或空结果，不抛出异常

### Requirement: 持久化 MUST 支持只写脏作用域与按作用域 TTL 淘汰

持久化 SHALL 支持"只写脏作用域"模式：当且仅当某作用域自上次落盘后被修改过，该作用域才被写入；未被修改的作用域 MUST NOT 被重写。该模式 SHALL 由配置键启用；未启用时 MUST 保持现状（整表落盘），行为与合入前一致。启用后按作用域与键查询读回的状态 MUST 与整表落盘等价。持久化 SHALL 支持按作用域 TTL 过期淘汰；TTL 未配置（默认）时 MUST NOT 淘汰任何作用域，行为与合入前一致。淘汰 MUST 幂等——重复淘汰同一已过期作用域不抛错；作用域被淘汰后按该作用域查询 MUST 返回空。TTL 的时间基准与进程重启后的语义 SHALL 在实现文档中明示。落盘的原子替换与显式失败语义 MUST 保持：写入失败 MUST 显式化（沿用 `PersistenceError`），MUST NOT 只留一条日志。上述落盘 / 替换语义在 Windows / Linux / macOS 上 MUST 一致成立。

#### Scenario: 未修改的作用域不被重写
- **WHEN** 启用增量持久化，修改作用域 A 后触发一次落盘，此时作用域 B 未被修改
- **THEN** 本次落盘只涉及 A，B 的持久化内容与上次落盘一致

#### Scenario: 增量落盘后读回与整表落盘等价
- **WHEN** 以增量模式写入若干作用域后，在新进程语境读回
- **THEN** 按作用域与键查询的结果与整表落盘模式下一致

#### Scenario: 未启用增量模式时行为与现状一致
- **WHEN** 未启用增量持久化并触发落盘
- **THEN** 整表被写出，行为与合入前一致

#### Scenario: 过期作用域被淘汰且幂等
- **WHEN** 配置 TTL 后某作用域超过存活时间，触发淘汰；随后再次对同一作用域触发淘汰
- **THEN** 该作用域被移除且按作用域查询返回空，重复淘汰不抛错

#### Scenario: 未配置 TTL 时不淘汰
- **WHEN** 未配置 TTL 并经过任意时长
- **THEN** 任何作用域都不被自动淘汰，行为与合入前一致

#### Scenario: 落盘失败显式化且跨平台一致
- **WHEN** 目标目录不可写导致落盘失败（在任一支持平台上）
- **THEN** 抛出显式 `PersistenceError`，MUST NOT 仅记录日志后静默返回
