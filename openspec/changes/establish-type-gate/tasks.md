## 1. 前置：确认依赖顺序并重取基线

- [ ] 1.1 确认 `fix-runtime-defects` 已落地（至少其与类型检查交叠的两处缺陷已修）；验证：`mypy zoo_framework --explicit-package-bases` 的输出中不再出现 `reactor/event_reactor.py` 的 `int`/`EventPriorities` 不兼容错误，也不再出现 `event/__init__.py` 的 `__all__` 元素类型错误
- [ ] 1.2 重取类型错误基线并归档为三类（真实缺陷 / 纯注解缺失 / 第三方存根缺失）；验证：`mypy zoo_framework --explicit-package-bases` 的错误清单已逐条归类并记录到提交说明或 design 的补充段落，类别计数之和等于总数

## 2. 修复类型检查的执行路径

- [ ] 2.1 删除仓库根的空 `__init__.py`；验证：`grep -rn "^from zoo import\|^import zoo$" zoo_framework/ tests/ example/` 无结果，且 `python -m build` 后 `twine check dist/*` 通过
- [ ] 2.2 从仓库根执行类型检查，确认不再因模块名映射冲突而中止；验证：`mypy zoo_framework` 输出中出现被检查文件数汇总，且不含 `errors prevented further checking`
- [ ] 2.3 确认被检查文件数覆盖框架包全部源文件；验证：`mypy zoo_framework` 报告的检查文件数等于 `find zoo_framework -name "*.py" | wc -l`。若因删除根 `__init__.py` 后仍存在映射冲突，按 design D1 的兜底在 `[tool.mypy]` 中显式声明包基后重验

## 3. 清零类型错误

- [ ] 3.1 修复归类为"真实缺陷"的类型错误；验证：该类别错误数归零，且相关回归用例仍通过
- [ ] 3.2 为归类为"纯注解缺失"的错误补充类型注解；验证：该类别错误数归零，且 `pytest -q` 仍全绿
- [ ] 3.3 处理归类为"第三方存根缺失"的错误，优先补存根依赖或收窄 `ignore_missing_imports` 的作用域，而非全局忽略；验证：`mypy zoo_framework` 报告零错误且退出码为 0
- [ ] 3.4 审查本次新增的每一处 `# type: ignore` 与 `cast`；验证：`grep -rn "type: ignore\|cast(" zoo_framework/` 的每一处都有相邻注释说明原因，且没有一处是用于压制本可修复的类型不匹配（逐条人工核对并记录）

## 4. 建立类型门禁

- [ ] 4.1 移除 `.github/workflows/quality.yml` 中 mypy 步骤的 `continue-on-error`；验证：临时向任一源文件插入一个类型错误后本地执行类型检查返回非零退出码，撤销后返回零
- [ ] 4.2 移除 `.github/workflows/release.yml` 中 mypy 步骤的 `continue-on-error`，并确认发布作业依赖质量检查的结果；验证：release.yml 中发布作业的 `needs` 链包含质量检查作业，且类型检查失败时发布步骤不执行
- [ ] 4.3 按 design D3 在 `[tool.mypy.overrides]` 中对 `zoo_framework/utils/` 开启 `disallow_untyped_defs`；验证：该模块中缺注解的函数被报告为类型错误
- [ ] 4.4 确认开启单模块严格模式后其他模块的检查结论不变；验证：对比开启前后 `mypy zoo_framework` 在其余模块上的错误数，二者一致（均为零）
- [ ] 4.5 确认本地与 CI 的类型检查命令逐字一致；验证：比对 `quality.yml` 的 mypy 步骤命令与本地执行的命令字符串，完全相同

## 5. 开发环境与锁定文件

