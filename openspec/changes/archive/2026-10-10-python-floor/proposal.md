## Why

`pyproject.toml` 声明 `requires-python = ">=3.13"`，但**这个门槛从未被系统评估过**：全仓 174 个 Python 文件里没有一个 3.11 之后才有的语法或标准库特性，唯一"3.13 专属"的部分是工具链配置与文档措辞。对一个要嵌入别人生产代码的框架，门槛的代价与独立 CLI 完全不同——它直接决定"能否被写进依赖"，而实测证据表明这个门槛把一个能在 3.10 上跑通的纯 Python 框架限制在了最新解释器上。

实测（本 worktree 亲跑，非推断）：

| 候选下界 | 全量测试 | 阻碍 |
|---|---|---|
| **3.11.15** | **1107 passed**（1 个模块 skip：可选 Rust 扩展未编译，与版本无关） | 无 |
| 3.10.20 | 1073 passed | `tests/test_security_supply_chain.py` 等 2 个测试模块 `import tomllib`（3.11+）连收集都失败 |
| 3.12 / 3.13 | 全绿 | — |

下界的真正来源是 **44 个文件**在**没有** `from __future__ import annotations` 的情况下使用 PEP 604（`X | None`）注解，注解在 import 期求值 ⇒ 硬性 **≥3.10**；3.11 是零适配成本的最近一档，也是 issue 的优先目标。

## What Changes

- **`requires-python` 3.13 → 3.11**（`pyproject.toml`），classifiers 列出 `>=3.11` 覆盖的版本区间。
- **单一真源同步**：`uv.lock` 的 `requires-python`、`[tool.ruff] target-version`（`py313` → `py311`）、`[tool.mypy] python_version`（`3.13` → `3.11`）随下界一起改，避免"元数据说 3.11、工具链按 3.13 检查"的分叉。
- **CI 测试矩阵覆盖下界**：`tests.yml` 的 `python-version` 由 `["3.13"]` 变为 `["3.11", "3.13"]`，仍跑 ubuntu / windows / macos 三平台（矩阵 3 → 6 个测试作业）。
- **BREAKING** 移除运行时依赖 `typing-extensions>=4.7.0`：它被声明为运行依赖、被 4 处文档计入"运行时依赖 4 个"，但**全仓 0 处 import**。依赖数量与名称的真源（`pyproject.toml`）与文档一并收敛。
- **文档门槛声明全量同步**：两份 README（含 Python badge）、`AGENTS.md`、`CLAUDE.md`、`CONTRIBUTING.md`、`docs/CONTRIBUTING_MAINTAINER.md`、`docs/README.md`、`docs/install.md`、`docs/FAQ.md`（现答案只有"因为 pyproject 这么写"，改为写出依据）、`docs/REPO_METADATA.md`、`.github/ISSUE_TEMPLATE/bug_report.md`、`.claude/` 下的 agent/skill 指令。**测量环境声明 MUST NOT 一并改写**——"bench 在 Python 3.13 上实测""迁移指南的报错在 3.13 上取得"是关于**测量环境**的事实，不是门槛声明，改掉就变成假话。
- **依据落盘**：`docs/DEVELOPMENT.md` 写明"为什么是 3.11"，避免下次再出现 `3.8+` / `3.13` 并存的矛盾。
- **机械守护**（issue 点名要 #114 那类检查拦住）：扩展 `tests/test_doc_consistency.py`，把"门槛声明与 `requires-python` 一致、工具链 target 与下界一致、无残留旧门槛、测量环境声明不被误改"写成断言。
- **`native/` 保持自己的 3.13 下界**：它是可选编译扩展、CI 完全不覆盖；跟着降等于写一条无法验证的声明。改为在规格与文档中写明"可选扩展与主包下界解耦"。

## Capabilities

### New Capabilities

（无——本变更不引入新能力，只收紧既有能力的验收口径。）

### Modified Capabilities

- `ci-and-packaging`：`开发环境安装 MUST 可复现` 增补"下界 MUST 有可复现证据、并与锁文件 / 工具链 target / CI 矩阵 / 文档门槛声明一致"；`CI 声明的参数 MUST 被实际使用` 增补"矩阵 MUST 覆盖下界并在三平台各跑一次"；新增 `运行时依赖 MUST 与实际使用一致`（声明即使用、文档计数与元数据一致）。
- `native-task-execution`：`原生扩展 MUST 为可选依赖且缺失时显式失败` 增补"扩展的 Python 下界独立于主包、MUST 在文档中说明、在下界解释器上安装失败 MUST 显式"。

## Impact

- **元数据与依赖**：`pyproject.toml`（`requires-python` / classifiers / `dependencies` / ruff / mypy）、`uv.lock`。
- **CI**：`.github/workflows/tests.yml`（矩阵）；`quality.yml` 等保持 3.13（静态检查单版本即可），文档改为区分"矩阵跑 3.11 与 3.13、静态检查跑 3.13"。
- **对外契约**：安装门槛放宽（新增 3.11 / 3.12 可安装），无 API、无持久化格式、无配置键变更；移除未使用的运行依赖会改变安装树（唯一实质性收窄）。
- **文档**：上列 12 处门槛声明 + `docs/DEVELOPMENT.md` 依据 + `docs/FAQ.md` 答案重写；`docs/SECURITY_MODEL.md`、`docs/install.md`、`docs/security-supply-chain.md` 的依赖清单与计数。
- **测试**：`tests/test_doc_consistency.py`（门槛一致性断言）、`tests/test_security_supply_chain.py`（依赖计数断言随移除更新）。
- **非目标**：不为支持 3.10 引入兼容层或 `tomli`；不改任何对外 API；不改 `native/` 的下界值；不重写 bench 的测量环境记录。
