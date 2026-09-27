# cli-scaffolding Specification

## Purpose

定义脚手架命令行工具定位产出目录的语义。该能力使工具在任意平台、任意启动方式下都把生成的文件写入正确的目录，而不依赖对进程启动路径的猜测。

## Requirements

### Requirement: 脚手架命令 MUST 依据工作目录结构定位产出目录

脚手架命令新增 Worker 文件时，产出目录 SHALL 依据当前工作目录的实际结构判定，MUST NOT 依赖进程的启动路径。当工作目录下存在源码目录时，产出 SHALL 落在该源码目录下的 Worker 目录；否则 SHALL 落在当前工作目录下的 Worker 目录。

#### Scenario: 工作目录下存在源码目录时产出到其中
- **WHEN** 在存在源码目录的项目根目录执行新增 Worker 命令
- **THEN** 生成的文件位于该源码目录下的 Worker 目录中

#### Scenario: 工作目录下不存在源码目录时产出到当前目录
- **WHEN** 在不含源码目录的位置执行新增 Worker 命令
- **THEN** 生成的文件位于当前工作目录下的 Worker 目录中

#### Scenario: 判定不依赖进程启动方式
- **WHEN** 以不同的方式启动该命令（可执行入口、模块方式、脚本方式），且工作目录结构相同
- **THEN** 三次生成的文件落在同一目录中

#### Scenario: 产出目录不存在时被创建
- **WHEN** 判定出的产出目录尚不存在
- **THEN** 该目录被创建，文件被成功写入

### Requirement: 新增 Worker 的名称 MUST 是合法标识符

命令行工具在接受一个 Worker 名称时 MUST 先校验该名称可作为 Python 标识符使用：不以数字开头、不含连字符与空白、不是 Python 关键字。校验不通过时命令 MUST 以非 0 退出码失败并指明原因，MUST NOT 产出任何文件。

名称校验 MUST 发生在产出之前，MUST NOT 依赖「生成后再检查」——产出不可解析的文件再报错，等于把恢复成本转嫁给调用方。

#### Scenario: 非法名称被拒绝
- **WHEN** 以一个含连字符的名称请求新增 Worker
- **THEN** 命令以非 0 退出码失败，且输出指明该名称非法

#### Scenario: 非法名称不产出任何文件
- **WHEN** 以一个以数字开头的名称请求新增 Worker
- **THEN** 工作目录下不产生新增的模块文件，且既有文件内容不变

#### Scenario: 合法名称被接受
- **WHEN** 以一个合法标识符名称请求新增 Worker
- **THEN** 命令成功，产出的模块与入口均可被解析

### Requirement: 产出操作无法完成时 MUST 明确失败并保持现场不变

当脚手架命令无法完成其被请求的产出时（目标已存在、目标路径不可创建），命令 MUST 以非 0 退出码失败并给出可读的原因。命令 MUST NOT 静默正常退出，MUST NOT 向调用方暴露未捕获的异常栈，且 MUST NOT 修改任何既有文件。

#### Scenario: 创建目标已存在时报错
- **WHEN** 对一个已存在的目录执行项目创建命令
- **THEN** 命令以非 0 退出码失败，并指明该目标已存在

#### Scenario: 创建目标已存在时不改动现场
- **WHEN** 对一个已存在且含内容的目录执行项目创建命令
- **THEN** 该目录下的所有文件内容与调用前完全一致

#### Scenario: 嵌套路径被正确创建
- **WHEN** 以一个父目录尚不存在的嵌套路径执行项目创建命令
- **THEN** 命令成功，父目录与目标目录均被创建

### Requirement: 一次调用中的创建项目与新增 Worker MUST 协同

当同一次调用同时请求创建项目与新增 Worker 时，新增的 Worker MUST 落在本次创建的项目内，且 MUST 被该项目的入口导入并注册。产出目录 MUST NOT 仅依据进程工作目录反推，否则会落到本次创建的项目之外。

#### Scenario: Worker 落入本次创建的项目
- **WHEN** 在同一次调用中同时请求创建项目与新增 Worker
- **THEN** 生成的 Worker 模块位于本次创建项目的 Worker 目录内

#### Scenario: Worker 被本次创建的入口注册
- **WHEN** 在同一次调用中同时请求创建项目与新增 Worker
- **THEN** 本次创建项目的入口文件中包含对该 Worker 的导入与注册条目

### Requirement: 重复新增同名 Worker MUST 幂等

对同一名称重复执行新增 Worker 时，入口文件 MUST NOT 累积重复内容。同一 Worker 的导入行与注册条目 MUST 各自只出现一次。

#### Scenario: 重复新增同名 Worker 不产生重复条目
- **WHEN** 对同一名称连续两次请求新增 Worker
- **THEN** 入口文件中该 Worker 的导入行与注册条目各只出现一次

#### Scenario: 重复新增同名 Worker 仍成功
- **WHEN** 对同一名称连续两次请求新增 Worker
- **THEN** 两次调用的退出码均为 0，第二次不因文件已存在而失败

#### Scenario: 不同名称的 Worker 互不影响
- **WHEN** 先后以两个不同名称请求新增 Worker
- **THEN** 入口文件中两个 Worker 的导入行与注册条目均存在，且各只出现一次
