# 贡献指南

这一页是**入口**：贡献有哪些方式、每一步的详版在哪。规范本身只有一份，在
[完整贡献者规范](../CONTRIBUTING_MAINTAINER.md)（分支策略、提交信息、质量门禁、类型门禁、
规范先行流程、发布流程）；仓库根的
[`CONTRIBUTING.md`](https://github.com/YearsAlso/zoo-framework/blob/dev/CONTRIBUTING.md)
是给"只想提一个小改动"的人看的**一页纸**版本。

!!! info "先记住一件事"
    拼写、文档、示例、注释类的改动**不需要** OpenSpec 提案，也不需要先开 issue —— 直接开 PR。
    改动涉及**外部可观察行为、兼容性或数据格式**时，才需要先写提案。

## 可以怎么贡献

| 方式 | 从哪开始 |
|---|---|
| 修文档 / 拼写 / 示例 / 注释 | 直接开 PR；想找活就从[可上手的任务](../GOOD_FIRST_ISSUES.md)里挑一条 |
| 报 Bug、提需求 | [GitHub Issues](https://github.com/YearsAlso/zoo-framework/issues) —— 本仓库没有聊天群、没有邮件列表 |
| 改代码 | 走下面的"一步一步" |
| 报告安全问题 | 走 [SECURITY.md](https://github.com/YearsAlso/zoo-framework/blob/dev/SECURITY.md) 的私密渠道，**不要**开公开 issue |

## 一步一步

1. **搭环境** —— 从零准备一个能提交 PR 的环境：[开发环境搭建](development.md)
2. **切分支** —— 从 `dev` 切出、PR 回 `dev`；发版在 `main` 上做：[分支策略](../BRANCHING.md)
3. **写代码** —— 质量门禁（ruff / pytest / mypy / bandit）、类型注解与提交信息规范：
   [完整贡献者规范](../CONTRIBUTING_MAINTAINER.md)
4. **提 PR** —— 用 [PR 模板](https://github.com/YearsAlso/zoo-framework/blob/dev/.github/PULL_REQUEST_TEMPLATE.md)；
   注意**合并进 `dev` 会自动发一个 `-beta` 版本**
5. **拿到回应** —— 小的 PR 或清晰的报告 **7 天内首次回应**，权威说明含安全响应时限：
   [MAINTAINERS.md](https://github.com/YearsAlso/zoo-framework/blob/dev/MAINTAINERS.md)；
   贡献者名单在 [CONTRIBUTORS.md](https://github.com/YearsAlso/zoo-framework/blob/dev/CONTRIBUTORS.md)

## 还需要什么

- [开发环境搭建](development.md) —— 解释器、依赖、pre-commit
- [调试指南](debugging.md) —— 常见问题排查与诊断工具
- [目录结构](structure.md) —— 仓库各目录的职责
- [架构设计](../ARCHITECTURE.md) —— 分层、调度模型与扩展缝
