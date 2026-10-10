# python-floor 任务清单

> 状态：全部完成（2026-10-10）。每条 `（验证：…）` 后附**实测结果**；
> 计划外但必需的工作登记在本文件末尾「9. 计划外但必需的工作」。

## 1. 元数据真源（design D1 / D2 / D5 / D9）

- [x] 1.1 `pyproject.toml` 的 `requires-python` 改为 `">=3.11"`，classifiers 改为列出该区间
      （3.11 / 3.12 / 3.13 / 3.14，保留既有的 3.14 声明），并把 `requires-python` 的注释
      指向 `docs/DEVELOPMENT.md` 的依据一节
      （验证：`grep -n "requires-python" pyproject.toml` 显示 `>=3.11`；
      `classifiers` 含 `Programming Language :: Python :: 3.11` 与 `:: 3.12`）
      **实测**：`pyproject.toml:21` = `requires-python = ">=3.11"`；classifiers 含
      3.11／3.12／3.13／3.14 四条，并注明"声明支持整段区间，实测集合见 tests.yml 矩阵"。
      **偏差**：design D7 写的是 `docs/DEVELOPMENT.md`，该文件在文档重构后不存在——依据一节
      落在 `docs/contributing/development.md`（即既有门槛断言已在解析的那份），注释指向它。
- [x] 1.2 `[tool.ruff] target-version` 改为 `"py311"`（注释同步）、`[tool.mypy] python_version`
      改为 `"3.11"`
      （验证：`grep -n "target-version\|python_version" pyproject.toml` 分别为 py311 / 3.11）
      **实测**：`pyproject.toml:121` = `target-version = "py311"`（带"跟随 requires-python"
      注释）；`[tool.mypy] python_version = "3.11"`。
      **连带**：target 降位后 ruff 不再触发 UP046／UP047（PEP 695 需 3.12+），三处旧 `noqa`
      变成"无用抑制"被 RUF100 判红——见第 9 节。
- [x] 1.3 从 `[project].dependencies` 移除 `typing-extensions>=4.7.0`
      （验证：`grep -n "typing-extensions" pyproject.toml` 无输出；
      `python -c` 解析 `[project].dependencies` 得到 3 条）
      **实测**：`pyproject.toml` 无 `typing-extensions`（仅留一行说明为何移除）；
      运行依赖 = click / pyyaml / python-dotenv，共 **3** 条。
- [x] 1.4 运行 `uv lock` 更新 `uv.lock` 的 `requires-python`，并**逐块核对 diff**
      ——只允许 `requires-python` 与 `typing-extensions` 相关行变化
      （验证：`git diff uv.lock` 逐段检查；`uv lock --check` 通过；若出现无关依赖升级则恢复该条目后重跑）
      **实测**：`uv.lock` 顶层 `requires-python = ">=3.11"`；diff 为 +288／−4，全部是
      "下界的后果"——条件依赖 `tomli`／`importlib-metadata`／`zipp`／`backports-tarfile`
      与 cp311／cp312 轮子条目，**没有任何既有包被升级**；`uv lock --check` 退出码 **0**。

## 2. 工具链与 CI（design D3）

- [x] 2.1 `.github/workflows/tests.yml` 的矩阵改为 `python-version: ["3.11", "3.13"]`
      （三平台不变），确认安装步骤仍使用矩阵值、覆盖率产物名仍带 `matrix.python-version`
      （验证：`grep -n "python-version" .github/workflows/tests.yml`；
      矩阵含两档；`name:` 行与 artifact 名未硬编码版本）
      **实测**：`:28` 矩阵 `["3.11", "3.13"]`、`os` 三平台不变；`:37` 安装步骤用
      `${{ matrix.python-version }}`；`:60` artifact 名含 `matrix.python-version`。
