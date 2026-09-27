## Purpose

定义以默认配置启动框架所依赖的 Worker 注册与实例化契约、注册到调度的生效性，以及 Worker 配置读取（含异步 Worker）与生命周期日志的契约。该能力确保框架管理器总能被成功构造，注册的 Worker 总能被调度，且配置读取路径不会在运行时抛出属性错误或返回与声明不符的取值。

## MODIFIED Requirements

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

## ADDED Requirements

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
