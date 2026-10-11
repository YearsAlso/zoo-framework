# 治理 / Governance

[English](#english) | [中文](#中文)

---

<a name="english"></a>
## 🇬🇧 English

### Who maintains this project

**One person.** The maintainer list in [MAINTAINERS.md](MAINTAINERS.md) is the single
source for who is responsible for what; this file does not repeat it.

**There is no committee, no steering group, no charter and no voting process.** This is a
solo project, and a governance file claiming otherwise would be the least credible document
in the repository.

### How decisions are made

- **Small changes** (bug fixes, docs, tests) are decided in the pull request. The
  maintainer approves, or the change does not land.
- **Anything that changes behaviour** is spec-first. `openspec/specs/<capability>/spec.md`
  is the authoritative statement of behaviour, and the reasoning behind a change is written
  into that change's `design.md`, which stays in the repository after the change is
  archived. A decision whose reasoning can be read later beats one that exists only in a
  chat log.
- **Declining is a decision.** This project refuses features deliberately — a small,
  coherent scope is the feature. A refusal comes with its reason, and it is a judgement
  about the work, never about the person who proposed it (see
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)).
- **Disagreement** is argued in the issue or pull request. If it cannot be settled there,
  the maintainer decides and records the reasoning in the pull request or in the change's
  `design.md`. Behaviour problems are not handled this way — they go through the Code of
  Conduct process.

### Becoming a maintainer

There is no application form and no checklist. The path is: land a few changes that show
you understand both the code and the project's insistence on spec-first, then ask — or be
asked. Maintenance is a commitment to respond, not a badge.

The single-maintainer risk is real and stated plainly: if the maintainer stops, releases
stop. There is no succession plan and no foundation behind this project. A second
maintainer is welcome, and [`.github/CODEOWNERS`](.github/CODEOWNERS) is already written to
accommodate one.

### Versions and breaking changes

- The version policy lives in [docs/VERSION_POLICY.md](docs/VERSION_POLICY.md) and is
  **not** restated here — two copies of a policy is one copy too many.
- While the project is pre-1.0, minor releases may break compatibility. Every breaking
  change is listed in [CHANGELOG.md](CHANGELOG.md) with a migration note, and
  [docs/MIGRATION.md](docs/MIGRATION.md) carries the longer upgrade paths.
- Vulnerabilities are **not** handled by the process above; they go through the private
  channel described in [SECURITY.md](SECURITY.md).

### Related documents

- [MAINTAINERS.md](MAINTAINERS.md) — who, and the expected response times
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — expected behaviour, and how to report abuse
- [SECURITY.md](SECURITY.md) — vulnerability reporting and the trust model
- [ADOPTERS.md](ADOPTERS.md) — who uses this, labelled honestly
- [docs/contributing/roadmap.md](docs/contributing/roadmap.md) — what is planned, from a
  user's point of view

---

<a name="中文"></a>
## 🇨🇳 中文

### 谁在维护

**一个人。** 谁负责什么，以 [MAINTAINERS.md](MAINTAINERS.md) 的维护者列表为唯一真源，
本文不重复一遍（两处名单就是一处漂移源）。

**没有委员会、没有指导组、没有章程、没有投票流程。** 这是单人项目；治理文件若往别的
方向写，会是整个仓库里最不可信的一份文档。

### 决策怎么做

- **小改动**（缺陷修复、文档、测试）在 PR 里决定：维护者通过，或者改不动。
- **凡是改变行为的改动**都是规范先行。`openspec/specs/<capability>/spec.md` 是行为的
  权威声明，改动背后的理由写进该变更的 `design.md`——变更归档后它仍留在仓库里。
  事后能读到理由的决定，胜过只存在于聊天记录里的决定。
- **拒绝也是一个决定。** 本项目有意拒绝功能：范围小且自洽本身就是这个项目的卖点。
  拒绝会给出理由，而且针对的是工作本身，从不针对提建议的人（见
  [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)）。
- **分歧**在 issue 或 PR 里讨论。谈不拢时由维护者决定，并把理由记录在 PR 或该变更的
  `design.md` 里。行为层面的问题不走这条路，走行为准则流程。

### 怎么成为共同维护者

没有申请表，也没有清单。路径是：先落地几个改动，证明你既懂代码、也理解本项目对
"规范先行"的坚持，然后提出来——或者被邀请。维护是"持续回应"的承诺，不是荣誉称号。

单人维护的风险是真实存在的，所以直说：维护者停下来，发布就停下来。本项目没有继任计划，
背后也没有基金会。欢迎第二位维护者，[`.github/CODEOWNERS`](.github/CODEOWNERS) 已经按
这个方向写好。

### 版本与破坏性变更

- 版本政策在 [docs/VERSION_POLICY.md](docs/VERSION_POLICY.md)，本文**不**重述——
  政策的第二份副本就是多余的副本。
- 项目在 1.0 之前，小版本可能不兼容。每一处破坏性变更都在
  [CHANGELOG.md](CHANGELOG.md) 里连同迁移说明列出，更长的升级路径见
  [docs/MIGRATION.md](docs/MIGRATION.md)。
- 安全漏洞**不**走上面的流程，走 [SECURITY.md](SECURITY.md) 描述的私密渠道。

### 相关文档

- [MAINTAINERS.md](MAINTAINERS.md) —— 谁在维护，以及可预期的响应时间
- [CONTRIBUTING.md](CONTRIBUTING.md) —— 怎么贡献
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) —— 行为期待，以及如何举报
- [SECURITY.md](SECURITY.md) —— 漏洞报送与信任模型
- [ADOPTERS.md](ADOPTERS.md) —— 谁在用，如实标注
- [docs/contributing/roadmap.md](docs/contributing/roadmap.md) —— 使用者视角的规划
