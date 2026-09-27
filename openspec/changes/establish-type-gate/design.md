## Context

动机见 `proposal.md`。以下现状均已在 Python 3.13.14 上实测确认。

**类型检查的真实状态**

```
                        CI 里配置的 mypy
                              |
              +---------------+---------------+
              |                               |
    continue-on-error: true          从仓库根执行
    (quality.yml:52,                  `mypy zoo_framework`
     release.yml)                          |
              |                               |
    即使报错也不拦截              根 __init__.py 使仓库根成为包
              |                               |
              |               Source file found twice:
              |               "zoo.zoo_framework.conf.log_config"
              |               "zoo_framework.conf.log_config"
              |                               |
              |               errors prevented further checking
              |                       => 检查了 0 个文件
              +---------------+---------------+
                              |
                   真实结果（绕过映射问题后）
              Found 110 errors in 36 files (checked 89 source files)
```

`[tool.mypy]` 侧同样关闭了强制力：`disallow_untyped_defs = false`、`disallow_incomplete_defs = false`、`ignore_missing_imports = true`。

**与 `fix-runtime-defects` 的交叠**：110 个错误里至少两处是**真实缺陷**，而非注解缺失——`reactor/event_reactor.py:17`（`int` 与 `EventPriorities` 不兼容）与 `event/__init__.py` 的 `__all__` 元素类型错误。二者都在 `fix-runtime-defects` 的范围内。因此本变更的"清零"必须在其之后重取基线，否则会把重复修复同一处。

**安装路径现状**：`uv.lock` 声明 `requires-python = ">=3.12"`，`pyproject.toml` 声明 `>=3.13`；锁定 `greenlet 3.0.3`（2023 年发布，早于 Python 3.13），在 3.13 上无可用 wheel 且本地构建失败——实测 `uv sync` 必然失败。`pip install -e ".[dev]"` 路径可用（140 个测试在此路径下全绿）。

## Goals / Non-Goals

**Goals**

- 让类型检查真正执行、真正覆盖、真正拦截
- 让"配置里声明的"与"实际生效的"一致——涵盖类型检查、CI 条件、工具配置、锁定文件、示例
- 为注解严格度的后续提升留下可逐模块推进的机制

**Non-Goals**

- 不一次性为 89 个源文件补齐全部注解（见 D3）
- 不引入 mkdocs 文档体系（见 D6）
- 不整体升级依赖（见 D4）
- 不改动 `zoo_framework` 的运行时行为与公开 API

## Decisions

### D1 · 根 `__init__.py`：删除文件，而非在配置里绕过

仓库根的 `__init__.py` 是 0 字节空文件，唯一作用是让仓库根成为包，而仓库根并非包——`pyproject.toml` 用 hatchling 且 `packages = ["zoo_framework"]`。

- **选**：删除该文件，随后验证打包路径不受影响（`python -m build` + `twine check dist/*`）。
- **理由**：冲突的根源是"根目录被当成包"这一错误事实，删除即消除根源；在配置里加 `explicit_package_bases` 只是绕过症状，且会让"为什么需要这个开关"成为后续维护者的隐性知识。
- **已考虑的替代**：保留文件 + 在 `[tool.mypy]` 设 `explicit_package_bases = true`。作为**兜底**保留在任务中：若删除后仍出现映射冲突，再启用该开关。
- **验证要求**：删除后必须实测打包通过，因为 `setup.py` 里存在 `find_packages()`（见 Risks）。

### D2 · 清除 `continue-on-error` 的顺序：先清零，再上锁

当前若直接移除 `continue-on-error`，CI 会立刻变红（110 个错误），门禁变成阻塞。

- **选**：严格按「重取基线 → 分类归档 → 修真实缺陷 → 补注解 → 零错误 → 移除 `continue-on-error`」推进。
- **理由**：门禁的价值来自"绿色是可信的"。在基线非零时上锁，只会得到一条长期被忽略的红色作业，与当前带 `continue-on-error` 的效果等价。

### D3 · 注解严格度：按模块 `overrides` 提升，而非全局开关

- **选**：`disallow_untyped_defs` 保持全局关闭，改用 `[[tool.mypy.overrides]]` 对单个模块开启；首期选 `zoo_framework/utils/` 作为试点。
- **理由**：spec 要求"严格程度可按模块提升"，`overrides` 直接支持该语义；选 `utils/` 是因为它依赖最少、且现有多处已有类型注解（如 `log_utils` 的 `message: str, cls_name: str | None = None`），试点成本最低。
- **已考虑的替代**：一次性全局开启。拒绝理由：会把一个门禁变更膨胀为覆盖 89 个文件的大规模注解工程，与"建立门禁"这一目标不成比例，且极易诱发 D2 中提到的批量压制。

### D4 · `uv.lock`：最小修正，不整体重新解析

- **选**：仅修正 `requires-python` 字段，并把 `greenlet` 升级到在 Python 3.13 上有可用产物的版本。
- **理由**：实测整体重新解析会连带变动大量无关依赖（1046 行插入 / 405 行删除，`annotated-types`、`anyio` 等全部换版），把"修一个装不上的锁文件"变成"依赖大升级"，引入不可控的回归面。
- **已考虑的替代**：`uv lock` 重新生成。拒绝理由同上；且本次目标只是让文档推荐的安装路径可用。
- **验证要求**：`git diff uv.lock` 必须只涉及 `requires-python` 与 `greenlet` 相关行及必要的传递依赖，并在 Python 3.13 上实测 `uv sync --frozen` 成功。

