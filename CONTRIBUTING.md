# Contributing to Zoo Framework

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## 🇬🇧 English

Thanks for your interest. This project is maintained by one person on a best-effort
basis, so the guidance below is written to make a contribution land in as few round
trips as possible.

### Before you write code

Open an issue first if your change is more than a small fix. For anything touching
behaviour — the scheduler, the waiter, worker dispatch, the event pipeline, state
persistence — the project works **spec-first**: `openspec/specs/<capability>/spec.md` is
the authoritative statement of behaviour, and a change to behaviour is a change to a
spec. Agreeing on that in an issue before writing code avoids a PR that has to be
re-scoped.

Small fixes (typos, doc corrections, a missing test, a narrow bug with a clear cause) do
not need a pre-issued issue.

### Development setup

Python **3.13+** is required, and this matters in practice:

> **Use an explicit interpreter.** On some machines a bare `python` resolves to an
> unrelated older virtualenv that cannot import the package at all. Use `uv run`, or
> `.venv/Scripts/python.exe` on Windows / `.venv/bin/python` elsewhere.

```bash
git clone https://github.com/YearsAlso/zoo-framework.git
cd zoo-framework

uv sync                    # preferred; uv.lock is committed
# or: pip install -e ".[dev]"

pre-commit install         # installs the git hooks
pytest                     # 367 cases should pass
```

If `pytest` cannot import `zoo_framework`, you are almost certainly on the wrong
interpreter — check `python -c "import sys; print(sys.executable)"` before anything else.

### Branch strategy

`main` is the release branch. `dev` is the integration branch. **All pull requests target
`dev`.**

| Branch | Role |
|---|---|
| `main` | Release branch, and the repository's default branch on GitHub. Receives merges from `dev` only, at release time. |
| `dev` | Integration branch. Every feature/fix PR merges here. |
| `feat/*`, `fix/*`, `docs/*`, `refactor/*`, `test/*`, `chore/*` | Your work. Branch from `dev`, PR back into `dev`. |

Real examples from this repository's history: `fix/runtime-hardening`,
`fix/zfc-cli-contract`, `refactor/cli-package`.

```bash
git checkout dev
git pull origin dev
git checkout -b fix/zfc-worker-name-validation
```

> **Merging to `dev` or `main` publishes to PyPI.** The release workflow bumps the version
> and pushes a release on every push to those branches — a patch `-beta` for `dev`, a
> minor stable for `main`. Do not push to them directly; go through a PR, and expect a
> merge into `dev` to ship a beta.

### Commit messages

Conventional Commits. The format is:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types** — `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`, `perf`.

**Scope** is the affected area. Use the package or concern name: `worker`, `waiter`,
`core`, `event`, `fifo`, `reactor`, `statemachine`, `params`, `plugin`, `aop`, `zfc`,
`ci`, `readme`, `openspec`, `bench`.

Write the subject and body in Chinese, matching the existing history.

Real examples from this repository:

```
fix(ci): 修复 ruff format 漂移与跨平台用例对平台默认编码的依赖
fix(zfc): 校验脚手架命令的输入并修正产出归属
docs(readme): 重写定位说明、修正与实现不符之处，并补充 AI Agent 定位
docs(openspec): 同步 fix-worker-scheduling 的 delta spec 并归档
```

Reference issues in the footer (`Closes #123`, `Fixes #456`).

### Quality gates

These are what CI actually enforces, on Python 3.13 across ubuntu / windows / macos:

| Gate | Command | Enforced? |
|---|---|---|
| Lint | `ruff check zoo_framework` | ✅ hard fail |
| Format | `ruff format zoo_framework` | ✅ hard fail (drift is a failure) |
| Tests | `pytest` | ✅ hard fail |
| Coverage | `pytest --cov=zoo_framework --cov-report=term-missing --cov-fail-under=30` | ✅ hard fail at **30%** |
| Types | `mypy zoo_framework` | ⚠️ `continue-on-error` |
| Security | `bandit -r zoo_framework -c .bandit.yaml` | ⚠️ advisory |

Run all of them locally before pushing:

```bash
ruff check zoo_framework --fix
ruff format zoo_framework
mypy zoo_framework
pytest --cov=zoo_framework --cov-report=term-missing
pre-commit run --all-files
```

Note the coverage gate is **30%**, not a high number — clearing it is a floor, not a goal.
New logic should come with tests that pin the contract, not tests that raise the number.

### Tests

The suite lives in `tests/` (one file per concern: `test_worker.py`,
`test_worker_scheduling.py`, `test_scheduler_model.py`, `test_event.py`,
`test_state_machine.py`, …) with shared fixtures in `tests/conftest.py`.

