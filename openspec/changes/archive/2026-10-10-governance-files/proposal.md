# 提案：governance-files

## Why

外部评估者与认证体系（OpenSSF Best Practices / CII-Best-Practices 徽章，issue #95）
最先检查的治理材料，本仓库一份都没有：`GOVERNANCE.md`、`MAINTAINERS.md`、
`ADOPTERS.md`、`.well-known/security.txt` 全部不存在（实测 `gh api .../contents/<f>`
对四者均返回 404）。没有这些文件，#95 的徽章申请会在问卷阶段卡住——问卷会直接问
"项目如何决策""谁是维护者""有没有使用者"，答不上来就拿不到分。

同时，`docs/FAQ.md` 已经写下了"目前没有可核实的外部使用者……欢迎提 PR 加入
`ADOPTERS.md`"，链接指向一个不存在的文件；`README.md` / `README.zh.md` 的
「社区与反馈」小节列了 SECURITY.md 与 CODE_OF_CONDUCT.md，却没有治理类材料的入口。
即：口径已经诚实，只是承载这些口径的文件缺席。

## What Changes

- **新增 `.well-known/security.txt`**（RFC 9116）：`Contact`（沿用 SECURITY.md 的两条
  渠道）、`Expires`（未来日期，≤1 年）、`Canonical`、`Policy`、`Preferred-Languages`。
  与 `SECURITY.md` 的报送渠道**逐字一致**。
- **让它在 GitHub Pages 上真正可达**：新增 `scripts/mkdocs_hooks.py`（`on_post_build`
  把仓库根 `.well-known/` 复制进 `site/`），`mkdocs.yml` 声明 `hooks:`，
  `docs.yml` 的触发路径补 `.well-known/**`。
  > 实测结论：mkdocs 会**忽略点开头的目录**——在 `docs/.well-known/` 放探针文件后
  > 构建，`site/probe-plain.txt` 存在而 `site/.well-known/` 不存在。因此 issue #120
  > 里"把文件同时放到 `docs/.well-known/`"按字面实施**不会**使它在 Pages 上可达，
  > 本变更改用构建钩子实现同一意图。
- **新增 `GOVERNANCE.md`**：如实描述单人维护现状（决策方式、如何成为共同维护者、
  冲突解决、版本与破坏性变更承诺），SHALL NOT 出现"由 TSC 管理"式模板文字。
- **新增 `MAINTAINERS.md`**：维护者列表 + 安全／发布／文档三类事项的负责人 +
  可预期的响应时间下界（写成单人可兑现的目标，而非承诺）。
- **新增 `ADOPTERS.md`**：结构为邀请句 + 真实条目。SHALL NOT 编造使用者；
  "维护者私有项目"标注**不可核实**，"zoo-code-agent"标注**可核实但属维护者自己的
  消费者**（其 `pyproject.toml` 声明 `zoo-framework==0.8.0`，可外部核对）。
- **核对 `CODE_OF_CONDUCT.md` 并补齐举报路由**：核对结果是**不是当前版本**——官方仓
  `EthicalSource/contributor_covenant`（默认分支 `release`，2026-05 仍在更新）已发布
  **v3.0**（含官方 zh-cn 译文），本仓为基于 v2.1 的精简改写版。本变更**不**迁移版本，
  而是在 CoC 顶部如实披露版本状态并链到迁移 issue（另开跟踪），同时补齐举报路由——
  沿用同一邮箱但以 `[Code of Conduct]` 主题前缀分流，平台级骚扰指向 GitHub 自带的
  Report abuse，文中明说它与安全渠道是两条路。
- **README（中英双份）新增「治理与规范」小节**，链到上述全部文件。

## Capabilities

### New Capabilities

- `project-governance`: 治理与可信度材料的**内容约束**——诚实性（不得编造维护者
  结构或使用者）、`security.txt` 字段与渠道一致性、治理文件互相引用不失效、
  README 可点到全部治理文件、行为准则的版本披露与举报渠道。

### Modified Capabilities

- `ci-and-packaging`: 新增"文档站产物 MUST 含 `.well-known/security.txt`"的
  要求——构建钩子的存在性、复制结果、以及工作流触发路径覆盖该文件
  （否则单独改 `Expires` 不会重新发布）。

## Impact

- **新增文件**：`.well-known/security.txt`、`GOVERNANCE.md`、`MAINTAINERS.md`、
  `ADOPTERS.md`、`scripts/mkdocs_hooks.py`、`tests/test_governance_consistency.py`
  （把验收项"引用一致 / 无失效链接 / 渠道一致 / `Expires` 未过期"变成 CI 能拦的断言）。
- **修改文件**：`mkdocs.yml`（`hooks:` + 注释）、`.github/workflows/docs.yml`
  （触发路径）、`README.md` 与 `README.zh.md`（治理小节）、`CODE_OF_CONDUCT.md`
  （版本披露与举报路由）。
- **另开 issue**：CoC 迁移到 Contributor Covenant 3.0（本变更只披露不迁移）。
- **不触碰**：`SECURITY.md` 的政策文本（渠道不变，只是被 `security.txt` 引用）、
  `zoo_framework/` 代码、`pyproject.toml` 依赖、发布工作流。
- **风险**：`docs.yml` 只在推 `main` 时构建并部署 Pages，因此镜像在 dev→main
  合并后才可达；本地构建可先行验证产物路径。
- 依赖外部事实：`zoo-code-agent` 的依赖声明（已验证）、Contributor Covenant
  当前版本（以官方站点为准）。
