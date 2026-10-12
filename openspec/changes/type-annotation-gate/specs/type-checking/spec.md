## ADDED Requirements

### Requirement: 进入 API 参考的公开签名 MUST 带类型注解

被文档站 API 参考收录（`docs/api/*.md` 中的 `:::` 指令）的模块，其函数签名 SHALL 为参数
与返回值提供类型注解。`*args` / `**kwargs` 无固定类型时 SHALL 标注 `Any`，MUST NOT 留空。

已具备完整注解的模块 SHALL 在类型检查配置中逐模块开启"要求函数签名完整注解"，使后续新增
的缺注解定义被门禁拦截。

#### Scenario: 公开签名全部有注解

- **WHEN** 对进入 API 参考的模块执行严格模式的文档站构建
- **THEN** 不出现"缺少参数或返回值类型注解"的告警

#### Scenario: 已注解模块逐模块开启严格模式

- **WHEN** 读取 `pyproject.toml` 的类型检查覆盖配置
- **THEN** 除既有模块外，`zoo_framework.core.params_path` 与
  `zoo_framework.statemachine.state_effect_scheduler` 被单独要求函数签名完整注解

#### Scenario: 新增缺注解定义被拦截

- **WHEN** 在上述任一模块中新增一个无注解的函数定义并执行类型检查
- **THEN** 类型检查报告该定义缺注解并以非零状态结束
