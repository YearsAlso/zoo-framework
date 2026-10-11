# 安全模型 / Security model

[English](#en) | [中文](#zh)

这是**给使用者**的安全说明：支持哪些版本、怎么报送漏洞、依赖策略是什么，以及我们
**没有做**什么。框架内部的信任边界（状态文件、`CmdUtils`、Worker 不是信任边界、
什么不算漏洞）在 [SECURITY.md](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md)
里，本文不重述。

---

## 🇬🇧 English {#en}

### Supported versions

Zoo Framework is pre-1.0. **Only the latest minor line receives security fixes** — there is
no LTS line and no back-porting to earlier minors. The authoritative table lives in
[SECURITY.md](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md#supported-versions)
and is written so it does not need editing at every release.

Older minor lines get **no** fixes: upgrade to the latest release.

### Reporting a vulnerability

Use the **private** channels listed in
[SECURITY.md](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md#reporting-a-vulnerability)
— a GitHub private security advisory (preferred) or email. **Do not open a public issue**:
the point of a private channel is that a fix can ship before anyone can use the flaw.

Acknowledgement within 48 hours, assessment and a fix timeline within 7 days; the fix is
released before public disclosure. This is a single-maintainer project, so those are
best-effort commitments.

### Dependency policy

Runtime dependencies (**3**): click, pyyaml, python-dotenv.

- **A declared dependency must be a used dependency.** `typing-extensions` used to be declared
  with zero imports anywhere in the repository; it was removed (issue #124) rather than kept as
  a dependency nobody uses.

- **The manifest is the only source.** `pyproject.toml` declares, `uv.lock` pins. There is
  no second, hand-maintained requirement list — one used to exist and it drifted from the
  manifest, which is exactly how a project ends up shipping advisories it never chose.
- **The locked set is scanned.** The dependency set described by `uv.lock` is scanned for
  known vulnerabilities; the reproducible command and the current result are recorded in
  [the supply-chain status page](security-supply-chain.md).
- **The attack surface is small by construction, not by policy.** The framework has **no
  broker, no network layer, no HTTP server and no authentication service** — it is an
  in-process library. Nothing in the runtime dependencies opens a socket on your behalf.
- **Updates arrive through Dependabot** (weekly, for both Python dependencies and GitHub
  Actions), and the Lockfile is re-locked with `uv lock`, which Dependabot does not do.

### What we have not done

- **No third-party security audit.** Nobody outside the project has reviewed this code.
  The security-relevant claims in these documents are the maintainer's own.
- **The supply-chain hardening is not in effect on the default branch yet.** CodeQL,
  pinned action SHAs, tightened workflow token permissions and dependabot live on the
  development line; the default branch has not received them. Tracked in
  [#107](https://github.com/YearsAlso/zoo-framework/issues/107), with the current state and
  evidence in [the supply-chain status page](security-supply-chain.md).
- **No OpenSSF Best Practices badge.** The project has not registered for it
  ([#95](https://github.com/YearsAlso/zoo-framework/issues/95)).
- **A long-lived credential still exists.** Publishing to PyPI uses OIDC (no stored PyPI
  token), but the automated release-branch pull requests use a long-lived
  `RELEASE_PAT` secret. It is kept deliberately — GitHub does not run workflows for pull
  requests opened with the default token — and it is a real, disclosed exception.
- **No fuzzing.** There is no fuzz target for the parsing-heavy paths (config resolution,
  event payloads).

---

## 🇨🇳 中文 {#zh}

### 支持的版本

Zoo Framework 尚未发布 1.0。**只有最新的 minor 线会收到安全修复**——没有 LTS 分支，也不会
向更早的次版本回迁补丁。权威表格在
[SECURITY.md](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md)
里，并刻意写成不需要随每次发版手改的形式。

更早的 minor 线**不会**收到修复：请升级到最新版。

### 报告漏洞

请使用
[SECURITY.md](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md)
里列出的**私密**渠道——GitHub 私密安全通告（首选）或邮箱。**不要开公开 issue**：私密渠道的
意义就在于修复能先于任何人都还没法利用之前发布。

48 小时内确认收到，7 天内给出评估与修复时间表；修复版本先发布，然后才公开披露。本项目
只有一位维护者，因此这些是尽力而为的承诺。

### 依赖策略

运行依赖（3 个）：click、pyyaml、python-dotenv。

- **声明了就得有人用。** `typing-extensions` 曾被声明为运行依赖，而全仓 0 处 import；
  它是被移除（issue #124），而不是继续挂着一个没人用的依赖。

- **清单是唯一真源。** `pyproject.toml` 声明，`uv.lock` 锁定。不存在第二份手工维护的依赖
  清单——历史上曾有一份，且它与清单长期漂移，那正是"被迫背着一堆自己从未选择的通告"的
  由来。
- **锁定集合会被扫描。** `uv.lock` 描述的依赖集合会做已知漏洞扫描，可复跑的命令与当前结论
  记录在[供应链状态页](security-supply-chain.md)。
- **攻击面小是结构决定的，不是承诺。** 框架**没有 broker、没有网络层、没有 HTTP 服务、
  没有认证服务**，它是一个进程内库。运行依赖里没有任何一个会替你在后台开套接字。
- **依赖更新经 Dependabot**（每周，覆盖 Python 依赖与 GitHub Actions 两类）；锁文件用
  `uv lock` 重锁，这一步不在 Dependabot 能力范围内。

### 未做的事

- **没有第三方安全审计。** 项目外没有人审过这份代码；这些文档里与安全有关的结论都是维护者
  自己的判断。
- **供应链加固尚未在默认分支生效。** CodeQL、action 钉 SHA、工作流 token 权限收紧与
  Dependabot 都在开发线上，默认分支还没拿到。跟踪于
  [#107](https://github.com/YearsAlso/zoo-framework/issues/107)，当前状态与证据见
  [供应链状态页](security-supply-chain.md)。
- **没有 OpenSSF Best Practices 徽章。** 尚未注册
  ([#95](https://github.com/YearsAlso/zoo-framework/issues/95))。
- **仍存在一个长期凭据。** 发布到 PyPI 走 OIDC（不持有 PyPI token），但自动开的 release
  分支 PR 使用长期 `RELEASE_PAT`。这是有意保留的——用默认令牌开的 PR 不会触发后续
  workflow——它是一处如实披露的例外。
- **没有 fuzz 测试。** 解析密集的路径（配置解析、事件载荷）没有 fuzz 目标。
