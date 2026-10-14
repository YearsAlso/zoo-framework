# worker-scheduling 规格变更（fix-worker-failure-result delta）

## ADDED Requirements

### Requirement: Worker 执行失败 MUST 产生可区分的结果事件

Worker 的执行体抛出异常时，系统 SHALL 仍然把这次执行的结果投递到统一结果主题，
MUST NOT 只把失败留在日志里。该结果 MUST 携带可判定的失败标记与错误信息，使订阅结果
主题的消费者能够把"执行失败"与"仍在执行"区分开。失败结果 MUST NOT 以成功结果的形态
投递——既 MUST NOT 缺少失败标记，也 MUST NOT 用"内容为空的成功结果"代替失败。
失败之后该 Worker 的结算 MUST 是确定的：其执行状态 MUST 被清除，MUST NOT 因失败而
永久停留在"在飞"状态。执行失败的 Worker 仍 SHALL 触发其错误与完成钩子。

#### Scenario: 失败的 Worker 在结果主题上留下恰好一条可区分的结果

- **WHEN** 一个 Worker 的执行体抛出异常，且接收方订阅统一结果主题
- **THEN** 接收方收到恰好一条该 Worker 的结果，该结果携带错误信息，且与成功结果可区分

#### Scenario: 失败不被伪装成成功空结果

- **WHEN** 消费者收到一条执行失败的结果
- **THEN** 该结果的失败标记为真且错误信息非空，消费者不会把它当成一次成功的空产出

#### Scenario: 成功的 Worker 结果不携带失败标记

- **WHEN** 一个 Worker 的执行体正常返回
- **THEN** 其结果的失败标记为假，内容为执行体的返回值

#### Scenario: 失败后不残留执行状态

- **WHEN** 一个 Worker 的执行体抛出异常并产生失败结果
- **THEN** 该 Worker 的执行状态被清除，后续调度轮次按其循环标志决定是否重新派发
