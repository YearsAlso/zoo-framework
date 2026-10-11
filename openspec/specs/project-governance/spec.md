# project-governance Specification

## Purpose
本能力规定项目治理材料的最低标准：安全报送入口符合 RFC 9116 且与安全策略同源、治理文件不得编造项目不具备的事实、材料互相可达无失效链接，维护者职责与响应下界可预期。

## Requirements

### Requirement: 安全报送入口 MUST 符合 RFC 9116 且与 SECURITY.md 同源

仓库根 `.well-known/security.txt` SHALL 存在并至少含 `Contact`、`Expires`、
`Canonical`、`Policy`、`Preferred-Languages` 五个字段。

`Expires` SHALL 是一个**未来**日期，且距写入日不超过一年（RFC 9116 建议上限）。

`Contact` 列出的每一条渠道 SHALL 能在 `SECURITY.md` 中逐字找到；`Policy` SHALL
指向 `SECURITY.md`。`SECURITY.md` 增删报送渠道时，`security.txt` MUST 同步更新
（该一致性由机械校验拦，不靠人工记忆）。

#### Scenario: 必需字段齐备且未过期

- **WHEN** 读取仓库根 `.well-known/security.txt`
- **THEN** `Contact` / `Expires` / `Canonical` / `Policy` / `Preferred-Languages` 五个字段均存在
- **AND** `Expires` 可解析为日期且晚于校验当日
- **AND** `Expires` 距该文件写入日不超过 366 天

#### Scenario: 报送渠道与安全策略一致

- **WHEN** 比对 `security.txt` 的 `Contact` 与 `SECURITY.md` 的报送章节
- **THEN** `Contact` 里的每个邮箱地址与 URL 都出现在 `SECURITY.md` 中
- **AND** `Policy` 指向本仓 `SECURITY.md`
- **AND** 若把 `SECURITY.md` 中的邮箱改掉而 `security.txt` 未同步，机械校验失败

### Requirement: 治理文件 MUST NOT 编造项目不具备的事实

`GOVERNANCE.md`、`MAINTAINERS.md`、`ADOPTERS.md` SHALL 只陈述可核实的事实。

`GOVERNANCE.md` SHALL NOT 出现本项目不具备的治理机构（无技术委员会、无选举、
无章程）；它描述的维护者人数 SHALL 与 `MAINTAINERS.md` 的列表一致。

`ADOPTERS.md` SHALL NOT 编造使用者。每一条目 SHALL 属于下列两类之一，并显式标注：

- **可核实**——给出可外部核对的依据（仓库地址 + 依赖声明所在文件）；
- **不可核实**——明写"读者无法核实"并说明它不作为证据。

无第三方使用者时 SHALL 如实写出该结论（与 `docs/FAQ.md` 的口径一致），
空位 SHALL 写成邀请句而非留白。

#### Scenario: 治理结构如实描述

- **WHEN** 阅读 `GOVERNANCE.md`
- **THEN** 文中声明维护者人数与 `MAINTAINERS.md` 列出的维护者条数一致
- **AND** 不存在"技术委员会／TSC／选举／章程"等本项目不具备的机构描述
- **AND** 决策方式、成为共同维护者的路径、冲突解决方式、版本与破坏性变更承诺四项均有可执行描述

#### Scenario: 使用者条目可核实或如实标注

- **WHEN** 审阅 `ADOPTERS.md` 的每一条目
- **THEN** 该条目要么给出可核对的依据（仓库地址 + 依赖声明文件），要么标为不可核实并说明不作证据
- **AND** 若声称存在第三方使用者，机械校验会因"无依据条目"失败
- **AND** 文件按"使用者自荐 PR 加入"的结构组织，空位是邀请句

### Requirement: 治理材料 MUST 互相可达且无失效链接

`README.md` 与 `README.zh.md` SHALL 各含一个「治理与规范」小节，链到
`GOVERNANCE.md`、`MAINTAINERS.md`、`ADOPTERS.md`、`SECURITY.md`、
`CODE_OF_CONDUCT.md`、`CONTRIBUTING.md` 与 `.well-known/security.txt`。

