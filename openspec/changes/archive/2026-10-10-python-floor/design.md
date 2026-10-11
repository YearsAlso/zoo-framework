## Context

门槛当前由五处分别声明，彼此没有机械约束（动机与实测数据见 `proposal.md`）：

| 位置 | 现值 |
|---|---|
| `pyproject.toml:17` `requires-python` | `>=3.13` |
| `pyproject.toml:53-54` classifiers | 3.13、3.14 |
| `pyproject.toml:111` `[tool.ruff] target-version` | `py313` |
| `pyproject.toml:206` `[tool.mypy] python_version` | `3.13` |
| `uv.lock:3` `requires-python` | `>=3.13` |
| `.github/workflows/tests.yml:24` | `["3.13"]` × ubuntu/windows/macos |

约束（本仓库既有事实，决定改动面）：

- **没有任何运行时版本守卫**——`zoo_framework/__init__.py` 与全包无 `sys.version_info` 分支，因此下界调整不涉及一行框架代码。
- **门槛声明与"测量环境声明"混用同一个字符串**：`bench/README.md:28`、`docs/benchmark.md:48,130`、`docs/MIGRATION.md:7`、`native/DECISION.md:36`、`README.md:348`、`CLAUDE.md:134` 等处的 3.13 是"当时在哪个解释器上测的"，不是门槛。
- **已有三道机械约束可复用**：`tests/test_doc_consistency.py`（文档门槛声明 vs pyproject）、`tests/test_security_supply_chain.py:338`（解析文档里的"运行时依赖 (N)"计数）、`tests/test_native_extension.py:24`（`pytest.importorskip`，扩展缺失时整模块 skip）。
- 运行时依赖的**新版本**下界：`click` ≥3.10、`python-dotenv` ≥3.10、`pyyaml` ≥3.8、`typing-extensions` ≥3.9 —— 都不高于本次候选下界。
- `native/pyproject.toml:9` 有**独立**的 `requires-python = ">=3.13"`；没有任何 workflow 覆盖 `native/`。

## Goals / Non-Goals

**Goals:**

- 下界落在"实测可行 + 零适配成本"的最低点，并把**依据**落盘（可复现、可复核）。
- 让 `requires-python`、锁文件、工具链 target、CI 矩阵、文档门槛声明**同源**；把"门槛漂移"变成 CI 能红的缺陷，而不是下一轮审计才发现。
- 把"门槛声明"与"测量环境声明"的判别规则写进规格，防止下一次降低门槛时把 bench 记录一起改假。

**Non-Goals:**

- 不支持 3.10（需要为测试引入 `tomli` 或条件导入，等于把门槛成本换成依赖成本）。
- 不改 `native/` 的下界值（保持 3.13），也不为它新增 CI 构建。
- 不改任何对外 API、配置键、持久化格式；不引入兼容层库。
- 不改写 bench 测量环境记录、不改 `docs/MIGRATION.md` 的报错取材环境。

## Decisions

### D1 下界取 3.11 —— 商业理由与实测证据

**扫描证据（174 个 Python 文件，`proposal.md` 的表）**：PEP 695 泛型/别名 0 处；`typing` 新名字（`Self` / `Never` / `override` / `TypeIs`）0 处；3.12/3.13 专属标准库 API 0 处；`match` 语句 0 处。唯一的 3.11 硬依赖是 `tests/test_security_supply_chain.py:19` 的 `tomllib`。硬性下界的真正来源是 **44 个文件**在没有 `from __future__ import annotations` 的情况下使用 PEP 604 注解（例：`zoo_framework/cli/scaffold.py:46`、`zoo_framework/core/adaptive/policy.py:39`）——注解在 import 期求值，故 **≥3.10**。

**实跑证据（本 worktree，非推断）**：

| 解释器 | 结果 |
|---|---|
| 3.11.15 | **1107 passed**，1 个模块 skip（`tests/test_native_extension.py` 的 `importorskip`：可选 Rust 扩展未为该解释器编译）。与版本无关：该模块在 3.13 上被收集到 12 个用例，1107 + 12 = 1119 = 3.13 的收集数，两侧自洽 |
| 3.10.20 | 1073 passed；`tests/test_security_supply_chain.py` 与 `tests/test_governance_consistency.py` **收集失败**（`ModuleNotFoundError: tomllib`） |

