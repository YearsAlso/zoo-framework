# repo-metadata 规格增量 · package-metadata

## Purpose

定义包级（PyPI）与仓库级（GitHub）检索元数据的单一真源与一致性契约，使三类目标读者（找调度/后台任务、找高并发/线程、找 AI Agent 基础设施）都能通过检索渠道发现本项目，并保证元数据不随时间漂移。

## ADDED Requirements

### Requirement: PyPI 检索元数据完备

`pyproject.toml` 的 `[project]` 表 SHALL 声明面向检索的 `keywords`（MUST 覆盖三类检索意图：任务调度/后台任务、并发/线程、AI Agent 基础设施，且 MUST 包含 `agent` 与 `orchestration`）；`classifiers` SHALL 包含 `Programming Language :: Python :: 3.14` 与 `Topic :: System :: Distributed Computing`；`[project.urls]` SHALL 包含 `Changelog` 与 `Benchmark` 两项。

#### Scenario: keywords 覆盖三类检索意图
- **WHEN** 阅读 `pyproject.toml` 的 keywords 与 `docs/REPO_METADATA.md` 的词表
- **THEN** 三类意图各有对应词条，且 `agent` 与 `orchestration` 在列

#### Scenario: classifiers 含 3.14 与分布式计算
- **WHEN** 在 PyPI 上按 `Programming Language :: Python :: 3.14` 或 `Topic :: System :: Distributed Computing` 过滤
- **THEN** zoo-framework 出现在结果中（元数据随下次发版生效）

#### Scenario: urls 含 Changelog 与 Benchmark
- **WHEN** 阅读 `[project.urls]`
- **THEN** `Changelog` 指向仓库内 CHANGELOG.md 路径，`Benchmark` 指向 zoo-bench 报告站点

### Requirement: 仓库元数据单一真源

仓库 SHALL 提供 `docs/REPO_METADATA.md` 作为 GitHub 侧元数据（topics / About 描述 / homepage）与 PyPI 元数据的唯一真源，其中：topics 列表 MUST ≥15 个、MUST 包含 `task-scheduler`、`background-jobs`、`orchestration`、`agent`、`llm`，并提供一行可复制粘贴的字符串；About 描述 MUST ≤160 字符且与 pyproject `description` 一致；每个词条 MUST 附"为什么选这个词、面向谁的检索"的说明。

#### Scenario: topics 可直接复制使用
- **WHEN** 维护者打开 `docs/REPO_METADATA.md` 准备更新 GitHub topics
- **THEN** 能找到 ≥15 个 topic 的单行可粘贴字符串，含五个必需词

#### Scenario: About 描述与 PyPI 一致
- **WHEN** 比较 REPO_METADATA.md 中的 About 建议值与 pyproject 的 description
- **THEN** 两者一致，且长度 ≤160 字符

### Requirement: 元数据变更不破坏构建

元数据变更 SHALL NOT 破坏既有安装与构建路径：可编辑安装成功、包可正常导入、构建产物通过 twine 校验。

#### Scenario: 安装与导入回归
- **WHEN** 元数据变更后执行 `pip install -e .` 与 `python -c "import zoo_framework"`
- **THEN** 安装成功且导入正常

#### Scenario: 构建产物校验
- **WHEN** 执行 `python -m build` 与 `twine check dist/*`
- **THEN** 构建成功且校验全部通过
