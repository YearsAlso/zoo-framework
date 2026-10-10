# Spec Deltas: security-model

## ADDED Requirements

### Requirement: 支持版本声明 MUST 不随版本号漂移

`SECURITY.md` 的支持版本表 SHALL 用**相对表述**描述支持范围（"PyPI 上的最新发布"、
"最新 minor 线"、"更早的 minor 线"），SHALL NOT 写死任何**当前版本线**的字面量
——包括表内举例里的版本号：`0.9.x` 这类举例会随版本推进而变成假话。

唯一允许出现的版本字面量是固定边界 `1.0`（它不随时间变化）。

`SECURITY.md` SHALL NOT 包含 `pyproject.toml` 声明的当前版本串。中英两份支持表的
行数与逐行支持标记（✅ / ❌）顺序 SHALL 一致。

该约束 SHALL 由机械校验拦截，不依赖发布前的人工检查。

#### Scenario: 版本表不含会漂移的版本号

- **WHEN** 解析 `SECURITY.md` 两个语种的支持版本表
- **THEN** 去掉固定边界 `1.0` 后，表中不再出现任何 `数字.数字` 形式的版本字面量
- **AND** 若把示例改回 `0.9.x` / `0.8.x` 之类的写法，机械校验失败

#### Scenario: 当前版本号不出现在安全策略里

- **WHEN** 读取 `pyproject.toml` 的 `[project].version`
- **THEN** 该版本串不出现在 `SECURITY.md` 中
- **AND** 版本 bump 后无需改动 `SECURITY.md` 也能保持校验通过

#### Scenario: 中英支持范围一致

- **WHEN** 比对两个语种的支持表
- **THEN** 数据行数相同
- **AND** 逐行的 ✅ / ❌ 顺序相同

### Requirement: 使用者视角的安全模型文档 MUST 齐备且如实

`docs/SECURITY_MODEL.md` SHALL 存在并被文档站 nav 收录（使用者不必翻仓库才能找到它），
且 SHALL 覆盖四节：

1. 支持版本策略；
2. 漏洞报送渠道（与 `SECURITY.md` 同源，指向私密渠道而非公开 issue）；
3. 依赖策略——以**可核对**的事实陈述（运行依赖条数、无 broker、锁定集合的扫描结果）；
4. **未做的事**——至少三条，且 SHALL 明确包含"尚无第三方安全审计"与"默认分支上的
   加固尚未生效"两类事实。

该文档 SHALL NOT 声称做过实际没做的事；它给出的可验证事实 SHALL 能用仓库文件或公开
接口复核（例如运行依赖条数 SHALL 与 `pyproject.toml` 的 `dependencies` 条数一致）。

#### Scenario: 四节齐备且文档站可达

- **WHEN** 检查 `docs/SECURITY_MODEL.md` 与 `mkdocs.yml` 的 nav
- **THEN** 四节均存在
- **AND** nav 中存在指向该文件的条目

#### Scenario: 未做的事是具体条目而非空话

- **WHEN** 读取"未做的事"小节
- **THEN** 该小节至少有 3 条列表项
- **AND** 至少一条明写尚**未**做第三方安全审计
- **AND** 至少一条明写默认分支（`main`）上的供应链加固尚未生效，并指向跟踪 issue

#### Scenario: 依赖事实可用文件核对

- **WHEN** 文档声明运行依赖条数
- **THEN** 该数字等于 `pyproject.toml` 中 `[project].dependencies` 的条目数
- **AND** 增删运行依赖后，未同步更新文档即导致机械校验失败

### Requirement: 供应链加固状态 MUST 留档并区分分支生效范围

`docs/security-supply-chain.md` SHALL 为 #89–#95 的每一项给出：**结论**
（已落地 / 部分落地 / 未做）与**证据**（文件路径 + 关键行，或可复跑的命令）。

该文档 SHALL 显式区分「已在开发线落地」与「默认分支尚未生效」，SHALL NOT 把只在
`dev` 生效的加固写成"已生效"；每一项的生效范围 SHALL 在该表中可读出。

该文档 SHALL 记录外部审计的采样依据（Scorecard 的采样时间、被采样的 commit、总分）
与**剩余扣分项的原因**，使"分数低"不再需要靠猜。

#### Scenario: 每条结论都带证据

- **WHEN** 读取状态表
- **THEN** #89–#95 每一行都有非空的证据列
- **AND** 证据是可复核的定位（`.github/workflows/...:行号` 或可复跑的命令），而不是"已完成"式断言

#### Scenario: 生效范围被显式标注

- **WHEN** 检查只落在开发线的加固项
- **THEN** 该行标注了"默认分支尚未生效"并指向跟踪 issue
- **AND** 若把该项改写成"已生效"，机械校验失败

#### Scenario: 分数可追溯到被采样的提交

- **WHEN** 读取状态表中的外部审计结论
- **THEN** 给出采样时间、被采样 commit 与总分
- **AND** 给出剩余扣分项的原因（例如需要写权限的作业本身合法，不为刷分删掉）

#### Scenario: 依赖复核命令可复跑

- **WHEN** 读取状态表的依赖漏洞结论
- **THEN** 给出可复跑的命令（对锁定集合做漏洞扫描）
- **AND** 说明第二份依赖清单缺失或已删除的事实
