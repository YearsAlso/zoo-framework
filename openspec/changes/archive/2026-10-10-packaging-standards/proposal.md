# 提案：packaging-standards —— PEP 639 许可证写法、CITATION.cff 与 SBOM

对应 issue：YearsAlso/zoo-framework#119（P1，standards）

## Why（为什么做）

打包元数据有三处不符合当前 Python 打包规范，削弱下游工具与合规扫描器的
**机器可读**识别能力：

1. **许可证是 PEP 639 之前的写法**：`pyproject.toml:10` 写着
   `license = {text = "Apache-2.0"}`。PEP 639 已用 SPDX 表达式取代
   （`license = "Apache-2.0"` + `license-files = ["LICENSE"]`）；旧写法在
   PyPI、SBOM 工具、许可证合规扫描器侧**无法可靠机器读取**。同时遗留的
   `License :: OSI Approved :: Apache Software License` classifier 已被 PEP 639
   标记为弃用（与 SPDX 表达式并存时工具会报错）。
2. **缺 `CITATION.cff`**：学术与规范化引用场景无法给出机器可读的引用信息。
   （issue 提到的审计交付物 `artifacts/CITATION.cff` 不在本仓库内，实施时按
   CFF 1.2.0 规范与仓库既有元数据起草。）
3. **无 SBOM**：release 附件只有 wheel/sdist 与签名，下游供应链扫描拿不到
   成分清单。

附带确认项（issue 第 2 条，逐项判断必要性）：`readme` content-type 声明的必要性、
`keywords`/`classifiers` 与 `docs/REPO_METADATA.md` 的一致性、`project.urls` 是否
齐备、`[project.optional-dependencies]` 分组是否清晰。

## What Changes（变更什么）

### 1. 迁移到 PEP 639 许可证写法

```toml
license = "Apache-2.0"
license-files = ["LICENSE"]
```

- 删除弃用的 `License :: OSI Approved :: Apache Software License` classifier；
- `[build-system].requires` 声明支持 PEP 639 的最低 hatchling 版本（当前
  `requires = ["hatchling"]` 未设下限，老版本会拒绝 SPDX 表达式）；
- **必须实际构建验证**（元数据里出现 `License-Expression`/`License-File`）。

### 2. 补齐 `CITATION.cff`（CFF 1.2.0）

作者/标题/版本/许可证/仓库 URL/摘要，全部取自仓库既有真源（`pyproject.toml`
的 authors/description、LICENSE、仓库 URL）。**`version` 字段是新增的第四处版本
声明**，必须并入 release 的版本更新步骤（否则就是 `repo-hygiene` 变更刚消除的
"声明漂移"类型）。

### 3. SBOM 随 release 发布（已选定方案 A）

用 `anchore/sbom-action`（Syft）在 release 工作流里对 `dist/` 生成 SPDX-JSON，
并加入 release 附件列表；不改变既有签名与 PyPI 上传步骤。

### 4. 元数据完整性取舍（在 design.md 逐项说明）

`readme` content-type、`keywords`/`classifiers`/`urls` 一致性、optional-dependencies
分组——逐项判断后只做必要改动，避免无关 churn。

### 5. 真实验证留痕

`python -m build`、`twine check dist/*`、安装 wheel 后 `import zoo_framework`
与 `zfc --help`，原始输出进变更记录（issue 验收点）。

## Impact（影响面）

| 文件 | 动作 |
|---|---|
| `pyproject.toml` | license 写法 + license-files + 删 license classifier + hatchling 下限 |
| `CITATION.cff` | 新增（根目录） |
| `.github/workflows/release.yml` | 版本更新步骤加 CITATION.cff；构建后加 SBOM 步骤；附件列表加 SBOM |
| `docs/REPO_METADATA.md` | 若其"必须含"清单与实现取舍冲突则同步（预计仅补 license 说明） |
| `docs/RELEASE_PROCESS.md` | 说明 SBOM 已成 release 工件（可选，视必要性） |

- 触发 release：改动含 `pyproject.toml`，合入 `dev`/`main` 会走发版流程——
  这是期望行为（元数据修正值得发一版）。
- 无运行时行为变化：`zoo_framework/` 代码零改动；测试套件不受影响。
- 风险：PEP 639 与 hatcling 版本的兼容性、SBOM action 首次运行失败——
  由 design 的失败可见性要求兜住（生成失败即工作流失败，不静默跳过）。
