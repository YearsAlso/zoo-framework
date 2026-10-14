## REMOVED Requirements

### Requirement: 健康监控的宣称 MUST 如实标注指标链路状态

**Reason**: 指标链路已接通（`get_health_report()` 返回真实执行计数）。该 Requirement 要求
在每一处能力宣称处标注"指标链路尚未接通 / 恒为 0"，与实况相反。

**Migration**: 由本变更新增的「健康监控的宣称 MUST 与运行实况一致」取代：仍要求如实，但
方向反转为"不得再把已接通的能力标注为未接通"。

## ADDED Requirements

### Requirement: 健康监控的宣称 MUST 与运行实况一致

`get_health_report()` 的指标输入链路 SHALL 已接通（返回真实执行计数）。文档中每一处宣称
"SVM 健康监控"能力的地方 SHALL 与运行实况一致：MUST NOT 再把已接通的能力标注为
"尚未接通 / 恒为 0"；MUST NOT 出现"自动故障检测"级**超出实现**的宣称；运行时日志 MUST NOT
输出 `SVM monitoring started` 这类历史不实字样。

#### Scenario: 已接通能力不再被标注为未接通

- **WHEN** 全库文档被扫描"SVM 健康监控能力宣称处"
- **THEN** 不存在"指标链路尚未接通 / `get_health_report()` 恒为 0"级别的过期标注

#### Scenario: 废弃宣称词不得回归

- **WHEN** 全库文档与运行时日志源码被扫描
- **THEN** `SVM monitoring started` 这类历史不实宣称字样出现次数为 0