**商业理由（issue #124 明确要求在 design 中写出，不只是技术可行性）**：下界决定本框架能被哪些上游写进依赖。3.11 一次放开 3.11 与 3.12 两个仍在生产中的版本带，而它是零适配成本的最低点；再降到 3.10 需要给测试引入 `tomli` 依赖或条件导入——那等于把"门槛成本"换成"依赖成本"并让最老的受支持版本上跑不到供应链门禁，与 issue 的"不要让适配成本失控"相冲突。

**替代方案**：3.12（多覆盖的只有 3.12 一档，商业收益远小于 3.11，而适配成本相同）；3.10（见上）；维持 3.13（实测并不存在"挡住的实现"，写不出可信的阻碍说明，与 issue 的商业理由直接冲突）。

### D2 静态检查工具的 target 跟随下界

`[tool.ruff] target-version` → `py311`、`[tool.mypy] python_version` → `3.11`。

理由：`target-version` 决定 ruff 允许哪些语法、`python_version` 决定 mypy 按哪个标准库存根检查。"能在 3.11 上跑"与"按 3.11 检查"必须是同一件事，否则有人写下 3.12+ 语法时本地与静态检查都不会拦住，只有 CI 的下界作业会红——属于事后发现。

**替代方案**：保持 `py313` 靠 CI 兜底（同上，事后发现）；只改 mypy 不改 ruff（留下语法侧缺口）。

### D3 CI 矩阵 = `["3.11", "3.13"]` × 三平台

6 个测试作业：下界在 ubuntu/windows/macos 各跑一次完整套件（规格新增 scenario 的硬要求），3.13 保留是因为它是当前唯一有实测数据与 bench 基线背书的版本。

**替代方案**：下界只在 ubuntu（违反规格）；加入 3.12（不带来额外信息，作业数 +3）；加入 3.14（本次不扩范围——见 Risks 的既存未证实声明）。

### D4 两类版本声明的判别规则（规格新增约束的落地口径）

| 类型 | 触发词 | 处置 |
|---|---|---|
| **门槛声明**（要求/需要/支持/前提） | `要求` / `需要` / `Requires` / `required` / `3.13+` / `>=3.13` | MUST 跟随 `requires-python`，本变更全量改写 |
| **测量环境声明**（实测/测得/在该版本上取得） | `实测` / `测得` / `Measured on` / `measured on` / `报错原文…上执行` | MUST NOT 改写（改掉即假话）；本变更逐条豁免并加断言 |

豁免清单（逐条核过）：`bench/README.md:28`、`docs/benchmark.md:48,130`、`docs/MIGRATION.md:7`、`native/DECISION.md:36,148`、`README.md:348`、`README.zh.md:327`、`CLAUDE.md:134,148`、`.claude/agents/perf-guardian.md:20,60`。

### D5 移除 `typing-extensions`（BREAKING）

全仓 0 处 import，却被声明为运行依赖，并被 4 处文档计入“运行时依赖 4 个”。联动点：`docs/SECURITY_MODEL.md:36,93`、`docs/install.md:9`、`docs/security-supply-chain.md:39`，以及 `tests/test_security_supply_chain.py:338`（解析计数）与 `:100`（遍历依赖列表）。三者必须同改，否则门禁红。

**替代方案**：保留（文档继续声称一个无人使用的依赖）；拆独立 issue（用户已选择本次一并处理——它与"门槛为什么这么高"同源：都是历史兼容尝试未清理的残留）。

### D6 `native/` 保持自己的 3.13 下界

CI 完全不覆盖 `native/`，本机也没有"在 3.11 上编译 PyO3 扩展"的验证路径；跟降等于新增一条无法证实的声明——正是本仓库正在治的病。改为：值不动，在 `native-task-execution` 规格里写明"扩展下界独立于主包"，并在文档标注可选扩展的下界。代价是 3.11 用户装扩展会在安装期显式失败（符合规格新增 scenario）。

**替代方案**：跟降到 3.11（未验证）；跟降并给它加 CI 构建（扩范围 + Rust 编译成本）。

### D7 依据落盘位置

`docs/DEVELOPMENT.md` 新增一节（"Python 下界的依据"），写出：下界、扫描与实跑证据、商业理由、以及"提高门槛必须先把依据写下来"。`docs/FAQ.md` 现有的"为什么要求 Python 3.13+"改为指向该节并给出结论。

**替代方案**：写进 `docs/ARCHITECTURE.md`（该文件讲分层与并发机制，与"门槛/生态"主题不搭）。

