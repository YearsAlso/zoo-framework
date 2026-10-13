## ADDED Requirements

### Requirement: 持久化失败 MUST 显式可感知

持久化无法完成时，系统 MUST 明确报错，MUST NOT 只记录一条日志、把失败留给被忽略的返回值。目标目录
不存在或不可写这类**必然且持续**的失败 MUST 在启动时被校验并当场失败（`start()`）；落盘失败时
`save()` MUST 抛出 `PersistenceError`，且 MUST NOT 清除脏标记（数据仍未落盘，须可重试）。成功的
落盘 MUST 返回成功信号；读盘在文件缺失时 MUST 仍优雅返回空值——读盘缺失是正常态，与写盘不可完成
分属不同语义。校验失败的错误信息 MUST 指明不可用的目录与配置键 `stateMachine:picklePath`。

#### Scenario: 目标目录不存在时落盘明确报错

- **WHEN** 目标文件的父目录不存在，且持久化调度器已有待落盘数据
- **THEN** `save()` 抛出 `PersistenceError`，错误信息含该目录，且脏标记仍为真、不留下半成品文件

#### Scenario: 启动时校验目标目录

- **WHEN** 以父目录不存在的路径启动持久化调度器
- **THEN** 启动当场失败并抛出 `PersistenceError`，而非进入后续每拍失败

#### Scenario: 目录可用时落盘照常成功

- **WHEN** 目标目录存在且可写
- **THEN** `save()` 返回成功信号、脏标记清零、文件落盘

#### Scenario: 读盘缺失文件仍优雅

- **WHEN** 目标文件不存在
- **THEN** `load()` 返回空值而不抛出异常
