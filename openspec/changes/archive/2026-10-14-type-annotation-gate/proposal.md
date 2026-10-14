# 提案：type-annotation-gate —— 补齐 API 签名注解并把文档站构建收成严格门禁

## Why

`mkdocs` 在 PR #140 接入 `mkdocstrings` 后，API 参考改为从 docstring 生成，griffe 随之
开始校验签名里的类型注解。2026-10-12 在 dev 上实测：`mkdocs build` 输出**恰好 40 条**
griffe 告警（"No type or annotation for parameter/returned value"），另有 **1 条**链接
告警（`docs/BRANCHING.md` 的 `../CONTRIBUTING.md`，已由 PR #203 修掉）。

因为 `mkdocs.yml` 写的是 `strict: false`、CI 用 `mkdocs build`（非严格），这些告警
**不会**让任何门禁变红——站点上 API 参考的签名缺类型，IDE 补全与类型检查的价值打折，
而没人会被提醒。同一时期 `docs.yml` 只在 `main` 的 push 上触发，`dev` 与 PR 完全不跑
文档构建，问题只会在发版后出现在访客面前。

## What Changes

- 补齐 40 处进入 API 参考的签名注解（`core/`、`event/`、`reactor/`、`statemachine/`、
  `workers/` 共 12 个模块），不改任何运行时行为。
- `mkdocs.yml`：`strict: false` → **`true`**，并更正末尾那段与实际不符的注释（它举的
  `../bench/DECISION.md`、`.github/PULL_REQUEST_TEMPLATE.md` 在仓库里并不存在）。
- `.github/workflows/docs.yml`：构建改 `mkdocs build --strict`；触发补 `dev` 与 PR，
  并把 `mkdocs.yml` 纳入触发路径；**部署只在 `main`**（构建与部署分离）。
- `pyproject.toml`：对已具备完整注解的模块逐模块开启 `disallow_untyped_defs`（沿用
  `zoo_framework.utils.*` 的先例），使新增的缺注解定义被门禁拦住。

## Non-Goals

- 不一次性全局打开 `disallow_untyped_defs`（会牵出大量本变更范围外的改动）。
- 不改任何运行时行为：本变更只加注解、改文档与 CI 配置。
- 不引入新的文档站点或替换 mkdocs 工具链。
- 不修 `state_effect_scheduler` 里既有的 `StateNodeIndex` 缺方法缺陷（见 Impact）。

## Impact

- 源码：12 个模块的签名注解；`dispatch_core` 的 `_policy` 返回值经显式局部变量收敛类型。
- 配置：`mkdocs.yml`、`.github/workflows/docs.yml`、`pyproject.toml`。
- 规格：`ci-and-packaging` 与 `type-checking` 各新增一条 Requirement。
- **发现的既有缺陷（不在本变更修复范围）**：`StateEffectScheduler.add_state_effect` /
  `remove_state_effect` 调用 `self.state_effect_index.add_state_effect(...)`，但
  `StateNodeIndex` 并没有这两个方法——该路径运行期会 `AttributeError`。当前
  `StateEffectScheduler` 全仓无构造点，属死代码上的潜伏缺陷；本变更以逐行
  `type: ignore[attr-defined]` 如实标注、不改行为，缺陷另行开 issue 跟踪。