```bash
pytest                                          # everything
pytest tests/test_worker.py::TestBaseWorker     # one class
pytest -m "not slow"                            # skip the slow tier
```

Available markers are `slow`, `integration` and `unit`, and `--strict-markers` is on — an
undeclared marker is an error, so register a new one in `pyproject.toml` before using it.

Two contracts in `BaseWorker` that are easy to get wrong in a test:

```python
from zoo_framework.workers import BaseWorker


def test_props_are_the_single_source_of_truth():
    # props is a required argument, and is the only source for these values
    worker = BaseWorker({"is_loop": True, "delay_time": 0.5})

    assert worker.is_loop is True  # attribute-style property — no call parens
    assert worker.delay_time == 0.5  # absent -> 0
    assert worker.run_timeout is None  # absent -> None


def test_base_execute_is_a_noop_and_run_propagates():
    worker = BaseWorker({})
    worker._execute()  # returns None; it does NOT raise
```

`is_loop` / `run_timeout` / `delay_time` are properties, not methods. Read them without
parentheses, and do not shadow them with instance attributes in a subclass.

To test schedule-related behaviour without real sleeping, override the wait
implementation through props instead of patching `time.sleep`:

```python
worker = BaseWorker({"delay_time": 5, "sleep_func": lambda _s: None})
```

### Spec-driven changes

Behaviour changes are recorded under `openspec/`:

```
openspec/
├── specs/<capability>/spec.md          # authoritative behaviour spec
└── changes/<id>/                       # proposal → design → spec deltas → tasks
    └── archive/<date>-<id>/            # completed changes land here
```

```bash
openspec validate --strict              # gates each change
```

Artifacts are written in Chinese (`openspec/config.yaml` pins zh-CN), while structural
headings and the `SHALL` / `MUST` keywords stay in English. If your change alters
behaviour, update the delta spec in the same PR — a code change whose spec delta is
missing is incomplete.

### Documentation contributions

Documentation is a first-class contribution here, and **doc/implementation drift is
treated as a defect** — a recent change was specifically "修正与实现不符之处" (correcting
things the docs said that the code did not do). When behaviour changes, the same PR should
update:

- `README.md` — the capability table and any snippet it shows
- `docs/*.md` — the relevant deep-dive
- docstrings — Google style (`Args:` / `Returns:` / `Raises:`)

Language conventions:

- **Comments, docstrings and `docs/` are written in Chinese.** Match that.
- **`README.md` is bilingual and the two halves must stay parallel** — if you change a
  section in one language, change its counterpart. Unequal halves are the most common
  defect in this file.

### Pull requests

Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md): what changed, whether tests were
run, whether there is a breaking change, whether docs were updated.

Review rules:

- CI must be green — `ruff` and `pytest` are the hard gates.
- Review comments are addressed on your own branch. Amending and force-pushing a PR branch
  is fine and keeps history readable; force-pushing a shared branch (`dev`, `main`) is not.
- If your change alters a documented contract, expect a request to update the docs and the
  spec delta. That is not a formality here.

### Good first issues