- [x] 2.2 核对其它 workflow 的 Python 版本引用，确认没有把门槛写死：`quality.yml`（静态检查）
      与 `release.yml` / `build.yml` / `docs.yml` / `codeql.yml` / `bench.yml` 保持 3.13，
      并在文档中把"测试矩阵"与"静态检查/发布"的版本口径分开表述
      （验证：`grep -rn "python-version" .github/workflows/` 输出与文档新增表述一致；
      改动仅限 `tests.yml` + 文档）
      **实测**：`grep -rn "python-version" .github/workflows/` = tests.yml 两档（矩阵）＋
      其余六个 workflow 均为单值 `3.13`（静态检查／发布／文档／bench，未动）。文档口径已分开：
      `CLAUDE.md:148`、`CONTRIBUTING.md:29`、`docs/CONTRIBUTING_MAINTAINER.md:119` 写明
      "测试矩阵跑 3.11 与 3.13，静态检查/发布仍是 3.13"。

## 3. 门槛声明全量同步（design D4）

- [x] 3.1 两份 README 的 badge 与门槛句：`README.md:11`（badge）、`:57`、`:181`；
      `README.zh.md:11`、`:54`、`:168`
      （验证：两文件 badge 为 `Python-3.11%2B`；`:57`/`:54` 与 `:181`/`:168` 写 3.11+
      ——顺带核对 `README.md:348` / `README.zh.md:327` 的"实测环境"句**未**被改）
      **实测**：两份 README 的 badge 均为 `Python-3.11%2B`；`README.md:57,181` 与
      `README.zh.md:54,168` 均为 3.11+，并链到依据一节；"实测环境"句
      （`README.md:349` / `README.zh.md:327`）逐字未动——现由机械断言守住（见 7.1 ⑤）。
- [x] 3.2 仓库根与贡献者文档：`CONTRIBUTING.md:18,65`（门槛）与 `:29,75`（CI 版本表述）、
      `docs/CONTRIBUTING_MAINTAINER.md:35,345`（门槛）与 `:119,426`（CI 版本表述）、
      `docs/README.md:25`、`AGENTS.md:18`、`CLAUDE.md:24`
      （验证：门槛句全部为 3.11+；CI 句改为"测试矩阵 3.11 与 3.13、静态检查 3.13"；
      中英两半同步）
      **实测**：门槛句 7 处全部 3.11+（`CONTRIBUTING.md:18,67`、
      `docs/CONTRIBUTING_MAINTAINER.md:35,345`、`docs/README.md:25`、`AGENTS.md:18`、
      `CLAUDE.md:24`）；CI 版本句 3 处（中英各半）均写明测试矩阵两档＋静态检查 3.13。
- [x] 3.3 安装与元数据文档：`docs/install.md:7,11`、`docs/REPO_METADATA.md:63-64`、
      `.github/ISSUE_TEMPLATE/bug_report.md:21`
      （验证：三处均与 `>=3.11` 一致；`docs/REPO_METADATA.md` 的 classifier 说明改写为
      "声明支持的区间"而非"CI 验证过的版本"）
      **实测**：`docs/install.md:7` 版本表 Python 行 = 3.11 起；`docs/REPO_METADATA.md:63-64`
      改为"classifiers 是声明支持区间，实测集合见 tests.yml"；issue 模板 = 3.11+。
- [x] 3.4 `.claude/` 下的指令文件：`agents/software-engineer.md:24`、
      `skills/python-syntax-review/SKILL.md:28`、`skills/architecture-review/SKILL.md:8`、
      `skills/cross-platform-review/SKILL.md:8,46`、`skills/architect-memory/SKILL.md:54`
      （验证：门槛句均为 3.11+；`agents/perf-guardian.md:20,60` 的**测量环境**句保持 3.13）
      **实测**：五处门槛句均为 3.11+（cross-platform-review 两处改为**指向矩阵**而非复述
      版本，避免第三份副本）；`agents/perf-guardian.md:20,60` 的测量环境句保持 3.13 未动。
- [x] 3.5 逐条核对 D4 的豁免清单未被改动：`bench/README.md:28`、`docs/benchmark.md:48,130`、
      `docs/MIGRATION.md:7`、`native/DECISION.md:36,148`、`CLAUDE.md:134,148`
      （验证：`git diff --stat` 中不出现这些文件的对应行变更；`git diff` 里这些文件的改动
      为零或与门槛无关）
      **实测**：`git diff --name-only` 中 `bench/README.md`、`docs/benchmark.md`、
      `docs/MIGRATION.md`、`native/DECISION.md`、`.claude/agents/perf-guardian.md`
      **全部为未改动**；`CLAUDE.md:134`（bench 复现所需的 3.13）逐字未动，`:148` 是
      3.2 明确要求改写的 CI 版本句（非豁免项）。

