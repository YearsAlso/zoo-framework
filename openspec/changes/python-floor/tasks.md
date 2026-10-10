# python-floor 任务清单

## 1. 元数据真源（design D1 / D2 / D5 / D9）

- [ ] 1.1 `pyproject.toml` 的 `requires-python` 改为 `">=3.11"`，classifiers 改为列出该区间
      （3.11 / 3.12 / 3.13 / 3.14，保留既有的 3.14 声明），并把 `requires-python` 的注释
      指向 `docs/DEVELOPMENT.md` 的依据一节
      （验证：`grep -n "requires-python" pyproject.toml` 显示 `>=3.11`；
      `classifiers` 含 `Programming Language :: Python :: 3.11` 与 `:: 3.12`）
- [ ] 1.2 `[tool.ruff] target-version` 改为 `"py311"`（注释同步）、`[tool.mypy] python_version`
      改为 `"3.11"`
      （验证：`grep -n "target-version\|python_version" pyproject.toml` 分别为 py311 / 3.11）
- [ ] 1.3 从 `[project].dependencies` 移除 `typing-extensions>=4.7.0`
      （验证：`grep -n "typing-extensions" pyproject.toml` 无输出；
      `python -c` 解析 `[project].dependencies` 得到 3 条）
- [ ] 1.4 运行 `uv lock` 更新 `uv.lock` 的 `requires-python`，并**逐块核对 diff**
      ——只允许 `requires-python` 与 `typing-extensions` 相关行变化
      （验证：`git diff uv.lock` 逐段检查；`uv lock --check` 通过；若出现无关依赖升级则恢复该条目后重跑）

## 2. 工具链与 CI（design D3）

- [ ] 2.1 `.github/workflows/tests.yml` 的矩阵改为 `python-version: ["3.11", "3.13"]`
      （三平台不变），确认安装步骤仍使用矩阵值、覆盖率产物名仍带 `matrix.python-version`
      （验证：`grep -n "python-version" .github/workflows/tests.yml`；
      矩阵含两档；`name:` 行与 artifact 名未硬编码版本）
- [ ] 2.2 核对其它 workflow 的 Python 版本引用，确认没有把门槛写死：`quality.yml`（静态检查）
      与 `release.yml` / `build.yml` / `docs.yml` / `codeql.yml` / `bench.yml` 保持 3.13，
      并在文档中把"测试矩阵"与"静态检查/发布"的版本口径分开表述
      （验证：`grep -rn "python-version" .github/workflows/` 输出与文档新增表述一致；
      改动仅限 `tests.yml` + 文档）

## 3. 门槛声明全量同步（design D4）

- [ ] 3.1 两份 README 的 badge 与门槛句：`README.md:11`（badge）、`:57`、`:181`；
      `README.zh.md:11`、`:54`、`:168`
      （验证：两文件 badge 为 `Python-3.11%2B`；`:57`/`:54` 与 `:181`/`:168` 写 3.11+
      ——顺带核对 `README.md:348` / `README.zh.md:327` 的"实测环境"句**未**被改）
- [ ] 3.2 仓库根与贡献者文档：`CONTRIBUTING.md:18,65`（门槛）与 `:29,75`（CI 版本表述）、
      `docs/CONTRIBUTING_MAINTAINER.md:35,345`（门槛）与 `:119,426`（CI 版本表述）、
      `docs/README.md:25`、`AGENTS.md:18`、`CLAUDE.md:24`
      （验证：门槛句全部为 3.11+；CI 句改为"测试矩阵 3.11 与 3.13、静态检查 3.13"；
      中英两半同步）
- [ ] 3.3 安装与元数据文档：`docs/install.md:7,11`、`docs/REPO_METADATA.md:63-64`、
      `.github/ISSUE_TEMPLATE/bug_report.md:21`
      （验证：三处均与 `>=3.11` 一致；`docs/REPO_METADATA.md` 的 classifier 说明改写为
      "声明支持的区间"而非"CI 验证过的版本"）
- [ ] 3.4 `.claude/` 下的指令文件：`agents/software-engineer.md:24`、
      `skills/python-syntax-review/SKILL.md:28`、`skills/architecture-review/SKILL.md:8`、
      `skills/cross-platform-review/SKILL.md:8,46`、`skills/architect-memory/SKILL.md:54`
      （验证：门槛句均为 3.11+；`agents/perf-guardian.md:20,60` 的**测量环境**句保持 3.13）
- [ ] 3.5 逐条核对 D4 的豁免清单未被改动：`bench/README.md:28`、`docs/benchmark.md:48,130`、
      `docs/MIGRATION.md:7`、`native/DECISION.md:36,148`、`CLAUDE.md:134,148`
      （验证：`git diff --stat` 中不出现这些文件的对应行变更；`git diff` 里这些文件的改动
      为零或与门槛无关）

## 4. 依据落盘（design D7）

- [ ] 4.1 `docs/DEVELOPMENT.md` 新增"Python 下界的依据"一节：下界（3.11）、扫描证据要点
      （PEP 604 于 44 个无 future import 的文件 ⇒ ≥3.10；唯一 3.11 硬依赖是测试里的 `tomllib`）、
      实跑证据（3.11.15 全量测试 1107 passed + 1 个 native 模块 skip；3.10.20 因 `tomllib`
      连收集都失败）、商业理由（下界决定能被哪些上游写进依赖）、以及
      "提高门槛 MUST 先写下依据"的约束
      （验证：该节含四条要点与依据指针；`docs/DEVELOPMENT.md` 行数增加且 md 渲染正常）