Issues labelled
[`good first issue`](https://github.com/YearsAlso/zoo-framework/labels/good%20first%20issue)
are scoped to be self-contained; [`help wanted`](https://github.com/YearsAlso/zoo-framework/labels/help%20wanted)
covers larger items that would benefit from a second pair of hands. The
[evolution tracking issue #32](https://github.com/YearsAlso/zoo-framework/issues/32) is the
index for planned work across the project's two target scenarios.

Good first contributions in this repository, roughly in order of difficulty:

1. A doc correction where the text and the code disagree — high value here, since drift is
   the defect this project most often fixes.
2. A missing or weak test for a contract that already exists.
3. A narrow bug fix with a clear reproduction.
4. Translating a section that exists in only one half of the bilingual README.

Comment on the issue and say you are taking it, so two people do not do the same work.

### Reporting bugs and proposing features

Use the GitHub issue templates. A bug report with a **minimal reproduction**, your Python
version and your OS is worth far more than a long description — the framework's whole
design premise is that a wrong input fails loudly, so the error text you get is usually the
fastest path to the cause.

Do not report security vulnerabilities in a public issue — see
[SECURITY.md](SECURITY.md).

### Code of Conduct

All participation is covered by [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

---

<a name="中文"></a>
## 🇨🇳 中文

感谢你的关注。项目由一个人维护，响应是尽力而为的，所以下面的内容是为了让你的贡献尽量
少走几个来回。

### 动手写代码之前

改动如果超过一个小修复，请先开 issue。凡是涉及行为的改动 —— 调度器、waiter、Worker
派发、事件管道、状态持久化 —— 本项目是**规范先行**的：`openspec/specs/<capability>/spec.md`
是行为的权威声明，改行为就是改规范。先在 issue 里把这件事谈清楚，能避免一个写完还要
重新划范围的 PR。

小修复（错别字、文档纠正、补一个测试、原因明确的窄接口 bug）不需要预先开 issue。

### 开发环境搭建

需要 Python **3.13+**，这一点在实际操作中很关键：

> **请使用明确的解释器。** 在某些机器上，裸 `python` 会解析到一个无关的旧虚拟环境，
> 那个环境**完全无法导入本包**。请使用 `uv run`，或 Windows 上的
> `.venv/Scripts/python.exe` / 其他平台上的 `.venv/bin/python`。

```bash
git clone https://github.com/YearsAlso/zoo-framework.git
cd zoo-framework

uv sync                    # 推荐；uv.lock 已入库
# 或：pip install -e ".[dev]"

pre-commit install         # 安装 git 钩子
pytest                     # 367 条用例应全部通过
```

如果 `pytest` 报无法导入 `zoo_framework`，几乎可以肯定你用错了解释器 —— 先跑一下
`python -c "import sys; print(sys.executable)"` 确认。

### 分支规范

`main` 是发版分支，`dev` 是集成分支。**所有 PR 都指向 `dev`。**

| 分支 | 职责 |
|---|---|
| `main` | 发版分支，也是 GitHub 上的默认分支。只在发版时接收来自 `dev` 的合并。 |
| `dev` | 集成分支。所有功能/修复 PR 都合并到这里。 |
| `feat/*`、`fix/*`、`docs/*`、`refactor/*`、`test/*`、`chore/*` | 你的工作分支。从 `dev` 切出，PR 回 `dev`。 |

本仓库历史中的真实例子：`fix/runtime-hardening`、`fix/zfc-cli-contract`、
`refactor/cli-package`。

```bash
git checkout dev
git pull origin dev
git checkout -b fix/zfc-worker-name-validation
```

> **合并进 `dev` 或 `main` 会发布到 PyPI。** 发版工作流会在每次推送到这两个分支时
> 自增版本并发布 —— `dev` 是补丁号 `-beta`，`main` 是次版本号稳定版。不要直接推这两个
> 分支，请走 PR，并且要知道合并进 `dev` 就意味着发一个 beta。

### 提交信息规范

采用约定式提交（Conventional Commits），格式为：

```
<type>(<scope>): <subject>

<body>

<footer>
```

**类型** —— `feat`、`fix`、`docs`、`style`、`refactor`、`test`、`chore`、`perf`。

**范围（scope）** 是受影响的区域，取包名或关注点：`worker`、`waiter`、`core`、`event`、
`fifo`、`reactor`、`statemachine`、`params`、`plugin`、`aop`、`zfc`、`ci`、`readme`、
`openspec`、`bench`。

标题与正文用中文写，与现有历史保持一致。

本仓库中的真实例子：

```
fix(ci): 修复 ruff format 漂移与跨平台用例对平台默认编码的依赖
fix(zfc): 校验脚手架命令的输入并修正产出归属
docs(readme): 重写定位说明、修正与实现不符之处，并补充 AI Agent 定位
docs(openspec): 同步 fix-worker-scheduling 的 delta spec 并归档
```

在 footer 里引用 issue（`Closes #123`、`Fixes #456`）。

### 质量门禁

以下是 CI 在 Python 3.13、ubuntu / windows / macos 三平台上真正执行的内容：

| 门禁 | 命令 | 是否强制 |
|---|---|---|
| Lint | `ruff check zoo_framework` | ✅ 硬失败 |
| 格式 | `ruff format zoo_framework` | ✅ 硬失败（格式漂移即失败） |
| 测试 | `pytest` | ✅ 硬失败 |
| 覆盖率 | `pytest --cov=zoo_framework --cov-report=term-missing --cov-fail-under=30` | ✅ 门禁为 **30%** |
| 类型 | `mypy zoo_framework` | ⚠️ `continue-on-error` |
| 安全 | `bandit -r zoo_framework -c .bandit.yaml` | ⚠️ 仅提示 |

推送前请全部本地跑一遍：

```bash
ruff check zoo_framework --fix
ruff format zoo_framework
mypy zoo_framework
pytest --cov=zoo_framework --cov-report=term-missing
pre-commit run --all-files
```

注意覆盖率门禁是 **30%**，不是一个高数字 —— 过线只是底线，不是目标。新逻辑应该配能钉住
契约的测试，而不是能抬高数字的测试。

### 测试规范

测试套件在 `tests/`，一个关注点一个文件（`test_worker.py`、`test_worker_scheduling.py`、
`test_scheduler_model.py`、`test_event.py`、`test_state_machine.py` 等），共享 fixture 在
`tests/conftest.py`。

```bash
pytest                                          # 全部
pytest tests/test_worker.py::TestBaseWorker     # 单个类
pytest -m "not slow"                            # 跳过慢速层
```

可用标记为 `slow`、`integration`、`unit`，且开启了 `--strict-markers` —— 未声明的标记会
直接报错，用新标记前先在 `pyproject.toml` 里注册。

`BaseWorker` 有两个容易在测试里写错的契约：

```python
from zoo_framework.workers import BaseWorker


def test_props_are_the_single_source_of_truth():
    # props 是必填参数，且是这些取值的唯一真源
    worker = BaseWorker({"is_loop": True, "delay_time": 0.5})

    assert worker.is_loop is True  # 属性式 property —— 不写调用括号
    assert worker.delay_time == 0.5  # 未声明时为 0
    assert worker.run_timeout is None  # 未声明时为 None


def test_base_execute_is_a_noop_and_run_propagates():
    worker = BaseWorker({})
    worker._execute()  # 返回 None，并不会抛异常
```

`is_loop` / `run_timeout` / `delay_time` 是 property 而非方法。读取时不要加括号，
子类中也不要用实例属性遮蔽它们。

要在不真实等待的前提下测试调度相关行为，请通过 props 替换等待实现，而不是去打补丁
`time.sleep`：

```python
worker = BaseWorker({"delay_time": 5, "sleep_func": lambda _s: None})
```

### 规范先行的改动（OpenSpec）

行为改动记录在 `openspec/` 下：

```
openspec/
├── specs/<capability>/spec.md          # 权威行为规范
└── changes/<id>/                       # 提案 → 设计 → 规范增量 → 任务
    └── archive/<date>-<id>/            # 已完成的改动归档于此
```

```bash
openspec validate --strict              # 每个改动都要过这道门
```

产出物用中文书写（`openspec/config.yaml` 固定为 zh-CN），而结构性标题与 `SHALL` / `MUST`
关键词保持英文。如果你的改动改变了行为，请在同一个 PR 里更新 delta spec —— 代码改了而
规范增量缺失，属于未完成的改动。

### 文档贡献

文档在本项目是一等贡献，并且**文档与实现不符会被当作缺陷处理** —— 近期有一个改动就是专门
「修正与实现不符之处」。行为变化时，同一个 PR 应当同步更新：

- `README.md` —— 能力表以及其中出现的任何代码片段
- `docs/*.md` —— 对应的深入文档
- docstring —— Google 风格（`Args:` / `Returns:` / `Raises:`）

语言约定：

- **注释、docstring 与 `docs/` 用中文书写。** 请保持一致。
- **`README.md` 是中英双语，两半必须保持平行** —— 你改了其中一种语言的一节，就要改对应的
  另一半。两半不对等是这份文件最常见的缺陷。

### PR 流程

请使用 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md)：变更描述、测试是否完成、是否有破坏性
变更、文档是否同步更新。

评审规则：

- CI 必须全绿 —— `ruff` 与 `pytest` 是硬性门禁。
- 评审意见在自己的分支上处理。对自己的 PR 分支做 amend 与 force push 是允许的，能让历史
  更干净；但对共享分支（`dev`、`main`）force push 不允许。
- 如果你的改动触及已文档化的契约，被要求补文档与规范增量是正常的。在这项目里那不算形式
  主义。

### Good First Issue

带 [`good first issue`](https://github.com/YearsAlso/zoo-framework/labels/good%20first%20issue)
标签的 issue 范围自足、适合上手；[`help wanted`](https://github.com/YearsAlso/zoo-framework/labels/help%20wanted)
是更需要人手的较大项。[演进追踪 issue #32](https://github.com/YearsAlso/zoo-framework/issues/32)
是项目两个目标场景下计划工作的索引。

本仓库中适合首次贡献的工作，大致按难度排列：

1. 文档与代码不一致处的纠正 —— 在这项目里价值很高，因为「漂移」正是本仓库最常修的缺陷。
2. 为已有但缺失或薄弱的契约补测试。
3. 有清晰复现步骤的窄接口 bug 修复。
4. 翻译双语 README 中只在一种语言里存在的那一节。

请在 issue 下留言认领，避免两个人做重复的事。

### 报告 Bug 与提出需求

请使用 GitHub 的 issue 模板。一份带有**最小复现**、Python 版本和操作系统的 Bug 报告，价值
远高于一段冗长的描述 —— 框架的设计前提就是「错误输入必须大声失败」，所以你拿到的报错文本
通常就是最快定位原因的路。

安全漏洞**不要**开公开 issue，请见 [SECURITY.md](SECURITY.md)。

### 行为准则

所有参与行为均受 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) 约束。