## 4. 依据落盘（design D7）

- [x] 4.1 `docs/DEVELOPMENT.md` 新增"Python 下界的依据"一节：下界（3.11）、扫描证据要点
      （PEP 604 于 44 个无 future import 的文件 ⇒ ≥3.10；唯一 3.11 硬依赖是测试里的 `tomllib`）、
      实跑证据（3.11.15 全量测试 1107 passed + 1 个 native 模块 skip；3.10.20 因 `tomllib`
      连收集都失败）、商业理由（下界决定能被哪些上游写进依赖）、以及
      "提高门槛 MUST 先写下依据"的约束
      （验证：该节含四条要点与依据指针；`docs/DEVELOPMENT.md` 行数增加且 md 渲染正常）
      **实测**：该节落在 `docs/contributing/development.md`（见 1.1 的偏差说明），含四条依据
      ＋复跑命令＋"门槛变了要一起改什么"表＋"两类不要跟着改"＋"提高门槛前必须写下依据"；
      mkdocs 构建后该页 83 KB、正文含 3.11 共 7 处。实跑数字按最终结果更新为
      **3.11.15：1112 passed + 1 skipped**（见 8.1；初稿记的 1107 是本变更前的基线）。
- [x] 4.2 `docs/FAQ.md` 的"为什么要求 Python 3.13+"改为现答案：下界是 **3.11**、依据指向
      `DEVELOPMENT.md` 那一节、并说明 issue #124 已落地
      （验证：该问答不再出现"因为这是当前 pyproject.toml 里的 requires-python"式的循环回答；
      含 3.11 与依据链接）
      **实测**：`docs/FAQ.md:88` 标题为"为什么要 Python 3.11+"，答案给扫描证据＋实跑结果＋
      依据链接，无循环回答；同页另一处"`uv.lock` 与 pyproject 不同步"的陈旧条目被换掉（第 9 节）。

## 5. 运行依赖清理联动（design D5）

- [x] 5.1 文档中的依赖清单与计数：`docs/SECURITY_MODEL.md:36,93`（中英各一处，含计数
      "4" → "3"）、`docs/install.md:9`、`docs/security-supply-chain.md:39`
      （验证：四处均不再出现 `typing-extensions`；计数为 3 且与元数据一致）
      **实测**：`docs/SECURITY_MODEL.md` 中英两处均为"运行时依赖（3 个）：click、pyyaml、
      python-dotenv"并加了"声明即使用"的判据；`docs/security-supply-chain.md` 依赖行改为
      三依赖＋行号区间（68–78）；`docs/install.md` 同步；四处均无 `typing-extensions`。
      该一致性由 `tests/test_security_supply_chain.py` 从 pyproject 动态推导守住。
- [x] 5.2 `tests/test_security_supply_chain.py` 的依赖断言随移除更新（计数解析与依赖遍历）
      （验证：`pytest tests/test_security_supply_chain.py` 全绿；
      若断言硬编码了依赖名集合，逐一核对与 `pyproject.toml` 一致）
      **实测**：该文件的依赖计数与名称**全部从 `pyproject.toml` 动态推导**（无硬编码 4），
      故无需改动即通过：`pytest tests/test_security_supply_chain.py` 19 passed
      （与 doc_consistency 合并跑为 193 passed）。

## 6. native 扩展的独立下界（design D6）

- [x] 6.1 `native/pyproject.toml` 的 `requires-python` **保持 `>=3.13`**，补注释说明
      "可选扩展与主包下界解耦；CI 不覆盖本目录，故不做未验证的下调"
      （验证：该文件除注释外无值变更；注释含"独立于主包"与"未验证"两点理由）
      **实测**：值仍为 `>=3.13`（diff 仅 +8 行注释）；注释写明"下界独立于主包""本目录没有
      CI 覆盖、本机没有 3.11 上编译 PyO3 的验证路径——跟降等于写一条无法证实的声明"，
      并说明 3.11／3.12 上安装会以显式错误结束。
