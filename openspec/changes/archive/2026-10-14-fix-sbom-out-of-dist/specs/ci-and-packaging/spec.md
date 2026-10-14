## MODIFIED Requirements

### Requirement: 每次 release MUST 附带 SBOM 工件

release 工作流 SHALL 在构建后生成软件物料清单（SPDX-JSON）并作为 release
附件发布；生成失败时工作流 SHALL 失败（SHALL NOT 静默跳过）；SHALL NOT 改变
既有的签名与 PyPI 上传行为。

SBOM 的扫描目标 SHALL 是待发布分发包所在目录，但其**产物 MUST 落在该目录之外**、
MUST NOT 与待上传的分发包混放——上传工具会把 `packages-dir`（默认 `dist/`）下的每个
文件都当作分发包校验，非分发包文件混入会使整个上传中止。

#### Scenario: SBOM 生成并随附件发布

- **WHEN** release 工作流运行到构建之后
- **THEN** `dist-sbom/` 中出现 SBOM 文件
- **AND** `dist/` 中只有 wheel 与 sdist
- **AND** release 附件列表包含该 SBOM 文件

#### Scenario: 失败可见

- **WHEN** SBOM 生成步骤失败
- **THEN** 工作流以非零状态结束（不产出"看起来成功但没有 SBOM"的 release）
