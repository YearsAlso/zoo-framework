# worker-lifecycle / project-scaffolding Spec Delta — quiet-default-logs

## ADDED Requirements

（挂载于 `worker-lifecycle` 能力）

### Requirement: Worker 的每轮生命周期日志 MUST 为 debug 级别

Worker 单次执行的开始与结束日志 SHALL 使用 debug 级别记录，MUST NOT 在框架默认
日志级别下输出到控制台。使用 `log.level=debug` 配置时这些日志 MUST 重新可见。

#### Scenario: 默认级别下启停日志不可见
- **WHEN** 以默认配置启动框架并观察标准错误流
- **THEN** 不出现 `Worker is Start` / `Worker is Stop` 字样的行

#### Scenario: debug 级别下启停日志重新可见
- **WHEN** 把 `log.level` 配置为 `debug` 后启动框架
- **THEN** `Worker is Start` / `Worker is Stop` 字样的行按每轮执行出现

### Requirement: 未接通的监控子系统日志 MUST NOT 声称监控已生效

指标链路未接通期间，SVM 相关日志 MUST NOT 使用"监控已启动 / 已完成"之类的断言性
措辞；SHALL 使用如实表述（指明指标管道尚未接通、健康报告恒为零），并以 debug
级别记录。

#### Scenario: SVM 注册日志不含断言性措辞
- **WHEN** 检查框架源码中的 SVM 注册与启停日志文案
- **THEN** 不存在 `SVM monitoring started` / `SVM Worker setup completed` 之类的
  断言已生效的文案，且描述指标未接通的日记文案存在

### Requirement: 脚手架产出的配置默认日志级别 MUST 为 warning

（挂载于 `project-scaffolding` 能力）`--create` 产出的 `config.json` 中日志级别
SHALL 为 `warning`；诊断时用户 MUST 能通过配置 `log.level` 恢复更详细的级别。

#### Scenario: 脚手架配置的默认级别
- **WHEN** 执行 `--create` 并读取产出的 `config.json`
- **THEN** 日志级别的值为 `warning`

#### Scenario: 用户可恢复详细级别
- **WHEN** 把产出配置的 `log.level` 改回 `debug`
- **THEN** 框架以 debug 级别输出（不因默认值变更而失去诊断路径）