### D5 · bandit 配置指向：改参数，不迁配置

- **选**：把 `.pre-commit-config.yaml` 的 bandit 参数由 `-c pyproject.toml` 改为 `-c .bandit.yaml`。
- **理由**：`.bandit.yaml` 已存在且已被 `quality.yml` 使用（`bandit -r zoo_framework -c .bandit.yaml`）。改一处参数即可让本地钩子与 CI 一致；把配置迁进 `pyproject.toml` 会造成迁移成本与后续两处配置漂移的风险，收益为零。

### D6 · CI 条件：让配套步骤与主步骤同条件，不新建体系

`docs.yml` 用 `hashFiles('mkdocs.yml') != ''` 跳过了 `mkdocs build`，但其后的产物上传步骤没有该条件——构建被跳过、上传仍执行，必然失败。

- **选**：把同一条件加到上传步骤上（以及 §6.5 要求的全量复核：所有 workflow 中不存在"条件只加在主步骤、未加在依赖它的后续步骤"的情形）。
- **理由**：这与 `fix-runtime-defects` 中"修复每一处静默失效"是同一条原则在 CI 上的应用。
- **已考虑的替代**：补出一个真实可用的 `mkdocs.yml`。拒绝理由：那等于新增一套文档构建体系，属于新功能而非修复，且会改变发布流程的产物。

### D7 · 测试矩阵：让声明成为单一真源

`tests.yml` 声明了 `matrix.python-version: ["3.13"]`，但 `actions/setup-python` 里硬编码 `"3.13"`——矩阵声明是装饰性的。

- **选**：安装步骤改用 `${{ matrix.python-version }}`。另有 `benchmark` 作业引用不存在的 `tests/benchmarks/`，按"目录存在才运行"处理。
- **理由**：声明与使用分离是 bug 温床；让矩阵成为单一真源后，将来扩版本只需改一处。

### D8 · 仓库卫生：只改索引，不动工作区文件

- **选**：补齐 `.gitignore`（虚拟环境、构建输出、字节码缓存），并把已被误跟踪的 `venv/`、`__pycache__/*.pyc`、`build/`、只剩字节码的 `test/` 从版本控制索引中移除，**保留磁盘上的文件**。
- **理由**：`git ls-files` 当前含 2863 个此类条目（含整个 `venv/` 与 `test/`）。移除索引条目不影响任何人的本地环境，也不删除任何文件；而把它们留在版本控制里会让每次提交都携带数千条噪声，并在 `.gitignore` 与实际状态之间制造持续矛盾。

### D9 · 示例：修到可运行，不重写

- **选**：`example/main.py` 改为以默认配置构造框架对象（当前传整数，实测抛 `AttributeError: 'int' object has no attribute 'config_path'`）；`example/event/demo_event.py` 的 `from build.lib.zoo_framework import event` 改为指向安装后的包。
- **理由**：示例是文档的一部分，当前两处都不可运行，会让使用者第一步就失败。不重写是因为示例反映的是使用方式而非框架能力，超出范围。

## Risks / Trade-offs

**[删除根 `__init__.py` 影响打包] → ** `setup.py` 里有 `find_packages()`，删除文件可能改变其发现结果。缓解：任务中要求实测 `python -m build` + `twine check dist/*` 通过；若失败则回退到 D1 的兜底方案（保留文件 + `explicit_package_bases`）。

**[清零 110 个错误时用 `# type: ignore` 掩盖真实缺陷] → ** 这是本次最实质的风险：把类型错误压成绿色，却留下未修的 bug，比不做门禁更坏（因为它制造"已检查"的假象）。缓解：任务中设专门环节审查每一处新增的 `ignore`/`cast`，要求逐处注释原因；并明确禁止用批量压制替代修复。

**[与 `fix-runtime-defects` 的交叠导致重复修复] → ** `event_reactor.py:17` 与 `event/__init__.py` 两处既是 mypy 错误又是真实缺陷。缓解：本变更的第一个任务就是确认前置变更已落地并重取基线，把这两处从清单中剔除。

**[门禁上线后阻塞他人提交流程] → ** 类型检查从"建议"变为"强制"是新约束，存量贡献者的提交习惯会受影响。缓解：先清零再上锁（D2），且严格度按模块推进（D3），使新增门槛是"新代码不许引入错误"而非"立刻补齐所有旧注解"。

**[修正 `uv.lock` 的 greenlet 版本引入行为差异] → ** greenlet 是 gevent 的底层依赖，跨多个版本升级可能影响 gevent 行为。缓解：只升到"在 3.13 上有 cp313 产物的最低可用版本"而非最新版；并实测 140 个既有测试仍全绿。

**[移除索引中的 `venv/` 影响他人工作区] → ** 若他人已克隆，其本地 `venv/` 文件不受影响，只是此后不再被跟踪。缓解：这一操作本就是恢复 `.gitignore` 已经声明的意图（`__pycache__/` 早已在忽略列表中），不存在语义变化。

**[示例改为可运行后可能暴露新的框架问题] → ** 示例此前不可运行，意味着它从未真正执行过。缓解：这属于 `fix-runtime-defects` D12 同一类收益（让未执行的路径被执行），若暴露新缺陷则暂停并单独提变更。
