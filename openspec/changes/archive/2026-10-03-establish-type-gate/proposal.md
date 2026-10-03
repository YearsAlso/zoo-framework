## Why

类型检查在本项目中**一次都没有真正执行过**：CI 里 mypy 步骤带 `continue-on-error: true`，而从仓库根执行时它因为重复模块名错误直接中止、检查了 0 个文件。配置里"看起来有类型检查"，实际既没有覆盖面也没有拦截力——让它真正运行后会报出 110 个错误。

同一批工程配置里还有若干"声明了但从不生效"的作业与设置：安全扫描指向不存在的配置节、文档作业跳过了构建却仍上传产物、测试矩阵声明了版本却硬编码、锁文件与项目元数据对不上导致文档推荐的安装命令必然失败。这些问题的共同特征是**失败被静默吞掉**，与类型检查的问题同源。

## What Changes

**D 组 · 类型门禁**

- 修复类型检查的执行路径：仓库根的空 `__init__.py` 使根目录成为包，导致 `Source file found twice under different module names`，从根执行时检查 0 个文件即中止
- 清零使其真正运行后暴露的 110 个类型错误（分布在 36 / 89 个源文件）
- 移除 `quality.yml` 与 `release.yml` 中 mypy 步骤的 `continue-on-error: true`，使类型检查成为合并门禁
- 在 `[tool.mypy]` 中采用按模块逐步收紧的策略，替代当前"全局关闭 `disallow_untyped_defs`"的一刀切

**E 组 · CI 与打包卫生**

- 修正 `uv.lock` 与 `pyproject.toml` 的 Python 版本要求不一致（`>=3.12` vs `>=3.13`），以及锁定的 `greenlet 3.0.3` 在 Python 3.13 上无可用 wheel 导致 `uv sync` 必然失败的问题
- 修正 pre-commit 的 bandit 步骤：`-c pyproject.toml` 指向的文件里没有 `[tool.bandit]`，实际配置在 `.bandit.yaml`，导致配置被静默忽略
- 修正 `docs.yml`：`mkdocs build` 被 `hashFiles('mkdocs.yml')` 跳过，但其后的产物上传步骤没有同条件，必然失败
- 修正 `tests.yml`：声明了 `matrix.python-version` 但安装步骤硬编码 `"3.13"`；引用不存在的 `tests/benchmarks/` 目录
- 修正 `example/main.py`（以整数调用 `Master`，实测抛 `AttributeError`）与 `example/event/demo_event.py`（从构建产物路径 `build.lib` 导入）
- 收紧 `.gitignore` 并清理被误跟踪的构建产物与虚拟环境：当前 `git ls-files` 含 `venv/`、大量 `__pycache__/*.pyc` 与只剩字节码的 `test/` 目录

## Capabilities

### New Capabilities

- `type-checking`:类型检查的执行路径与覆盖面、类型错误基线的维护、以及检查结果作为合并门禁的强度
- `ci-and-packaging`:CI 作业对其声明输入的校验、开发环境安装的可复现性、示例代码的可运行性、以及版本控制对构建产物的排除

### Modified Capabilities

无。`openspec/specs/` 当前为空，本次是首次建立 spec 基线，两个能力均为新建。

## Impact

**受影响文件**

| 类别 | 文件 |
|---|---|
| 类型检查配置 | `pyproject.toml`（`[tool.mypy]`）、被检查的 `zoo_framework/**/*.py`（类型注解补充） |
| 仓库根 | `__init__.py`（删除） |
| CI | `.github/workflows/quality.yml`、`.github/workflows/release.yml`、`.github/workflows/docs.yml`、`.github/workflows/tests.yml` |
| 工具配置 | `.pre-commit-config.yaml`、`.gitignore`、`uv.lock` |
| 示例 | `example/main.py`、`example/event/demo_event.py` |

**不涉及的边界**

- 不新增运行时依赖，不改 `zoo_framework` 的运行时行为与公开 API
- 不追求一次性为全部 89 个源文件补齐注解；`disallow_untyped_defs` 按模块逐步开启
- 不处理 `fix-runtime-defects` 覆盖的 12 条运行时缺陷。两处有交叠需注意：`mypy` 报出的 `event_reactor.py:17`（`int` 与 `EventPriorities` 不兼容）与 `event/__init__.py`（`__all__` 元素类型错误）**正是**该变更要修的真实缺陷，因此本变更的"清零 110 个错误"必须在 `fix-runtime-defects` 之后进行并重新取基线
- 不在本次引入 mkdocs 文档体系（`docs.yml` 的问题按"上传与构建同条件"处理，而非补出 `mkdocs.yml`）
