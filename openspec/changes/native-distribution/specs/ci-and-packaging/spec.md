## ADDED Requirements

### Requirement: 原生扩展 MUST 由 CI 构建、测试并发布

仓库内 `native/` 的原生扩展 SHALL 具备持续集成覆盖：`cargo test` SHALL 在 Linux、macOS、
Windows 三平台运行；构建出的扩展 SHALL 被安装到 Python 环境并执行原生相关的 pytest 路径。

发布的 wheel SHALL 通过 abi3 覆盖多个 Python 版本，SHALL NOT 以「每个 Python 版本各发
一份」的方式交付。启用 abi3 时，扩展自身的 Python 下界 SHALL 同步降到 abi3 覆盖的下界，
MUST NOT 让下界把 abi3 覆盖的版本挡在门外。

发布 SHALL 走 OIDC 短期令牌（trusted publishing），MUST NOT 依赖长期令牌。发布流程 SHALL
是幂等的：目标版本已存在于索引时 SHALL 跳过上传，而不是让工作流失败。

发布 MUST NOT 只发出部分产物：构建出的每一份 wheel SHALL 全部进入待发布集合，集合收不全
时发布 SHALL 失败并给出缺失数量，MUST NOT 静默发出残缺的一份。该约束 SHALL 由产物侧的
实际登记数保证，MUST NOT 依赖手工维护的平台清单或数量常量——清单会随构建矩阵漂移，
而「少了」与「做对了」在漂移后不可区分。同一约束 MUST NOT 在版本已存在（幂等跳过）时
误报为失败。

扩展为可选安装：主包 SHALL 以可选附加的形式暴露安装入口，MUST NOT 默认捆绑原生扩展，
MUST NOT 因未安装扩展而改变既有纯 Python 行为。

#### Scenario: 三平台原生测试

- **WHEN** 改动 `native/` 的提交触发原生工作流
- **THEN** `cargo test` 在三个平台上运行且通过
- **AND** 安装构建出的扩展后，原生 pytest 路径通过

#### Scenario: 同一 wheel 覆盖多个 Python 版本

- **WHEN** 原生工作流构建出 wheel
- **THEN** wheel 文件名带 abi3 标记
- **AND** 同一个 wheel 产物在至少两个 Python 版本上安装并加载成功

#### Scenario: 下界不得吃掉 abi3 的收益

- **WHEN** 检查扩展的元数据
- **THEN** `requires-python` 不高于 abi3 目标版本所覆盖的下界

#### Scenario: 可选附加而非默认捆绑

- **WHEN** 用户安装主包且未选择原生附加
- **THEN** 安装过程中不出现 Rust 工具链或原生构建步骤
- **AND** 请求原生能力时框架显式报错，不静默回退为纯 Python 实现

#### Scenario: 重复发布被跳过

- **WHEN** 目标版本已存在于索引
- **THEN** 发布步骤跳过上传且工作流不失败

#### Scenario: 每个构建平台的 wheel 都进入索引

- **WHEN** 一次真实 tag 触发的发布完成
- **THEN** 索引上该版本下存在与构建作业数量相同的 wheel，平台标签各不相同

#### Scenario: 产物收不全时拒绝发布

- **WHEN** 待发布集合中缺少某个构建作业产出的 wheel
- **THEN** 发布步骤失败并报出集合内数量与产物登记数量的差异
- **AND** 该版本在索引上不新增任何文件
