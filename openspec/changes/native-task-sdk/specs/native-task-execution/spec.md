## ADDED Requirements

### Requirement: 原生任务契约 MUST 公开且可机械校验

原生任务的契约 SHALL 以仓库内文档的形式对第三方公开：四个入口的形状、三族错误的语义边界、
panic 纪律、执行纪律与契约演进规则 MUST 各自成文，且 SHALL NOT 只存在于实现注释里。

仓库 SHALL 提供一个可编译的最小任务模板，模板自身的 `cargo test` MUST 通过——第三方照抄的
起点不能自己就是坏的。

仓库 SHALL 提供一个可运行的契约校验器：它 MUST 能对满足契约的 crate 报通过、对违反任一
条纪律的 crate 报出具体违规项并以非零状态结束。校验器 SHALL 被纳入原生扩展的持续集成。

文档 SHALL 给出「该不该下沉」的判断表，且表中每条判定 MUST 附仓库自身的实测数字作为依据，
MUST NOT 以未测量的性能预测充当依据。

#### Scenario: 模板开箱可用

- **WHEN** 复制模板目录并执行其 `cargo test`
- **THEN** 测试全部通过

#### Scenario: 校验器接受合规 crate

- **WHEN** 对满足契约的 crate 运行校验器
- **THEN** 输出通过信息且退出码为零

#### Scenario: 校验器拒绝违规 crate

- **WHEN** 对一个契约版本号与框架不一致的 crate 运行校验器
- **THEN** 输出指名该违规项的信息，且退出码非零

#### Scenario: 判断表有实测依据

- **WHEN** 阅读「该不该下沉」判断表
- **THEN** 每条判定都能追溯到仓库内留档的实测数字
