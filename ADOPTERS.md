# 使用者 / Adopters

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## 🇬🇧 English

### Add yourself

If you use Zoo Framework — in production, in an internal tool, or as the base of something
you ship — add a row to the table below in a pull request. That is the entire process; there
is nothing to ask permission for.

A row needs three things:

| Column | What to put there |
|---|---|
| **Project or organisation** | A name and, ideally, a link a reader can open |
| **How it uses Zoo Framework** | One line: what the framework is doing for you |
| **Verifiable?** | Either a link a stranger can check (a public dependency file), or `not verifiable` |

A `not verifiable` row is accepted and stays labelled that way. An uncheckable claim is
still useful context — it just is not evidence, and this file does not pretend otherwise.

### Known users

| Project or organisation | How it uses Zoo Framework | Verifiable? |
|---|---|---|
| [`YearsAlso/zoo-code-agent`](https://github.com/YearsAlso/zoo-code-agent) — the maintainer's own repository, vendored into this tree at [`example/agent`](example/agent) | A minimal agent consumer, also used to validate framework requirements. Pins `zoo-framework==0.8.0` in its `pyproject.toml`, deliberately tracking a released version rather than the `dev` branch | ✅ **Verifiable** — the dependency declaration is in that repository's `pyproject.toml`. It is **not** a third party and **not** production evidence |
| The maintainer's private project | Uses the framework in production | ❌ **Not verifiable** — readers cannot check it, so it is listed as a disclosure, **not** as evidence |

### The honest gap

**There are currently no verifiable third-party adopters.** That is a gap in the record, not
a hidden one: it is also stated in the [FAQ](docs/FAQ.md), and this file exists precisely so
that the first real adopter has somewhere to land. If you are the first, the pull request is
welcome.

---

<a name="中文"></a>
## 🇨🇳 中文

### 把自己加进来

如果你在用 Zoo Framework——生产环境、内部工具，或者作为你发布的东西的地基——提一个 PR
把一行加到下面的表里。整个流程就这些，不需要先问谁同意。

一行需要三样东西：

| 列 | 写什么 |
|---|---|
| **项目或组织** | 名称，最好带一个读者点得开的链接 |
| **怎么用的** | 一句话：框架在你这里干什么 |
| **可核实？** | 要么给出陌生人能查的依据（公开的依赖声明文件），要么写"不可核实" |

"不可核实"的行也接受，并会一直带着这个标注。查不到的依据仍是背景信息——它只是不构成
证据，本文件不会假装它是。

### 已知使用者

| 项目或组织 | 怎么用的 | 可核实？ |
|---|---|---|
| [`YearsAlso/zoo-code-agent`](https://github.com/YearsAlso/zoo-code-agent)——维护者自己的仓库，以 [`example/agent`](example/agent) 形式固定在本仓库内 | 最小的 agent 消费方，同时用于验证框架需求。其 `pyproject.toml` 里钉住 `zoo-framework==0.8.0`，有意消费已发布版本而不跟随 `dev` 主干 | ✅ **可核实**——依赖声明就在该仓库的 `pyproject.toml` 里。它**不是**第三方，也**不是**生产使用证据 |
| 维护者自己的私有项目 | 在生产环境使用本框架 | ❌ **不可核实**——读者无法核对，因此仅作披露，**不**作为证据 |

### 这个诚实的空缺

**目前没有可核实的第三方使用者。** 这是记录上的空缺，不是被藏起来的空缺：同一句话也写在
[常见问题](docs/FAQ.md) 里，而这份文件存在的意义，正是让第一位真实使用者有地方落脚。
如果你是第一个，欢迎提 PR。
