## ADDED Requirements

### Requirement: 文档站构建 MUST 以严格模式作为门禁

文档站构建 SHALL 以严格模式运行（`mkdocs build --strict`）。任何构建告警——链接目标缺失、
进入 API 参考的签名缺类型注解等——MUST 使构建以非零状态结束，MUST NOT 出现"有告警但
构建成功"的中间态。

构建与部署 SHALL 分离：改动文档相关路径的 `dev` 推送、以及面向 `dev` 的拉取请求 SHALL
触发构建作业；部署作业 SHALL 只在 `main` 上执行，`dev` 与拉取请求的构建产物 MUST NOT
发布到站点。

#### Scenario: 存在死链时构建失败

- **WHEN** `docs/` 下存在指向 `docs_dir` 之外且站点上不可解析的相对链接
- **THEN** 文档站构建以非零状态结束

#### Scenario: 签名缺注解时构建失败

- **WHEN** 进入 API 参考的某个函数签名缺少参数或返回值注解
- **THEN** 文档站构建以非零状态结束

#### Scenario: dev 与拉取请求上构建但不部署

- **WHEN** 文档相关路径的改动被推送到 `dev`，或存在面向 `dev` 的拉取请求
- **THEN** 构建作业以严格模式运行，且部署作业不执行

#### Scenario: 只有 main 部署

- **WHEN** 严格构建在 `main` 上成功
- **THEN** 站点产物被发布到 GitHub Pages