- [ ] 4.2 `docs/FAQ.md` 的"为什么要求 Python 3.13+"改为现答案：下界是 **3.11**、依据指向
      `DEVELOPMENT.md` 那一节、并说明 issue #124 已落地
      （验证：该问答不再出现"因为这是当前 pyproject.toml 里的 requires-python"式的循环回答；
      含 3.11 与依据链接）

## 5. 运行依赖清理联动（design D5）

- [ ] 5.1 文档中的依赖清单与计数：`docs/SECURITY_MODEL.md:36,93`（中英各一处，含计数
      "4" → "3"）、`docs/install.md:9`、`docs/security-supply-chain.md:39`
      （验证：四处均不再出现 `typing-extensions`；计数为 3 且与元数据一致）
- [ ] 5.2 `tests/test_security_supply_chain.py` 的依赖断言随移除更新（计数解析与依赖遍历）
      （验证：`pytest tests/test_security_supply_chain.py` 全绿；
      若断言硬编码了依赖名集合，逐一核对与 `pyproject.toml` 一致）

## 6. native 扩展的独立下界（design D6）

- [ ] 6.1 `native/pyproject.toml` 的 `requires-python` **保持 `>=3.13`**，补注释说明
      "可选扩展与主包下界解耦；CI 不覆盖本目录，故不做未验证的下调"
      （验证：该文件除注释外无值变更；注释含"独立于主包"与"未验证"两点理由）
- [ ] 6.2 在门槛文档中写明可选扩展的下界：`docs/install.md` 增一句（3.11 用户可装主包，
      原生加速扩展需要 3.13+，装不上是显式失败）
      （验证：`docs/install.md` 含该句，且与 `native/pyproject.toml` 的声明一致）

## 7. 机械守护（design D8）

- [ ] 7.1 扩展 `tests/test_doc_consistency.py`：以下界为真源断言
      ① `uv.lock` 的 `requires-python` 与 `pyproject.toml` 一致；
      ② `[tool.ruff] target-version`（`py3xx`）与 `[tool.mypy] python_version` 换算后等于下界；
      ③ `tests.yml` 的矩阵包含下界且三个平台都在；
      ④ 仓库内门槛式表述（`3.x+` / `>=3.x` / `Requires Python 3.x`）版本等于下界；
      ⑤ 测量环境式表述（含 `Measured on` / `实测` / `测得` 等环境词）**不被** ④ 误伤
      （验证：`pytest tests/test_doc_consistency.py` 全绿）
- [ ] 7.2 防"空跑"自检：④ 的正则必须命中合成违规样本（如 `Python 3.13+` 门槛句）、
      ⑤ 必须放过合成合法样本（如 `Measured on Python 3.13`），且门槛声明集合为空时报错
      （验证：合成样本断言通过；临时把正则改坏后该自检变红——注入验证见 8.4）
- [ ] 7.3 断言复跑于下界解释器：把 3.11 解释器上的全量测试纳入验证记录
      （验证：3.11 上 `pytest` 输出与 8.1 记录一致）

## 8. 验证与收尾

- [ ] 8.1 下界实跑：在 Python 3.11 上运行全量测试并留档（基线：1107 passed + 1 skip；
      3.13 上为 1119 passed，差额是本变更无关的可选扩展模块）
      （验证：两条命令的实际输出；3.11 上无 failed/error）
- [ ] 8.2 门禁：`ruff check zoo_framework tests` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` / 全量 `pytest`（3.13）不回归；`uv lock --check` 通过
      （验证：逐条命令输出）
- [ ] 8.3 文档站不回归：非 strict `mkdocs build` 退出码 0，链接告警数不高于基线 1 条
      （验证：构建输出的告警清单；`site/` 中 `install`、`FAQ`、`DEVELOPMENT` 页面为最新）
- [ ] 8.4 注入验证断言有牙齿：串行执行、逐次按 md5 还原，至少四处——
      ① `pyproject.toml` 的下界改回 `3.13`；② `uv.lock` 的 `requires-python` 改回；
      ③ `tests.yml` 矩阵删掉下界；④ 文档里塞回一句 `Python 3.13+` 门槛句；
      另加一处**反向**注入：把某句测量环境声明改成门槛式表述，确认 ⑤ 会红
      （验证：五处注入对应的断言各自变红，还原后 md5 与打桩前逐字节一致；
      脚本与备份留在 `/f/Python/zoo/.orca/tmp-bak/python-floor/`）
- [ ] 8.5 `openspec validate python-floor --strict` 0 警告；tasks 全勾；提交
      （`Closes #124`）+ 备份与 md5 核对
      （验证：validate 输出；commit 成功）
- [ ] 8.6 如实标注生效范围：门槛放宽只在**下一个发到 PyPI 的版本**上对外可见；
      README / 文档站的措辞合并到默认分支后可见；本变更只保证仓库内一致、
      CI 覆盖与依据落盘，SHALL NOT 声称"3.11 用户已经能装上"
      （验证：提交说明与最终汇报的表述与此一致）
