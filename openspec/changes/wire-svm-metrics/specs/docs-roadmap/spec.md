## MODIFIED Requirements

### Requirement: ROADMAP 与既有文档口径一致

`docs/contributing/roadmap.md` SHALL NOT 与 README、`docs/benchmark.md` 各自声明的
事实冲突，包括但不限于：健康监控 statement 须与 README 特性表同一口径（指标链路已接通
即如实陈述为可用，MUST NOT 再把已接通能力留在 Later 或标注为未接通）；性能声明 SHALL 以
zoo-bench / `docs/benchmark.md` 为证据来源；版本门槛 SHALL 与 `pyproject.toml` 的
`requires-python` 一致。

已立项（Next）条目 SHALL 携带对应的 issue 链接。

#### Scenario: 与 README 限制表一致

- **WHEN** roadmap 页陈述健康监控（SVM）相关能力
- **THEN** 与 `README.md` 特性表同一口径（指标链路已接通、该行不再是 ⚠️）
- **AND** 页内无"生产就绪（已验证）"式无公开证据的绝对化评级

#### Scenario: 已立项条目互链 issue

- **WHEN** 审阅 roadmap 的 Next（已立项）条目
- **THEN** 与指标接缝 / 观测导出相关的条目带有对应 issue 链接（如 #246）

#### Scenario: 证据来源锚定

- **WHEN** roadmap 页引用性能或基准数据
- **THEN** 指向 zoo-bench 仓库或 `docs/benchmark.md`，不使用内部项目作为公开证据
