## Purpose（本变更新增条款）

公共导出面与实际注册/派发路径的一致性：导出了但不生效的项不得存在。

## ADDED Requirements

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
