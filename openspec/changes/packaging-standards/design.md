# 设计：packaging-standards

## 决策

### D1: PEP 639 迁移写法与构建后端下限

选定：

```toml
[build-system]
requires = ["hatchling>=1.27"]
build-backend = "hatchling.build"

[project]
license = "Apache-2.0"
license-files = ["LICENSE"]
```

**为何设下限**：当前 `requires = ["hatchling"]` 无下限，而 PEP 639 的 SPDX 表达式
与 `license-files` 需要较新的 hatchling（1.27 起支持）；无下限时旧解析器可能
拒绝或忽略字段，产出"看起来成功但元数据不合规"的包。设下限使失败发生在构建期
而非下游扫描期（失败前置原则）。下限值以**实际构建验证**为准：若 `>=1.27` 构不出
`License-Expression`，则上调到实际所需版本并把实测结论写回本文件。

**为何删 `License :: OSI Approved :: Apache Software License`**：PEP 639 明确弃用
许可证 classifier，且当 SPDX 表达式与许可证 classifier 并存时工具应报错——两者
并存会让 PyPI 侧校验与合规扫描出现互相矛盾的信号。删除安全性核对：
`docs/REPO_METADATA.md` 的"classifiers 必须含"清单只列
`Programming Language :: Python :: 3.14` 与 `Topic :: System :: Distributed Computing`，
**不含**许可证 classifier，故删除不破坏该真源一致性（对应 spec 的"投影一致"场景）。

### D2: `CITATION.cff` 起草依据与版本同源

- **起草依据（全部来自仓库既有真源，不新造事实）**：
  `title`/`abstract` ← README 首段与 `pyproject.description`；
  `authors` ← `pyproject` 的 `authors`（XiangMeng / mengxiang931015@live.com）；
  `license` ← `LICENSE`（Apache-2.0）；`repository-code` ← `project.urls.Repository`；
  `version` ← `pyproject` 版本（**非**独立值）。
- **第四处版本声明**：`repo-hygiene` 变更刚确立"版本声明必须同源、不得漂移"，
  CITATION 的 `version` 若不纳入机制就是新漂移点。因此把 release 工作流的
  "Update version declarations" 步骤从三处扩到四处（sed 按**键**匹配，与既有
  做法一致），并把断言循环的 `for f in ...` 一并扩到四个文件——少写一处即步骤
  失败，不允许开出错的 PR。
- CFF 的 `version` 是字符串字段，`0.10.6-beta` 这类预发布标识合法（无需转 semver）。
- **校验方式**：首选 `cffconvert --validate`（需网络装包）；若环境不可用，退化为
  结构化校验——YAML 可解析 + 六个必备字段存在性 + `version` 与 pyproject 相等，
  并把"未跑通工具校验"的事实写进变更记录，不谎称已通过工具校验。

### D3: SBOM 生成方案（用户已选 A）

三方案对比与结论：

| 方案 | 收益 | 风险 | 改动量 | 结论 |
|---|---|---|---|---|
| **A. `anchore/sbom-action`（Syft）生成 SPDX-JSON** | GitHub 生态成熟；与仓库"action 按 SHA 固定"的既有约定一致；零 Python 依赖 | 引入一个第三方 action（按 SHA pin 可控）；产物是文件级成分清单 | release.yml ~+12 行 + 附件 1 行 | **选定** |
| B. `cyclonedx-bom`（pip）生成 CycloneDX JSON | 安全扫描器最常消费的格式 | CI 新增 pip 依赖及其传递依赖，与"依赖极简"取向相悖 | release.yml ~+14 行 | 未选 |
| C. 只记录方案不改 workflow | 零 CI 风险 | 合规/供应链期待仍未交付，需另立 issue | 仅文档 | 未选（issue 允许的降级路径，本次不需要） |

落地要点：

- 步骤位置：**构建之后、签名之前**（保证 SBOM 描述的就是要发布的 `dist/` 产物）；
- 输出：`dist/<name>.spdx.json`（文件名确定，便于加入附件列表）；
- **失败可见**：action 失败即工作流失败（不加 `continue-on-error`）——"看起来成功
  但没有 SBOM"的 release 比没有 SBOM 更糟；
- **不碰**：cosign 签名步骤、PyPI OIDC 上传步骤、tag/版本算术。

### D4: 元数据完整性逐项取舍（issue 第 2 条）

| 项 | 现状 | 结论 |
|---|---|---|
| `readme` content-type | `readme = "README.md"`（hatchling 按扩展名推断 `text/markdown`） | **不改**。hatchling 会自动推断并在 PyPI 正确渲染；显式字典写法是等价冗余，增加无收益的改动面 |
| `keywords` | 19 个，与 REPO_METADATA 三类检索意图对应 | **不改**（已一致） |
| `classifiers` | 含 3.14 与 Distributed Computing 两项必需项 + 1 个许可证 classifier | 仅删许可证 classifier（见 D1） |
| `project.urls` | Homepage/Documentation/Repository/Issues/Changelog/Benchmark 六项齐全 | **不改**（REPO_METADATA 要求的 Changelog 与 Benchmark 均已在） |
| `[project.optional-dependencies]` | `dev`（质量工具＋测试＋构建）与 `docs` 两组 | **不改**。拆出 `test` 组不会给使用者带来收益（`dev` 仍是一次装齐的入口），却会让 CI 安装命令与文档同步改动——违背最小改动 |

### D5: 验证方式与留痕

按 issue 验收点逐条真跑并保留原始输出：`python -m build` → `twine check dist/*`
→ 干净环境安装 wheel → `import zoo_framework` + `zfc --help`。构建走隔离环境
（默认），确保验证的是声明了下限后的真实解析路径。`dist/` 为构建产物，不入库。

## 风险

- **hatchling 下限标错**：以实际构建输出为准回写（D1），不做未验证的猜测。
- **SBOM action 首跑失败**（权限/网络）：失败即工作流失败，属期望行为；
  若确因 action 不可用而受阻，退回方案 C 并记录（issue 明确允许）。
- **发版触发**：改动含 `pyproject.toml`，合入 `dev` 后会自动走一次 patch 发版——
  元数据修正值得发版，无需额外处理。
