# worker-lifecycle Specification

## Purpose

定义以默认配置启动框架所依赖的 Worker 注册与实例化契约，以及异步 Worker 的属性访问与生命周期日志契约。该能力确保框架管理器总能被成功构造，且 Worker 的配置读取路径不会在运行时抛出属性错误。

## Requirements

### Requirement: 框架管理器 MUST 能以默认配置构造

系统 SHALL 允许调用方以默认配置构造框架管理器，并自动完成默认 Worker 的注册与实例化。构造过程 MUST NOT 因 Worker 注册抛出类型错误。

#### Scenario: 默认配置构造成功
- **WHEN** 调用方以默认配置构造框架管理器
- **THEN** 构造成功并返回管理器实例，不抛出任何异常

#### Scenario: 默认 Worker 注册后可被枚举
- **WHEN** 框架管理器构造完成后枚举已注册的 Worker
- **THEN** 枚举结果至少包含状态机 Worker 与事件 Worker

#### Scenario: 构造过程可重复
- **WHEN** 先后两次以默认配置构造框架管理器
- **THEN** 两次均成功，不抛出异常

### Requirement: Worker 注册 MUST 接受可产出实例的 Worker 定义

注册 Worker 时，注册表 SHALL 接受任何能够产出 Worker 实例的定义形式（类或工厂函数），并 SHALL 支持延迟实例化——注册时不要求立即创建实例。对于不能产出 Worker 实例的输入，注册表 MUST 抛出 TypeError，且错误信息 SHALL 能够定位被拒绝的输入。注册完成后，该 Worker MUST 进入调度，MUST NOT 要求调用方额外执行装配步骤才能使其被调度。

#### Scenario: 注册 Worker 类并取用实例
- **WHEN** 向注册表注册一个 Worker 类，随后按名称取用
- **THEN** 返回该 Worker 的实例，不抛出异常

#### Scenario: 同一名称重复取用返回同一实例
- **WHEN** 对同一名称连续两次取用 Worker
- **THEN** 两次返回同一个实例

#### Scenario: 注册时不立即实例化
- **WHEN** 仅注册一个 Worker 类而不取用
- **THEN** 注册过程不抛出异常，且注册表可列出该名称

#### Scenario: 拒绝不可产出 Worker 的输入
- **WHEN** 向注册表注册一个不能产出 Worker 实例的对象
- **THEN** 抛出 TypeError，且错误信息包含被拒绝输入的标识

#### Scenario: 注册后无需额外装配即可被调度
- **WHEN** 在框架管理器已构造之后注册一个 Worker，随后触发调度轮次
- **THEN** 该 Worker 被执行，调用方未额外执行装配步骤

### Requirement: 异步 Worker MUST 以属性字典承载配置

异步 Worker 的配置 SHALL 通过属性字典传入。其名称、循环标志与延迟时间的读取 MUST 始终返回配置值或既定默认值，MUST NOT 抛出 AttributeError。

#### Scenario: 读取异步 Worker 的名称
- **WHEN** 以名称为参数构造异步 Worker，并读取其名称
- **THEN** 返回的名称包含传入的名称，不抛出 AttributeError

#### Scenario: 未传名称时读取异步 Worker 的名称
- **WHEN** 不传名称构造异步 Worker，并读取其名称
- **THEN** 返回非空名称，不抛出 AttributeError

#### Scenario: 读取异步 Worker 的循环标志
- **WHEN** 未显式开启循环时读取异步 Worker 的循环标志
- **THEN** 返回假值，不抛出 AttributeError

### Requirement: 异步 Worker 的生命周期日志 MUST 可安全执行

异步 Worker 的初始化、销毁与同步执行入口 SHALL 能在日志输出中引用该 Worker 自身的名称，MUST NOT 因名称属性缺失而抛出 AttributeError。

#### Scenario: 异步初始化成功
- **WHEN** 在事件循环中执行异步 Worker 的异步初始化
- **THEN** 初始化成功完成，不抛出 AttributeError

#### Scenario: 异步销毁成功
- **WHEN** 在事件循环中执行异步 Worker 的异步销毁
- **THEN** 销毁成功完成，不抛出 AttributeError

#### Scenario: 同步执行入口的日志路径可用
- **WHEN** 调用异步 Worker 的同步执行入口以触发其日志输出
- **THEN** 日志输出成功引用 Worker 名称，不抛出 AttributeError

### Requirement: Worker 的循环标志 MUST 以属性形式暴露

Worker 的循环标志 SHALL 以属性形式暴露，读取时 MUST NOT 需要调用语法。承载配置的字典 SHALL 是该标志的唯一真源；其取值 MUST NOT 取决于子类是否恰好以实例属性遮蔽了同名成员。

#### Scenario: 循环标志以属性形式可读
- **WHEN** 读取任一 Worker 的循环标志
- **THEN** 返回布尔值，该值不是可调用对象

#### Scenario: 配置为真时循环标志为真
- **WHEN** 构造一个配置中声明循环的 Worker，并读取其循环标志
- **THEN** 返回真值

#### Scenario: 配置为假时循环标志为假
- **WHEN** 构造一个配置中声明不循环的 Worker，并读取其循环标志
- **THEN** 返回假值

#### Scenario: 配置缺省时循环标志为假
- **WHEN** 构造一个配置中未声明循环标志的 Worker，并读取其循环标志
- **THEN** 返回假值

#### Scenario: 配置字典是唯一真源
- **WHEN** 一个未以实例属性遮蔽该标志的子类被读取循环标志
- **THEN** 返回值与配置字典中声明的值一致，而非恒定的真值

### Requirement: 公共导出面 MUST 与实际注册/派发路径一致

框架公共包（`zoo_framework.core` 与 `zoo_framework.core.aop`）导出的每一项注册面/装饰器 MUST 接通真实的注册或派发路径——导出 MUST NOT 意味着"调用后静默不生效"。已判定不提供的注册途径 MUST NOT 出现在 `__all__` 中；其遗留导入路径在被使用时 MUST 发出弃用警告，MUST NOT 静默按旧语义写入无人读取的表。

#### Scenario: 导出的装饰器都能被有效使用

- **WHEN** 逐项取用 `core.__all__` 与 `core.aop.__all__` 中的注册面/装饰器并按其文档语义使用
- **THEN** 每一项的效果都能被框架的真实路径观察到（被派发、被解析、被注册），不存在"调用成功但无任何效果"的项

#### Scenario: 已判废的注册面不再被导出

- **WHEN** 检查 `core.__all__`、`core.aop.__all__` 与 `core.worker_registry.__all__`
- **THEN** 其中不含 `worker`、`worker_register`、`validation`、`validation_params`、`register_worker`（装饰器）这些已判废项

#### Scenario: 遗留导入路径发弃用警告

- **WHEN** 使用者从模块路径直接导入并调用 `@worker(...)`
- **THEN** 触发 `DeprecationWarning` 指明该注册面不接通调度，而不是静默注册进不被派发读取的表

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