- [ ] 5.1 按 design D4 修正 `uv.lock` 的 `requires-python`，使其与 `pyproject.toml` 一致；验证：两个文件的 Python 版本要求字符串相等
- [ ] 5.2 按 design D4 将 `uv.lock` 中的 `greenlet` 升级到在 Python 3.13 上有可用产物的最低版本，仅做最小改动；验证：`uv sync --frozen` 在 Python 3.13 上成功完成，不再出现 greenlet 构建失败
- [ ] 5.3 确认锁定文件未发生无关依赖变动；验证：`git diff uv.lock` 只涉及 `requires-python` 与 `greenlet` 相关行及必要的传递依赖，不含无关包的版本变动
- [ ] 5.4 确认元数据安装路径仍可用；验证：`pip install -e ".[dev]"` 成功，随后 `pytest -q` 全绿

## 6. CI 作业修正

- [ ] 6.1 按 design D5 把 `.pre-commit-config.yaml` 中 bandit 的参数由 `-c pyproject.toml` 改为 `-c .bandit.yaml`；验证：`pre-commit run bandit --all-files` 实际读取到 `.bandit.yaml` 中的 `skips` 与 `exclude_dirs`（不再静默忽略配置）
- [ ] 6.2 按 design D6 给 `.github/workflows/docs.yml` 的产物上传步骤加上与构建步骤相同的 `hashFiles('mkdocs.yml')` 条件；验证：在 `mkdocs.yml` 缺失的前提下，构建与上传步骤同为跳过，作业不以失败结束
- [ ] 6.3 按 design D7 让 `.github/workflows/tests.yml` 的 Python 安装步骤使用 `${{ matrix.python-version }}`；验证：该文件中不再出现硬编码的 Python 版本字面量
- [ ] 6.4 按 design D7 修正 `tests.yml` 中引用不存在目录的 `benchmark` 作业（加目录存在性条件，或移除该作业）；验证：在 `tests/benchmarks/` 缺失的前提下该作业被跳过而非失败。若选择移除，须在提交说明中记录原因
- [ ] 6.5 全量复核所有 workflow 中"条件加在主步骤、未加在依赖它的后续步骤"的情形；验证：逐个 workflow 检查含 `if:` 的步骤，其下游依赖步骤均带同条件，无遗漏

## 7. 示例与仓库卫生

- [ ] 7.1 按 design D9 修正 `example/main.py` 构造框架对象的方式（当前以整数调用，实测抛 `AttributeError`）；验证：按示例自身声明的方式运行该入口不再抛异常
- [ ] 7.2 按 design D9 修正 `example/event/demo_event.py` 从 `build.lib` 导入的问题；验证：`grep -rn "build\.lib" example/ zoo_framework/` 无结果，且该模块可被成功导入
- [ ] 7.3 按 design D8 补齐 `.gitignore`，使其覆盖字节码缓存、构建输出与虚拟环境三类路径；验证：忽略规则中三类路径均存在，且 `git status` 不再把 `venv/` 列为未跟踪的潜在新增项
- [ ] 7.4 按 design D8 把已被误跟踪的构建产物、字节码缓存与虚拟环境从版本控制索引中移除，**保留磁盘文件**；验证：`git ls-files | grep -E '^(venv|build)/|__pycache__|\.pyc$'` 结果为空，且 `ls venv/Scripts/python.exe` 等文件仍在磁盘上
- [ ] 7.5 按 design D8 清理只剩字节码的 `test/` 目录索引条目；验证：`git ls-files test/` 结果为空

## 8. 收尾验证

- [ ] 8.1 端到端验证门禁有效性：临时引入一个类型错误 → 本地类型检查失败且退出码非零 → 撤销后通过且退出码为零；验证：两次结果符合预期，且第二次的通过是真实的零错误而非被 `ignore` 压制
- [ ] 8.2 全量回归确认未破坏运行时行为；验证：`pytest -q` 全绿，用例总数不少于 `fix-runtime-defects` 完成后的数量
- [ ] 8.3 确认未夹带范围外改动；验证：`git diff --stat` 限于 `pyproject.toml`、`.gitignore`、`.pre-commit-config.yaml`、`.github/workflows/`、`uv.lock`、`example/`、仓库根 `__init__.py` 及为消除类型错误所必需的最小源文件调整，不含新增运行时依赖
