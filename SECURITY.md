# 安全策略 / Security Policy

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## 🇬🇧 English

### Supported versions

Zoo Framework is pre-1.0. Only the latest minor line (the newest release on PyPI) receives
security fixes; there is no LTS line and no back-porting to earlier minors. This table is
written so it does not need a manual edit at every version bump.

| Version | Supported |
|---|---|
| Latest release on PyPI | ✅ |
| The latest minor line (the newest minor version series) | ✅ security fixes; recent fixes only |
| Older minor lines | ❌ upgrade to the latest |
| `1.0` and later (future) | ✅ |

### Reporting a vulnerability

**Do not open a public issue.** Use either private channel:

1. **GitHub private security advisory** — preferred, tracked and auditable:
   <https://github.com/YearsAlso/zoo-framework/security/advisories/new>
2. **Email** — `mengxiang931015@live.com`

Please include:

- What you can do with the flaw that you should not be able to do.
- The affected version and platform, and the Python version.
- A minimal reproduction, or a proof of concept.
- Whether the issue is already public anywhere.

### Disclosure policy

- **Acknowledgement** within 48 hours.
- **Assessment and a fix timeline** within 7 days.
- A fix is released **before** public disclosure. Once a fixed release is published, the
  advisory is made public and you are credited unless you ask not to be.
- If you intend to disclose publicly, please tell us first so we can release together.

This is a single-maintainer project, so timelines are best-effort. We will not ask you to
sit on a critical issue indefinitely.

### Security model and trust boundaries

Zoo Framework is an **in-process library**. It has no network layer, no HTTP server, no
authentication, and no sandbox: Workers execute in your process, with your process's
privileges. That shape determines what is and is not a vulnerability.

**The state file is trusted input.** State is persisted with `pickle`
(`stateMachine:picklePath`, default `./zooStates.pic`) and restored with `pickle.load`.
Unpickling an attacker-controlled file is arbitrary code execution. Therefore:

- Do not point `stateMachine:picklePath` at a shared or world-writable location.
- Treat a state file as you would an executable: restore only files your own deployment
  wrote.
- A flaw that requires an attacker to already control that file is **not** a framework
  vulnerability — it is a misconfiguration of a trusted path.

**`CmdUtils` executes commands verbatim.** `zoo_framework.utils.CmdUtils` is a public
helper that runs a string through `os.popen` / `os.system` with no escaping or allow-list.
Nothing inside the framework calls it; it exists for callers who need it. Do not pass it
untrusted input — it offers no protection against shell metacharacters.

**Workers are not a trust boundary.** A Worker is code you wrote and deliberately
registered. The framework will not contain it, limit its filesystem or network access, or
protect the host from it. Running untrusted code as a Worker is out of scope.

### Out of scope

- Malicious or buggy code inside a Worker you registered.
- A state file, config file, or scaffold input that an attacker already controls.
- Denial of service through configuration (for example, a Worker that never returns, or a
  pathologically large `worker:pool:size`). The framework observes and circuit-breaks a
  timed-out Worker; it does not forcibly kill a running thread — CPython cannot do that
  safely, and the framework does not claim otherwise.
- Missing hardening headers, TLS configuration, and similar concerns — there is no server
  here to configure.

---

<a name="中文"></a>
## 🇨🇳 中文

### 支持的版本

Zoo Framework 尚未发布 1.0。只有最新的 minor 线（PyPI 上最新发布的那个次版本段）会收到
安全修复；项目没有 LTS 分支，也不会向更早的次版本回迁补丁。本表刻意写成不随版本号 bump
漂移的形式，无需随每次发版手改。

| 版本 | 是否支持 |
|---|---|
| PyPI 上的最新发布 | ✅ |
| 最新 minor 线（最新次版本所在的整个系列） | ✅ 仅安全修复 |
| 更早的 minor 线 | ❌ 请升级到最新版 |
| 未来的 `1.0` 及以后 | ✅ |

### 报告漏洞

**不要开公开 issue。** 请使用以下任一私密渠道：

1. **GitHub 私密安全通告** —— 首选，可追踪、可审计：
   <https://github.com/YearsAlso/zoo-framework/security/advisories/new>
2. **邮箱** —— `mengxiang931015@live.com`

请包含：

- 利用这个缺陷，你能做到哪些本不该做到的事。
- 受影响的版本与平台，以及 Python 版本。
- 最小复现，或一份 PoC。
- 该问题是否已在别处公开。

### 披露政策

- **48 小时内确认收到。**
- **7 天内给出评估与修复时间表。**
- 修复版本先发布，**然后**才公开披露。修复版本发布后，安全通告会公开，并致谢报告者（除非
  报告者要求匿名）。
- 如果你打算自行公开披露，请先告知我们，以便同步发布。

本项目只有一位维护者，因此时间线是尽力而为的。但我们不会要求你对一个严重问题无限期保密。

### 安全模型与信任边界

Zoo Framework 是一个**进程内库**。它没有网络层、没有 HTTP 服务、没有认证、没有沙箱：
Worker 在**你的进程内**以**你进程的权限**执行。这个形态决定了什么算漏洞、什么不算。

**状态文件是可信输入。** 状态通过 `pickle` 持久化（`stateMachine:picklePath`，默认
`./zooStates.pic`），并用 `pickle.load` 恢复。反序列化一个攻击者可控的文件等于任意代码
执行。因此：

- 不要把 `stateMachine:picklePath` 指向共享目录或全局可写的位置。
- 把状态文件当作可执行文件对待：只恢复你自己部署写入的文件。
- 「需要攻击者已经控制该文件」的缺陷**不构成**框架漏洞 —— 那是可信路径的配置错误。

**`CmdUtils` 会原样执行命令。** `zoo_framework.utils.CmdUtils` 是一个公开工具类，把字符串
直接交给 `os.popen` / `os.system`，不做转义、不做白名单。框架内部没有任何地方调用它，它是
留给调用方自己用的。不要向它传入不可信输入 —— 它对 shell 元字符没有任何防护。

**Worker 不是信任边界。** Worker 是你自己编写并主动注册的代码。框架不会约束它、不会限制它
的文件系统或网络访问、也不会保护宿主免受其影响。把不可信代码当作 Worker 运行，不在保护
范围之内。

### 不在安全边界内

- 你注册的 Worker 内部的恶意或有缺陷代码。
- 已经被攻击者控制的状态文件、配置文件或脚手架输入。
- 通过配置造成的拒绝服务（例如永不返回的 Worker，或极端巨大的 `worker:pool:size`）。框架
  会观测并熔断超时的 Worker，但**不会**强制杀死正在运行的线程 —— CPython 无法安全地做到
  这一点，框架也不声称做到了。
- 安全响应头、TLS 配置一类的问题 —— 这里没有可供配置的服务端。