- [x] 6.2 在门槛文档中写明可选扩展的下界：`docs/install.md` 增一句（3.11 用户可装主包，
      原生加速扩展需要 3.13+，装不上是显式失败）
      （验证：`docs/install.md` 含该句，且与 `native/pyproject.toml` 的声明一致）
      **实测**：`docs/install.md:16` 引用块写明"可选的原生执行扩展另有自己的下界
      （Python 3.13+）……装不上是显式失败"；`docs/VERSION_POLICY.md:85` 与
      `docs/contributing/development.md:64` 同口径。

## 7. 机械守护（design D8）

- [x] 7.1 扩展 `tests/test_doc_consistency.py`：以下界为真源断言
      ① `uv.lock` 的 `requires-python` 与 `pyproject.toml` 一致；
      ② `[tool.ruff] target-version`（`py3xx`）与 `[tool.mypy] python_version` 换算后等于下界；
      ③ `tests.yml` 的矩阵包含下界且三个平台都在；
      ④ 仓库内门槛式表述（`3.x+` / `>=3.x` / `Requires Python 3.x`）版本等于下界；
      ⑤ 测量环境式表述（含 `Measured on` / `实测` / `测得` 等环境词）**不被** ④ 误伤
      （验证：`pytest tests/test_doc_consistency.py` 全绿）
      **实测**：新增 5 条断言（①②合为 `test_python_floor_is_single_source`、③
      `test_ci_matrix_covers_floor_and_platforms`、④ `test_floor_claims_equal_the_floor`、
      ⑤ `test_environment_claims_are_not_reformulated_as_floor_claims`、自检见 7.2）。
      ④ 的扫描集 = `.claude/`＋`.github/`＋`docs/` 文本＋仓库根关键文件（116 个文件），
      实测命中 **27** 条门槛陈述、覆盖 **20** 个文件；③ 的"三平台"与"下界＋开发解释器
      各跑一次"都从 `tests.yml`／`.python-version` 推导，不写死版本号。
      `pytest tests/test_doc_consistency.py` = 174 passed。
- [x] 7.2 防"空跑"自检：④ 的正则必须命中合成违规样本（如 `Python 3.13+` 门槛句）、
      ⑤ 必须放过合成合法样本（如 `Measured on Python 3.13`），且门槛声明集合为空时报错
      （验证：合成样本断言通过；临时把正则改坏后该自检变红——注入验证见 8.4）
      **实测**：`test_floor_claim_scanner_has_teeth` 用 4 条违规样本（断言**检出的版本号**
      等于样本里的版本，防止捕获组写错）＋ 7 条合法样本（含裸 `Python 3.13`、
      `pyyaml>=6.0` 依赖 pin、`maturin>=1.0` 约束）；另设"这些文件 MUST 陈述门槛"清单
      （10 个文件，检不出即报错）防扫描范围退化；豁免清单 4 条须"仍然命中"，否则报"豁免腐烂"。
      注入 ⑥ 把 `+` 从正则里去掉后该自检变红（见 8.4）。
- [x] 7.3 断言复跑于下界解释器：把 3.11 解释器上的全量测试纳入验证记录
      （验证：3.11 上 `pytest` 输出与 8.1 记录一致）
      **实测**：3.11.15 上全量 3 连跑结果与 8.1 一致（1112 passed + 1 skipped ×3），
      新增的 5 条断言在下界解释器上同样通过。

## 8. 验证与收尾

- [x] 8.1 下界实跑：在 Python 3.11 上运行全量测试并留档（基线：1107 passed + 1 skip；
      3.13 上为 1119 passed，差额是本变更无关的可选扩展模块）
      （验证：两条命令的实际输出；3.11 上无 failed/error）
      **实测**：3.11.15（Windows）：`1112 passed, 1 skipped` 连续 3 次
      （`22.6s / 22.6s / 22.4s`，日志 `py311-final.log`）；3.13.14：`1124 passed`
      （`py313-final.log`）。差额 11 条 = 只在 3.13 装得上的可选扩展模块用例。
      首跑曾出现 1 failed —— 是**既有**计时用例在 Windows 3.11 上的时钟粒度抖动，
      已按用户选定的方案修正（见第 9 节），修后 20/20 稳定。
