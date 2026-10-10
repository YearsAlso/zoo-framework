# Spec Deltas: ci-and-packaging

## ADDED Requirements

### Requirement: 工作流 MUST 显式声明最小权限并钉住 action 版本

`permissions`：每个 workflow SHALL 在顶层显式声明权限，默认只读（`contents: read`
或 `read-all`）；需要写权限的作业 SHALL 只在作业级声明，SHALL NOT 在顶层放开写权限。

`uses`：每个 action 引用 SHALL 钉到 40 位 commit SHA，并以注释标注其语义化标签。
`@v4` 形式一律不合格——**"大部分钉了"不算通过**：只要存在一处 tag 引用，钉 SHA 这一项
即判定为未达成。这一条按"全做或不算做"执行，因为供应链攻击只需要一个未钉的引用。

#### Scenario: 每个工作流都声明顶层权限

- **WHEN** 遍历 `.github/workflows/*.yml`
- **THEN** 每个文件都有顶层 `permissions:` 块
- **AND** 顶层不含 `write`（写权限只出现在作业级）

#### Scenario: 所有 action 引用都钉在 commit SHA 上

- **WHEN** 抽取每个 workflow 中的 `uses:` 引用
- **THEN** 每个引用都指向 40 位十六进制 commit SHA
- **AND** 若在任一 workflow 里留下 `actions/checkout@v4` 这类 tag 引用，机械校验失败

#### Scenario: 写权限仅出现在确实需要写的作业

- **WHEN** 检查声明了作业级写权限的作业
- **THEN** 每处写权限都有其必要性（推分支/tag、上传 SARIF、签发 OIDC 令牌）
- **AND** 状态表如实记录这些作业级写权限是外部审计的剩余扣分项，而不是为刷分把它们删掉

### Requirement: 发布 MUST 走 OIDC 短期令牌并产出可核对来源

发布作业 SHALL 声明 `id-token: write`，SHALL NOT 依赖长期 token：向发布步骤传
`password:` 一律不合格。发布的产物 SHALL 附带可由外部核对的来源或签名（PyPI 上的
PEP 740 证明、`cosign` keyless 签名与证书、SPDX SBOM 三者至少其一）。

发布 SHALL 以测试与质量作业为前提（`needs` 链），SHALL NOT 出现"测试没过也发了版"。

#### Scenario: 发布作业声明 OIDC 权限

- **WHEN** 读取发布 workflow 的发布作业
- **THEN** 该作业声明了 `id-token: write`

#### Scenario: 不传长期 token

- **WHEN** 检查发布步骤的参数
- **THEN** 不传 `password`（长期 PyPI token 不是发布路径的一部分）
- **AND** 机械校验失败于任何把长期 token 接回发布步骤的改动

#### Scenario: 产物带签名与 SBOM

- **WHEN** 检查发布作业的步骤
- **THEN** 存在 SBOM 生成步骤（SPDX）
- **AND** 存在对 `dist/` 产物的 keyless 签名步骤

#### Scenario: 发布以测试与质量为前提

- **WHEN** 读取发布作业的 `needs`
- **THEN** 发布作业依赖测试与质量作业

### Requirement: 依赖漏洞状态 MUST 可复现地复核

依赖真源 SHALL 唯一：`pyproject.toml` 声明依赖、`uv.lock` 锁定版本。仓库内 SHALL NOT
再存在第二份手工维护的依赖清单（历史上 `requirements.txt` 与 `pyproject.toml` 长期漂移，
已删除）。

锁文件 SHALL 与 `pyproject.toml` 保持一致：声明的每个运行依赖 SHALL 能在 `uv.lock` 中
找到对应包条目。对锁定集合的漏洞扫描 SHALL 为 0 命中；复核所用命令 SHALL 记录在
`docs/security-supply-chain.md`，任何人不依赖 CI 也能复跑。

处置结论 SHALL 记入 `CHANGELOG.md` 的 Security 段。

#### Scenario: 不存在第二份依赖清单

- **WHEN** 检索仓库
- **THEN** 不存在 `requirements*.txt`
- **AND** 依赖只由 `pyproject.toml` + `uv.lock` 描述

#### Scenario: 锁文件与 pyproject 同源

- **WHEN** 读取 `pyproject.toml` 的 `dependencies`
- **THEN** 每个声明名都能在 `uv.lock` 的包条目里找到
- **AND** 新增运行依赖但未更新锁文件时机械校验失败

#### Scenario: 锁定集合扫描为零命中

- **WHEN** 对 `uv.lock` 描述的锁定集合执行漏洞扫描
- **THEN** 命中数为 0
- **AND** 复核命令记录在状态表中，可复跑得到同一结论

#### Scenario: 结论记入变更日志

- **WHEN** 读取 `CHANGELOG.md`
- **THEN** 存在 Security 段记录本次依赖漏洞状态复核的结论与钉 SHA 漏项修复
