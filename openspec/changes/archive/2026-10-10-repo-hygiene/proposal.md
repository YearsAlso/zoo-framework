# 提案：repo-hygiene

## Why（为什么）

issue #115 列的三处卫生问题（逐条实测证据见下）都在直接误导贡献者：
`[tool.bumpversion]` 声称 `0.8.0` 而真实版本是 `0.10.6-beta`；README / CONTRIBUTING /
CLAUDE.md 三处警告"`uv sync` 会毁环境"，而**实测已不再成立**；`requirements-dev.txt`
与 `pyproject.toml [dev]` 内容分叉构成双依赖真源。

## What Changes（做什么）

### 逐条复核核对表（4 条 → 处置）

| # | issue 表述 | 实测证据（2026-10-10，基线 0.10.6-beta） | 定性 | 处置 |
|---|---|---|---|---|
| 1 | bumpversion 说谎 | `pyproject.toml:285 current_version = "0.8.0"` vs `:7 version = "0.10.6-beta"`、`__init__.py:29 __version__ = "0.10.6-beta"`（三者不一致）。发布流程用 `scripts/next_version.py` + `sed` 三处版本声明（release.yml:216-218）**完全不经 bumpversion**；`[tool.bumpversion]` 含 `[[tool.bumpversion.files]]` 挂两个文件的替换规则——是零使用的死配置 | **成立** | **修**：删除 `[tool.bumpversion]` 整段与 dev 依赖里的 `bump-my-version`（流程不用它，保留只会误导）；`__init__.py` 与 pyproject 一致无需改 |
| 2 | uv.lock 陈旧，三处警告兜底 | **警告已过时**：实测 `uv.lock` 里 gevent/greenlet **零命中**（0e7d02b 重锁后描述的是 0.9+ 依赖集）；本次 `uv lock` 后 `uv lock --check` 干净、**隔离干净 venv `uv sync --extra dev --extra docs` 完整可用**（pytest 9.1.1 + ruff 0.16.10 装齐；全量 1017 passed / 1 skipped，skip 为 `zoo_framework_native` 可选扩展未装——良性） | **结论反转：lock 已能安全用** | **修**：`uv lock` 重锁补 mkdocstrings；三处文档警告收敛为一句"标准用法 `uv sync --extra dev` 与 pip 皆可"；CLAUDE.md 的"pip 备用路径"说明同步 |
| 3 | requirements.txt 失真 | `requirements.txt` 已在 `93afc18`（#93）删除。**但 `requirements-dev.txt` 仍在**：内容与 `pyproject [dev]` 对照多出 hatchling / pytest-benchmark / bandit / structlog / types-PyYAML（部分不在 dev extra），且唯一引用点 docs/contributing/development.md:80（"方式二"） | **成立（以 requirements-dev.txt 形式）** | **修**：删 `requirements-dev.txt` + development.md 的「方式二」节；依赖唯一真源 = `pyproject.toml` |
| 4 | main 的 SECURITY.md `0.5.3-beta` | **分支上已修**：本分支 SECURITY.md 为无版本硬编码的"最新 minor 线"表述；`origin/main:SECURITY.md` 仍是旧文（`0.5.3-beta`，L12/L90）——随本分支合入 dev→main 流程即被覆盖 | **dev 侧已解开** | **验证**：合入 main 后 grep 复核（移交动作记录在案） |

另：development.md:51 `conda create -n zoo python=3.11`——Python 门槛 3.13（#114 刚修过同文件 3.8），3.11 装不上项目，属同一"门槛陈述过期"族，顺带修。

### 验收锚点（对应 issue 验收标准）

- `grep current_version pyproject.toml` → 0 命中；`^version` 与 `__version__` 一致（0.10.6-beta）
- 干净环境 `uv sync` 装齐并跑 pytest（证据：本轮隔离 venv 全量 1017 passed / 1 skipped-benign）
- 三处 uv 警告收敛为一条正常说明
- `requirements-dev.txt` 删除，全库引用 0 命中
- 全量 pytest 全绿

## Capabilities（能力）

- **New**: `repo-hygiene` — 版本声明真源唯一、依赖真源唯一、lock 文件与文档承诺一致
- **Modified**: 无

## 影响（Impact）

- `pyproject.toml`：删 `[tool.bumpversion]` 段 + dev 列表里的 `bump-my-version`
- `uv.lock`：重锁（+mkdocstrings）；`docs/contributing/development.md`、`CONTRIBUTING.md`（双节）、`README.md`、`README.zh.md`、`CLAUDE.md`：uv 警告收敛 + conda 3.11 修正 + 删「方式二」
- 删除 `requirements-dev.txt`
- 不碰：release 流程（它不经 bumpversion）、`.env`（三处版本声明之一，本就一致）