两份 README 的小节 SHALL 保持同一组链接（路径一致，不出现只在一侧存在的条目）。

仓库内任何指向上述治理文件的相对链接 MUST 指向存在的文件——包括
`docs/FAQ.md` 中已有的 `ADOPTERS.md` 引用。

#### Scenario: 两份 README 都能点到全部治理文件

- **WHEN** 分别检查 `README.md` 与 `README.zh.md` 的治理小节
- **THEN** 两者都出现全部七个治理入口
- **AND** 两者列出的目标路径集合相同
- **AND** 每个目标路径在仓库中真实存在

#### Scenario: 既有引用不再悬空

- **WHEN** 校验仓库内指向 `GOVERNANCE.md` / `MAINTAINERS.md` / `ADOPTERS.md` 的引用
- **THEN** 每个被引用的文件都存在（`docs/FAQ.md` 的 `ADOPTERS.md` 引用由此解析）

### Requirement: MAINTAINERS MUST 给出职责分区与可预期的响应下界

`MAINTAINERS.md` SHALL 列出维护者与各类事项（至少安全、发布、文档）的负责人，
并为每类事项给出**响应时间下界**。

下界 SHALL 写成单人可兑现的目标（例如"issue 七天内首次回应"），SHALL NOT 写成
无条件保证；安全类下界 SHALL NOT 与 `SECURITY.md` 已声明的时限冲突
（确认 48 小时内、评估与修复时间线 7 天内）。

#### Scenario: 职责与响应下界齐备

- **WHEN** 阅读 `MAINTAINERS.md`
- **THEN** 安全、发布、文档三类事项各有明确的负责人条目
- **AND** 每类事项带有可预期的响应时间下界
- **AND** 安全类下界不宽于 `SECURITY.md` 的 48 小时确认 / 7 天评估
- **AND** 文中说明这些是单人项目下的尽力目标，而非保证

### Requirement: 行为准则 MUST 披露版本状态并给出独立于安全渠道的举报路由

`CODE_OF_CONDUCT.md` SHALL 声明其所依据的 Contributor Covenant 版本号，并如实
标注该版本相对官方最新版本的状态：若官方已发布更新版本，SHALL 写明"官方当前版本
为 vX"以及本仓仍依据旧版本的事实与迁移去向（跟踪 issue）。

举报路由 SHALL 与 `SECURITY.md` 的渠道**区分开**：CoC 举报走邮箱并约定
`[Code of Conduct]` 主题前缀，平台级骚扰 SHALL 指向 GitHub 自带的 Report abuse；
文件 SHALL 明说这两条路与安全漏洞报送不同。因本项目只有一位维护者，文件 SHALL
如实说明无法提供独立的第三方举报受理，并保留"维护者本人是报告对象时"的处置说明。

两个语种 SHALL 表述一致（同一邮箱、同一前缀约定、同一版本声明）。

#### Scenario: 版本状态如实披露

- **WHEN** 检查 `CODE_OF_CONDUCT.md` 的版本说明
- **THEN** 文中给出所依据的 Contributor Covenant 版本号
- **AND** 若该版本不是官方最新版本，文中写明官方最新版本号与迁移跟踪 issue 编号
- **AND** 不存在"已采用当前最新版本"这类与事实不符的表述

#### Scenario: 举报路由与安全渠道可辨

- **WHEN** 阅读 `CODE_OF_CONDUCT.md` 的举报章节
- **THEN** 给出邮箱地址与 `[Code of Conduct]` 主题前缀约定，且给出平台级骚扰的举报入口
- **AND** 文中说明该路由与安全漏洞报送（GitHub 私密安全通告优先）是两条不同的路径
- **AND** 不存在未替换的模板占位符（如 `[TODO]`、`[联系方式]`）
- **AND** 中英两份的邮箱、前缀与版本号一致
