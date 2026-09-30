# Workflow: code-review — 代码审查

本文件是该 workflow 的唯一规范源。路由规则与场景信号见 `.claude/agents/leader.md`，主对话按本文件编排阶段序列执行。

## 适用场景

审查 / review / 代码质量 / 安全审查 / 架构审查。独立审查请求（非 feature-dev / bugfix 流程内置的审查阶段）。触发方式：用户直接请求审查 / `/review` 命令。

## 阶段序列

| 阶段 | 负责人 agent | 输入 | 产物 |
|------|-------------|------|------|
| 1. 范围确认 | pm | 用户请求 + 变更列表 | 审查范围 + 重点维度（安全/架构/语法/一致性） |
| 2. 代码扫描 | code-indexer | 审查范围 | 受影响模块全链路定位（需求→配置→装饰器→Worker/Reactor→FIFO/调度器→持久化） |
| 3. 深度审查 | reviewer | 代码 + 扫描结果 | 统一分级报告（python-syntax / security / architecture / persistence / cross-platform / docs-consistency 按需执行） |
| 4. 审计落盘 | reviewer | 🔴 发现 | audit-report 至 docs/audit-reports/ + 发现账本登记 |
| 5. 归档 | pm | 审查报告 + 审计报告 | 文档基线更新 + pm-memory 记录 |

## 裁剪规则

- 用户指定审查维度（如"只看安全"）→ 仅执行对应 skill，跳过其他维度
- 无 🔴 发现 → 跳过阶段 4（审计落盘）
- 单文件微审（<50 行）→ 可跳过阶段 1-2，直接 reviewer 轻量审查

## 边界与升级

- 审查发现须修复的 bug / 安全漏洞 → 输出修复建议，另起 bugfix 或 feature-dev 实施
- 审查发现架构问题 → 另起 design-doc 出方案，不在此 workflow 内直接改代码
- 审查发现 openspec 规格与实现漂移 → 转交 spec-syncer 核对规格同步
- 本 workflow 只审不改，除非用户明确要求"审查并修复"