- [x] 8.2 门禁：`ruff check zoo_framework tests` / `ruff format --check zoo_framework` /
      `mypy zoo_framework` / 全量 `pytest`（3.13）不回归；`uv lock --check` 通过
      （验证：逐条命令输出）
      **实测**：`ruff check zoo_framework tests` exit 0；`ruff format --check zoo_framework`
      = 107 files already formatted；`mypy zoo_framework` = Success, 107 files；全量 pytest
      （3.13）= 1124 passed；`uv lock --check` exit 0；另：`bandit 1.9.4`（与 CI 同版）
      exit 0。
- [x] 8.3 文档站不回归：非 strict `mkdocs build` 退出码 0，链接告警数不高于基线 1 条
      （验证：构建输出的告警清单；`site/` 中 `install`、`FAQ`、`DEVELOPMENT` 页面为最新）
      **实测**：`mkdocs build` exit 0；链接告警恰好 **1** 条（`BRANCHING.md → ../CONTRIBUTING.md`，
      即既有基线 GFI-2）；`site/install/`、`site/FAQ/`、`site/contributing/development/`
      三页已生成且正文含 3.11（分别 2／7／7 处）。griffe 告警为既有（--strict 始终红的原因）。
- [x] 8.4 注入验证断言有牙齿：串行执行、逐次按 md5 还原，至少四处——
      ① `pyproject.toml` 的下界改回 `3.13`；② `uv.lock` 的 `requires-python` 改回；
      ③ `tests.yml` 矩阵删掉下界；④ 文档里塞回一句 `Python 3.13+` 门槛句；
      另加一处**反向**注入：把某句测量环境声明改成门槛式表述，确认 ⑤ 会红
      （验证：五处注入对应的断言各自变红，还原后 md5 与打桩前逐字节一致；
      脚本与备份留在 `/f/Python/zoo/.orca/tmp-bak/python-floor/`）
      **实测**：脚本 `/f/Python/zoo/.orca/tmp-bak/python-floor/inject.py`，日志 `inject.log`——
      **6 处**（上述五处＋7.2 要求的"把门槛正则改坏"）**全部命中目标断言**，且每处还原后
      md5 与注入前一致（6/6）。目标断言依次为 `test_python_floor_is_single_source`（①与②）、
      `test_ci_matrix_covers_floor_and_platforms`（③）、`test_floor_claims_equal_the_floor`
      （④）、`test_environment_claims_are_not_reformulated_as_floor_claims`（⑤反向）、
      `test_floor_claim_scanner_has_teeth`（⑥反向）。判红不只看退出码，还要求**目标节点名**
      出现在失败输出里，避免"别的断言红了"冒充。
- [x] 8.5 `openspec validate python-floor --strict` 0 警告；tasks 全勾；提交
      （`Closes #124`）+ 备份与 md5 核对
      （验证：validate 输出；commit 成功）
      **实测**：`openspec validate python-floor --strict` = valid（0 警告）；本文件全勾；
      改动前的原文件备份 33 个在 `/f/Python/zoo/.orca/tmp-bak/python-floor-apply/`
      （`files.txt` + `md5-before.txt`，备份副本自身按 md5 核对 **33/33 一致**）；
      提交带 `Closes #124`。
- [x] 8.6 如实标注生效范围：门槛放宽只在**下一个发到 PyPI 的版本**上对外可见；
      README / 文档站的措辞合并到默认分支后可见；本变更只保证仓库内一致、
      CI 覆盖与依据落盘，SHALL NOT 声称"3.11 用户已经能装上"
      （验证：提交说明与最终汇报的表述与此一致）
      **实测**：提交说明与收尾汇报均按此口径表述（当前 PyPI 上的版本仍是门槛 3.13 的构建；
      本分支只改仓库内声明、工具链、CI 矩阵与文档，未发布）。

## 9. 计划外但必需的工作（如实登记）

以下四项均**不在** proposal／design／本清单的原定范围内，但为让门禁通过或让声明为真而必须做；
均在收尾汇报中单独列出，不做静默吸收。