### D8 机械守护：扩展 `tests/test_doc_consistency.py`

- 真源 = `pyproject.toml` 的 `requires-python`；据此断言 `tool.ruff.target-version`、`tool.mypy.python_version`、`uv.lock` 的 `requires-python`、`tests.yml` 矩阵同源。
- 门槛声明扫描：对仓库中的门槛式表述（`3.x+` / `>=3.x` / `Requires Python 3.x`）断言版本等于下界；命中 D4 判别规则中的环境词则豁免。
- **防"空跑"**：用合成样本自检——已知违规样本（如 `Python 3.13+` 门槛句）必须被检出、合法样本（`Measured on Python 3.13`）不被误伤；扫描名单为空时报错。（做法与 `tests/test_contributor_ramp.py` 的三条防空跑自检一致。）

### D9 `uv.lock` 的更新纪律

改动 `pyproject.toml` 后运行 `uv lock`，再 `git diff uv.lock` **逐块核对**：只允许出现 `requires-python` 与 `typing-extensions` 相关行；若顺带升级了任何依赖版本，说明解析被重新求解，需把无关条目恢复并按 `uv lock --check` 复核。依据：本仓库曾出现"本地工具版本 ≠ CI 版本"的取数事故，锁文件的静默升级会让"只降门槛"变成"顺手升级依赖"。

## Risks / Trade-offs

- **支持面变宽 ⇒ 维护面变宽** → 缓解：CI 下界作业即刻暴露 3.11 上的破绽；`target-version` 与 `python_version` 同步收紧，让越界语法在本地就被拦。
- **未来某个依赖抬高自身下界**（如 click 新版本要求 3.12）→ 锁文件同步会在 3.11 上拒绝；缓解：CI 下界作业会红，用户侧 `>=` 下限仍可解析到旧版本。
- **classifiers 仍声称 3.14，而 CI 不跑 3.14** → 这是本变更**之前就存在**的未证实声明（`docs/REPO_METADATA.md:63` 只解释了"3.14 用户能找到包"）。本次不改；文档口径改为明确区分"声明支持的区间"与"CI 实测的版本集合"，避免读者误以为 3.14 被验证过。
- **bench / 迁移指南的数据仍来自 3.13** → 不得据此声称 3.11 上性能等同；缓解：D4 的豁免清单 + 断言。
- **门槛声明散落 12+ 处，漏改风险高** → 缓解：D8 的机械断言 + 逐条 grep 核对（任务清单里给出清单）。
- **移除运行依赖改变了安装树**（对极少数依赖传递引入 `typing_extensions` 的用户不再自动获得它）→ 缓解：写进提交说明与 CHANGELOG 式说明，标注为 BREAKING 级别的元数据变更。

## Migration Plan

1. 元数据真源：`pyproject.toml`（`requires-python` / classifiers / ruff / mypy / 依赖）→ `uv lock`（D9 核对）。
2. 工具链与 CI：`tests.yml` 矩阵；`quality.yml` 保持 3.13（静态检查单版本即可），文档同步为"测试矩阵跑 3.11 与 3.13、静态检查跑 3.13"。
3. 文档：门槛声明按 D4 全量改写，环境声明逐条豁免；`docs/DEVELOPMENT.md` 写依据，`docs/FAQ.md` 重写答案。
4. 测试：扩展 `tests/test_doc_consistency.py`（D8）、更新 `tests/test_security_supply_chain.py` 的依赖计数断言。
5. 验证：3.11 与 3.13 两个解释器各跑一次全量测试；`uv lock --check`；非 strict `mkdocs build` 不新增告警。

**回滚**：改回 `requires-python` 与 CI 矩阵两处即可（无数据迁移、无 API 变更、无持久化格式变化）。

**生效范围**：门槛放宽要等**下一个发布到 PyPI 的版本**才对外可见；README / 文档站的措辞合并到默认分支后可见。本变更只保证仓库内一致与 CI 覆盖，不声称"3.11 用户已经能装上"。

## Open Questions

- **3.14 的 classifier 与 CI 要不要对齐**（既存未证实声明，本次不扩范围）：留给后续 issue——要么把 3.14 加进矩阵，要么收紧 classifier。不影响本变更的规格、方案与任务拆分。
- **是否进一步降到 3.10**（需要 `tomli` 或条件导入）：本次已按 issue 的优先目标定在 3.11；若日后生态数据表明 3.10 人群仍大，可按 D1 的同一套证据流程重新评估。
