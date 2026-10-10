# Spec Deltas: packaging-standards

## ADDED Requirements

### Requirement: 许可证元数据 MUST 用 SPDX 表达式声明

`pyproject.toml` SHALL 以 PEP 639 的 SPDX 表达式声明许可证
（`license = "Apache-2.0"`）并用 `license-files` 列出许可证文件；
SHALL NOT 保留 PEP 639 已弃用的 `License :: OSI Approved :: ...` classifier。
`[build-system].requires` SHALL 声明支持 PEP 639 的最低构建后端版本，
使旧后端不会静默产出不符合规范的元数据。

#### Scenario: 声明形式与弃用 classifier

- **WHEN** 读取 `pyproject.toml`
- **THEN** `[project].license` 是 SPDX 表达式字符串且 `license-files` 指向 `LICENSE`
- **AND** `[project].classifiers` 中不存在以 `License ::` 开头的条目
- **AND** `[build-system].requires` 有支持 PEP 639 的最低版本下限

#### Scenario: 构建产物含机器可读许可证

- **WHEN** 构建 wheel 并检查其 `METADATA`
- **THEN** 元数据含 SPDX 许可证表达式与许可证文件条目（如
  `License-Expression: Apache-2.0` 与 `License-File: LICENSE`）
- **AND** 不再只有旧的自由文本 `License:` 字段

### Requirement: 构建与安装 MUST 以真实执行验证

打包元数据变更 SHALL 以真实构建与安装验证，SHALL NOT 仅凭静态检查宣称通过。

#### Scenario: 构建与 twine 校验

- **WHEN** 在仓库根执行 `python -m build`
- **THEN** 产出 sdist 与 wheel 且退出码为 0
- **AND** `twine check dist/*` 对所有产物输出 `PASSED`

#### Scenario: 安装产物可用

- **WHEN** 在干净环境安装构建出的 wheel
- **THEN** `import zoo_framework` 成功
- **AND** 命令行入口（`zfc --help`）可执行

### Requirement: CITATION.cff MUST 存在且版本与真源一致

仓库根 SHALL 提供 CFF 1.2.0 的 `CITATION.cff`，含 `authors`、`title`、`version`、
`license`、`repository-code`、`abstract`；其 `version` SHALL 与
`pyproject.toml` 的版本一致，SHALL 纳入 release 的版本更新步骤（否则即产生
"版本声明漂移"）。校验方式（`cffconvert --validate` 或退化为结构化校验）SHALL
在变更记录中说明。

#### Scenario: 字段完整且与 pyproject 同源

- **WHEN** 解析 `CITATION.cff`
- **THEN** 六个必备字段齐全且 `version` 等于 `pyproject.toml` 的版本
- **AND** 校验结果（工具校验通过，或结构化校验的逐项结论）被记录

#### Scenario: 版本更新不遗漏 CITATION

- **WHEN** release 工作流执行版本更新步骤
- **THEN** `CITATION.cff` 的 `version` 与其它版本声明一起被改写
- **AND** 任一版本声明未被写入新版本号时该步骤失败（不允许开出错的 PR）

### Requirement: 每次 release MUST 附带 SBOM 工件

release 工作流 SHALL 在构建后生成软件物料清单（SPDX-JSON）并作为 release
附件发布；生成失败时工作流 SHALL 失败（SHALL NOT 静默跳过）；SHALL NOT 改变
既有的签名与 PyPI 上传行为。

#### Scenario: SBOM 生成并随附件发布

- **WHEN** release 工作流运行到构建之后
- **THEN** `dist/` 中出现 SBOM 文件
- **AND** release 附件列表包含该 SBOM 文件

#### Scenario: 失败可见

- **WHEN** SBOM 生成步骤失败
- **THEN** 工作流以非零状态结束（不产出"看起来成功但没有 SBOM"的 release）

### Requirement: 打包元数据 MUST 与单一真源保持一致

`pyproject.toml` 的 `keywords`、`classifiers`、`project.urls` SHALL 与
`docs/REPO_METADATA.md` 的投影区保持一致；`readme` 的内容类型声明方式与
`[project.optional-dependencies]` 分组取舍 SHALL 在 design 中说明理由。

#### Scenario: 投影一致

- **WHEN** 比对 `docs/REPO_METADATA.md` 的必需项与 `pyproject.toml` 实际值
- **THEN** 两者逐项一致，无"文档要求含而实现缺失"的条目

#### Scenario: 取舍有记录

- **WHEN** 审阅 design.md
- **THEN** `readme` content-type、urls 齐备性、optional-dependencies 分组三项
  均有明确结论（改或明确不改，附理由）
