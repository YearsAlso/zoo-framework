<!--
PR 目标分支默认为 `dev`。`main` 只在发版时接收来自 `dev` 的合并 —— 推送 `dev`/`main`
会触发自动发版并发布到 PyPI。
Base branch for PRs is `dev`. `main` only receives merges from `dev` at release time —
pushing to `dev`/`main` triggers an automatic release published to PyPI.
-->

## 变更描述 / What changed

<!--
说清楚「为什么」，而不只是「改了什么」。diff 已经说明了改了什么。
Explain the *why*, not just the *what* — the diff already shows what changed.
-->



## 关联 issue / Related issue

<!-- Closes #123 / Fixes #456 / 无 / none -->

## 变更类型 / Type of change

- [ ] `fix` —— Bug 修复 / bug fix
- [ ] `feat` —— 新功能 / new capability
- [ ] `docs` —— 文档 / documentation only
- [ ] `refactor` —— 重构，行为不变 / behaviour-preserving refactor
- [ ] `test` —— 测试 / tests only
- [ ] `chore` / `perf` —— 构建、工具、性能 / build, tooling, performance

## 测试 / Testing

**本地已执行 / Run locally:**

```bash
ruff check zoo_framework --fix
ruff format zoo_framework
pytest --cov=zoo_framework --cov-report=term-missing
```

- [ ] 以上命令本地全部通过，`pytest` 无失败 / all of the above pass locally
- [ ] 新增或修改的行为已有用例守护 / new or changed behaviour is covered by tests
- [ ] 涉及 `is_loop` / `run_timeout` / `delay_time` 等契约时，用例按属性式读取断言
      （不加调用括号）/ contract assertions use attribute-style reads

**这份改动是 / This change is:**

- [ ] 有测试覆盖的代码改动 / a code change covered by tests
- [ ] 仅文档改动，不涉及运行时代码 / documentation only, no runtime code touched
- [ ] 无法用自动化测试验证 —— 原因写在下面 / not verifiable by automated tests — reason below:

<!-- 如果是最后一项，请说明你手动验证了什么。不要声称未验证的事情已验证。 -->

## 破坏性变更 / Breaking change

- [ ] 否 / No
- [ ] 是 / Yes —— 见下方说明 / see below

<!--
若为「是」，请说明：破坏了什么、受影响的使用方式、迁移方法。如果是行为规范层面的变更，
必须同时提供 OpenSpec delta spec。
If yes: what breaks, which usage is affected, and how to migrate. If it is a documented
behaviour contract, an OpenSpec delta spec is required in this same PR.
-->

## 文档同步 / Documentation

- [ ] `README.md` —— 若能力表或代码片段受影响，**中英两半都已更新** / both language halves updated
- [ ] `docs/*.md` —— 对应的深入文档已更新 / relevant deep-dive updated
- [ ] docstring —— Google 风格（`Args:` / `Returns:` / `Raises:`）
- [ ] 不涉及文档 / no documentation affected
- [ ] `openspec/` —— delta spec 已提交 / delta spec included

## 自检 / Self-review checklist

- [ ] 我没有提交调试残留（print、注释掉的代码、临时文件）/ no debugging leftovers
- [ ] 我没有绕过质量门禁（未使用 `--no-verify`）/ no quality gate bypassed
- [ ] 我核对过文档对行为的描述与实现一致 / docs match the implementation
- [ ] 我没有从 `dev` 或 `main` 直接提交 / not committed directly to `dev` or `main`
