## REMOVED Requirements

### Requirement: 未接通的监控子系统日志 MUST NOT 声称监控已生效

**Reason**: 指标链路已接通，该 Requirement 的前提（"指标链路未接通期间"）不再成立——
它要求"如实标注未接通"，而实况已是接通，继续保留会把过期口径当成契约。

**Migration**: 由本变更新增的「监控子系统的日志 MUST 与指标链路的接通状态一致」取代：
日志仍须如实，但如实的方向由"标注未接通"改为"与当前接通状态一致"。

## ADDED Requirements

### Requirement: 监控子系统的日志 MUST 与指标链路的接通状态一致

SVM 相关日志 SHALL 如实描述指标链路的**当前**接通状态：链路接通后 MUST NOT 再以
"指标未接通 / 恒为零"之类与实况不符的措辞描述它；MUST NOT 复活历史的不实宣称字样
（如 `SVM monitoring started`）；MUST NOT 声称未实现的监控能力。日志级别 SHALL 为 debug。

#### Scenario: 接通后日志不再声称未接通

- **WHEN** 检查框架源码中的 SVM 注册与启停日志文案
- **THEN** 不存在 "metrics input not wired" / "get_health_report() returns zeros"
  之类与实况不符的措辞
- **AND** 不存在 `SVM monitoring started` 这类历史不实宣称字样

### Requirement: 执行事实 MUST 经可注册的观察接缝生产

内核 SHALL 在**唯一的结算收口**处为每次执行产出一条**不可变**的执行事实（含 Worker 身份、
本次耗时、成功或失败）。事实的**去向由消费者决定**：消费者 SHALL 能一次性注册观察回调接收
事实，并能注销该回调；内核 MUST NOT 内置任何具体的指标消费者或导出目标。

未注册任何观察回调时，接缝 SHALL 为空操作：调度、结果投递与既有行为 MUST 与没有该接缝时
逐项一致。注销后的回调 MUST NOT 再被调用。

#### Scenario: 注册后收到每次执行的事实

- **WHEN** 注册一个观察回调并让若干 Worker 完成执行
- **THEN** 回调为每次完成收到一条事实，其 Worker 身份与本次执行对应
- **AND** 其中失败的一次执行所对应的事实标记为失败

#### Scenario: 未注册观察者时行为不变

- **WHEN** 不注册任何观察回调，正常调度并完成若干次执行
- **THEN** 调度与结果投递行为与未引入接缝时一致，不抛出异常

#### Scenario: 注销后不再收到事实

- **WHEN** 先注册一个观察回调、确认其收到过事实，随后注销该回调
- **THEN** 注册期间确实收到过事实（非空前置）
- **AND** 注销之后该回调不再被调用

### Requirement: 健康报告 MUST 反映真实执行事实

`get_health_report()` SHALL 返回由**真实执行事实**累加出的 `execute_count` / `error_count`
与健康判据，MUST NOT 恒返回零。未发生过执行时计数 SHALL 如实为零，MUST NOT 编造非零值。

#### Scenario: 真实调度下执行计数非零

- **WHEN** 在真实调度下让已注册的 Worker 完成至少一次执行后查询健康报告
- **THEN** 对应 Worker 的 `execute_count` 为非零，且与实际完成次数一致

#### Scenario: 失败执行计入错误计数

- **WHEN** 一个 Worker 的执行体抛出异常并结算后查询健康报告
- **THEN** 该 Worker 的 `error_count` 计入该次失败（成功执行不计入错误计数）
