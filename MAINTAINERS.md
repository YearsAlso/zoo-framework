# 维护者 / Maintainers

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## 🇬🇧 English

### Maintainers

| Maintainer | GitHub | Responsible for |
|---|---|---|
| XiangMeng | [@YearsAlso](https://github.com/YearsAlso) | everything below |

There is exactly one maintainer. If that changes, this table is the place it changes first —
[GOVERNANCE.md](GOVERNANCE.md) describes how someone becomes a maintainer, and
[`.github/CODEOWNERS`](.github/CODEOWNERS) is already shaped to take a second entry.

### Areas of responsibility

| Area | Owner | What "owned" means |
|---|---|---|
| **Security** | @YearsAlso | Triage private reports, decide severity, prepare and release the fix, publish the advisory |
| **Releases** | @YearsAlso | Version arithmetic, the release workflow, PyPI publication, changelog entries |
| **Documentation** | @YearsAlso | The docs site, the README pair, and keeping docs in step with behaviour |
| Everything else | @YearsAlso | Issues, pull requests, review, the spec baseline under `openspec/` |

### Expected response times

These are **best-effort targets from a one-person project, not a guarantee or an SLA.**
They are stated so that a report can tell the difference between "not looked at yet" and
"missed".

| Area | Expected first response | Notes |
|---|---|---|
| **Security report** | **48 hours** to acknowledge; **7 days** for an assessment and a fix timeline | Same commitments as [SECURITY.md](SECURITY.md), which is the authority if the two ever disagree |
| **Issue or pull request** | **7 days** for a first reply | A report with a minimal reproduction, Python version and OS is much faster to answer than one without |
| **Documentation fix** | 7 days, same as any pull request | |
| **Release** | No date commitment | A fix merged to `dev` is released automatically by the release workflow; there is no fixed release calendar |

If a report has gone unanswered past these bounds, a polite ping on the thread is the right
move — it is far more likely to be a missed notification than a decision.

### How to reach a maintainer

- **Public questions, bugs, feature requests** — [GitHub Issues](https://github.com/YearsAlso/zoo-framework/issues).
  There is no chat server and no mailing list.
- **Security vulnerabilities** — the private channel in [SECURITY.md](SECURITY.md),
  never a public issue.
- **Code of Conduct incidents** — see [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

### What review does not cover

`ruff check`, `ruff format`, `mypy`, `bandit` and the full test suite run as hard gates in
CI, on all three platforms. A green CI run means the mechanical checks passed — it does not
mean the design was reviewed. Review is one person reading the diff, and it is not a
substitute for your own testing.

---

<a name="中文"></a>
## 🇨🇳 中文

### 维护者

| 维护者 | GitHub | 负责范围 |
|---|---|---|
| XiangMeng | [@YearsAlso](https://github.com/YearsAlso) | 下面全部 |

维护者**只有一位**。这个状态若变化，会先改这张表——成为维护者的路径写在
[GOVERNANCE.md](GOVERNANCE.md)，[`.github/CODEOWNERS`](.github/CODEOWNERS) 已经按
"再加一条"的形状写好。

### 职责分区

| 事项 | 负责人 | "负责"指什么 |
|---|---|---|
| **安全** | @YearsAlso | 处理私密报告、判定严重级别、准备并发布修复、公开安全通告 |
| **发布** | @YearsAlso | 版本号算术、发布工作流、PyPI 发布、变更日志条目 |
| **文档** | @YearsAlso | 文档站、README 双份，以及让文档跟上行为变化 |
| 其余全部 | @YearsAlso | issue、PR、代码审查、`openspec/` 下的规范基线 |

### 可预期的响应时间

**这是单人项目的尽力目标，不是保证，也不是 SLA。** 写出来的目的是让报告者能区分
"还没看到"和"漏了"。

| 事项 | 预期首次响应 | 说明 |
|---|---|---|
| **安全报告** | **48 小时内**确认收到；**7 天内**给出评估与修复时间线 | 与 [SECURITY.md](SECURITY.md) 的承诺一致；两者万一不一致，以 SECURITY.md 为准 |
| **issue 或 PR** | **7 天内**首次回应 | 附带最小复现、Python 版本与操作系统的报告，回答起来快得多 |
| **文档修复** | 7 天，与普通 PR 相同 | |
| **发布** | 不承诺日期 | 合入 `dev` 的修复由发布工作流自动发版；本项目没有固定发版日历 |

如果超过以上时限仍未回应，在帖子里礼貌地 ping 一下就是正确做法——那更可能是通知漏了，
而不是被决定搁置。

### 怎么找到维护者

- **公开提问、缺陷、功能建议** —— [GitHub Issues](https://github.com/YearsAlso/zoo-framework/issues)。
  本项目没有 IM 群，也没有邮件列表。
- **安全漏洞** —— 走 [SECURITY.md](SECURITY.md) 的私密渠道，绝不开公开 issue。
- **行为准则事件** —— 见 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。

### 审查覆盖不到的东西

`ruff check`、`ruff format`、`mypy`、`bandit` 与全量测试套件在 CI 里是硬门禁，三个平台
都跑。CI 全绿只说明机械检查过了，**不**等于设计被审过。审查就是一个人读 diff，
不能替代你自己的测试。