- [x] 9.1 **ruff 的 UP046／UP047 抑制失效**（1.2 的直接后果）：`target-version` 降到
      `py311` 后 ruff 不再要求 PEP 695 写法（该语法需 3.12+），
      `zoo_framework/core/params_path.py`、`zoo_framework/fifo/base_fifo.py`、
      `zoo_framework/utils/thread_safe_dict.py` 里三处 `# noqa: UP046/UP047` 被 RUF100
      判为"无用抑制"，`ruff check` 由绿转红。处置：删掉三处 `noqa`，并把原注释
      （"ruff 要求 PEP 695、而 pre-commit 钉的 mypy 1.7.1 不支持，两工具要求相反"）
      改写为现状——**下界是 3.11，PEP 695 本就不可用，`Generic`／`TypeVar` 是唯一合法写法**；
      同时留下"若把门槛抬到 3.12+，该冲突会回来，须先升级 mypy"的提示。
      `ruff format` 因此把 `param` 的签名收成一行。验证：`ruff check zoo_framework tests`
      exit 0、`ruff format --check zoo_framework` 107 文件已格式化、mypy 0 error。
- [x] 9.2 **既有时限断言在 Windows 3.11 上抖动**（用户选定"放宽时间余量"方案）：
      `tests/test_execution_time.py` 的 `TestEventExpiryTimeBase` 用"时限 0.05 + 睡眠 0.06"
      建立"已超时"前置；Windows 上 3.11／3.12 的 `time.monotonic()` 粒度约 15.6 ms，
      实测增量可能是 46.8 ms（量化到 3 个 tick）——**比时限还小**，断言随相位偶发翻红
      （直接复现 3/20 次、类级 pytest 复跑 1/12 次、首次全量跑 1 次；3.13 上 0/20）。
      处置：时限改 0.01 s、等待改 0.2 s（余量 0.19 s = tick 的 12 倍），并把规则与实测数字
      写成用例上方的注释，同时在 `docs/contributing/development.md` 的「Python 下界的依据」
      里留档。验证：同类用例在 3.11 上 **20 连跑 0 次翻红**；3.11 全量 3 连跑全绿。
- [x] 9.3 **两处关于锁文件的陈旧陈述**（枚举之外的实况错误）：`docs/install.md` 与
      `docs/FAQ.md` 原写"`uv.lock` 与 `pyproject.toml` 不同步（issue #115）"，但
      `uv lock --check` 在改动前后均退出 0——该说法与实况不符。处置：改写为"锁文件在同步
      状态；改动依赖后跑 `uv lock`，再以 `uv lock --check` 复核"；FAQ 的第二条坑位换成
      "用错解释器（工作树里的 3.9 `venv/` 装不上）"。
- [x] 9.4 **`distutils` 旧说法因门槛下降而变假**：`CLAUDE.md`、`docs/contributing/structure.md`
      （中英各一处）原写"`setup.py` 导入 `distutils`，而 `distutils` 在本项目支持的所有
      Python 上都不存在"——门槛降到 3.11 后该句不再成立（3.11 仍带 `distutils`）。处置：
      三处改写为"它在本项目**当时**发布所支持的解释器（门槛当时为 3.13）上从来不可能工作，
      且已移除"。属"文档同改"义务，非新增范围。
- [x] 9.5 **门槛陈述的枚举之外站点**（design D4 的清单不全）：除清单列出的文件外，实测还需
      同步 `llms.txt`（2 处）、`docs/VERSION_POLICY.md`、`docs/tutorial/01-quickstart.md`、
      `docs/contributing/roadmap.md`（陈旧 `>=3.13` 引用）、`docs/contributing/structure.md`、
      `.claude/skills/cross-platform-review/SKILL.md` 等。按 D4 的同一判据逐处处置；
      7.1 ④ 的扫描集（116 个文件）已覆盖这些位置，防止再次漏改。
      `.python-version`（3.13）**不是**门槛，是开发环境解释器——已在依据一节写明，
      且 7.1 ③ 用它（而非写死的版本号）表达"矩阵 = 下界 + 开发解释器"。
