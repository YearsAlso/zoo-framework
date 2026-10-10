# Contributing to Zoo Framework

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## 🇬🇧 English

> **Small changes do not need paperwork.** Spelling, documentation, example and comment fixes
> need **no** OpenSpec proposal and no prior issue — just open the pull request. Changes to
> externally observable behaviour, compatibility or a data format are the ones that should
> have a proposal first. Complete spec:
> [`docs/CONTRIBUTING_MAINTAINER.md`](docs/CONTRIBUTING_MAINTAINER.md).

### 1. Set up and run the tests

Python **3.11+**:

```bash
git clone https://github.com/YearsAlso/zoo-framework.git && cd zoo-framework
pip install -e ".[dev]"    # or: uv sync --extra dev
pre-commit install         # git hooks
pytest                     # full suite; add a path to run a single file while you work
```

If `pytest` cannot import `zoo_framework` you are on the wrong interpreter — check
`python -c "import sys; print(sys.executable)"`. CI runs `ruff` + `pytest` + `mypy` +
`bandit` on Python 3.11 and 3.13 across ubuntu / windows / macos; green CI is the merge bar.
(3.11 is the floor declared in `pyproject.toml`; the matrix lives in
`.github/workflows/tests.yml`.)

### 2. Send the pull request

Branch off `dev` and open the PR **into `dev`** — `main` only takes merges from `dev` at
release time, and a merge into `dev` publishes a `-beta` release automatically:

```bash
git checkout dev && git pull origin dev && git checkout -b fix/your-fix
```

Use the [PR template](.github/PULL_REQUEST_TEMPLATE.md).

### 3. Ask — and what you get back

Open a [GitHub issue](https://github.com/YearsAlso/zoo-framework/issues) — there is no chat
server and no mailing list. A report with a minimal reproduction, your Python version and
your OS gets answered fastest. Security problems go to the private channel in
[SECURITY.md](SECURITY.md), never a public issue.

A small pull request or a clear report gets a first reply **within 7 days** (the authority,
including the security timeline, is [MAINTAINERS.md](MAINTAINERS.md)). Contributors are
listed in [CONTRIBUTORS.md](CONTRIBUTORS.md); for a scoped 15–60 minute first task see
[`docs/GOOD_FIRST_ISSUES.md`](docs/GOOD_FIRST_ISSUES.md).

---

<a name="中文"></a>
## 🇨🇳 中文

> **小改动不用走流程。** 拼写、文档、示例、注释类的修正**不需要** OpenSpec 提案、也不需要先开
> issue —— 直接开 PR。改动涉及**外部可观察行为、兼容性或数据格式**时，才需要先写提案。
> 完整规范：[`docs/CONTRIBUTING_MAINTAINER.md`](docs/CONTRIBUTING_MAINTAINER.md)。

### 1. 搭环境、跑测试

需要 Python **3.11+**：

```bash
git clone https://github.com/YearsAlso/zoo-framework.git && cd zoo-framework
pip install -e ".[dev]"    # 或：uv sync --extra dev
pre-commit install         # 装 git 钩子
pytest                     # 跑全量；开发时加个路径可以只跑一个文件
```

`pytest` 报无法导入 `zoo_framework` 几乎肯定是解释器用错了 —— 跑
`python -c "import sys; print(sys.executable)"` 确认。CI 在 Python 3.11 与 3.13 上跑
`ruff` + `pytest` + `mypy` + `bandit`（ubuntu / windows / macos 三平台），**CI 全绿是合并
门槛**（3.11 是 `pyproject.toml` 声明的下界，矩阵见 `.github/workflows/tests.yml`）。

### 2. 提 PR

从 `dev` 切分支，PR **指向 `dev`** —— `main` 只在发版时接收 `dev` 的合并，而合并进 `dev`
会自动发一个 `-beta` 版本：

```bash
git checkout dev && git pull origin dev && git checkout -b fix/your-fix
```

用 [PR 模板](.github/PULL_REQUEST_TEMPLATE.md)。

### 3. 怎么问，以及你能得到什么

开 [GitHub issue](https://github.com/YearsAlso/zoo-framework/issues) —— 本仓库没有聊天群、
没有邮件列表。附上最小复现、Python 版本与操作系统的问题，得到答复最快。安全问题走
[SECURITY.md](SECURITY.md) 里的私密渠道，**不要**开公开 issue。

小的 PR 或清晰的报告会在 **7 天内得到首次回应**（权威说明含安全响应时限，见
[MAINTAINERS.md](MAINTAINERS.md)）。贡献者名单在 [CONTRIBUTORS.md](CONTRIBUTORS.md)；
想从一件 15–60 分钟的小活开始，看 [`docs/GOOD_FIRST_ISSUES.md`](docs/GOOD_FIRST_ISSUES.md)。
