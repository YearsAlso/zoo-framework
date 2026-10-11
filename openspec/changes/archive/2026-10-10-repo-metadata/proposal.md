# repo-metadata 提案

## Why

仓库当前"被发现"能力为零：GitHub `topics` 为空、`About` 描述是废弃旧文案且不含任何开发者会检索的关键词、homepage 为空（文档站实际在线）；PyPI 上的 `keywords` 仅 5 个泛词、`classifiers` 缺 `3.14` 与分布式计算分类、`project.urls` 缺 Changelog 与 Benchmark 两项。项目已有差异化定位（"为 AI 生成代码而设计"）与活的文档站，但没有任何检索入口能让目标用户找到它——这是全部审计动作里投入产出比最高的一项。

## What Changes

- **pyproject.toml `[project]` 表（仅元数据字段）**：
  - `keywords` 补齐面向检索的术语（按三类检索意图组织，见 design.md）
  - `classifiers` 增加 `Programming Language :: Python :: 3.14` 与 `Topic :: System :: Distributed Computing`
  - `project.urls` 增加 `Changelog` 与 `Benchmark` 两项
- **新增 `docs/REPO_METADATA.md`**：仓库元数据单一真源——GitHub Topics（≥15 个，含可复制的一行字符串）、GitHub About 描述（≤160 字符）、Homepage 值、PyPI keywords / classifiers / project_urls 建议；每一项标注"为什么选这个词、面向谁的检索"。
- SHALL NOT 修改任何产品代码、测试或 workflow。

## Capabilities

### New Capabilities

- `package-metadata`：包级与仓库级检索元数据契约——PyPI 元数据字段（keywords / classifiers / urls）SHALL 与 `docs/REPO_METADATA.md` 单一真源保持一致；真源文档 MUST 覆盖三类检索意图（调度/后台任务、高并发/线程、AI Agent 基础设施）且包含可直接使用的 GitHub 侧元数据。

### Modified Capabilities

（无——`ci-and-packaging` 的现有 Requirement 均关于安装可复现性，本 change 不触碰其行为；仅要求 apply 后重跑安装/构建验证，属于既有 Requirement 的回归。）

## Impact

- 受影响文件：`pyproject.toml`（metadata 字段）、`docs/REPO_METADATA.md`（新增）。
- 外部可见：PyPI 页面 keywords/classifiers/urls 变化（下次发版生效）；GitHub 侧 topics/About/homepage 需维护者手动在仓库设置中粘贴（代码仓库无法管理，这正是真源文档存在的原因）。
- 验证涉及：`pip install -e .`、`python -m build`、`twine check`——均为既有门禁回归，不改其配置。
- 关联 issue：#108（本 change 的工作单）。
