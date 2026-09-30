---
name: review
description: 全维度代码审查 — reviewer 单 agent 按变更位置执行全部审查 skill（python-syntax-review / security-review / architecture-review / persistence-review / cross-platform-review / docs-consistency-review），汇总分级报告后按需执行 unit-tester / doc-writer，审查后更新架构师/PM 记忆
---

# /review — 全维度审查工作流

在准备提交或完成功能模块后使用，替代快速审查的浅层模式。

> 本 skill 由 `reviewer` agent 执行。按 reviewer 的路由规则调用对应审查 skill，汇总统一分级报告。

## 工作流

### Phase 1: 按变更位置审查

由 reviewer 按变更文件位置路由审查 skill：

| 变更位置 | 执行 skill | 说明 |
|---------|-----------|------|
| `**/*.py`（zoo_framework/） | python-syntax-review + security-review | 代码规范 + 安全双维度 |
| `bench/pyo3_probe/**/*.rs` | python-syntax-review（Rust 段）+ security-review | PyO3/GIL/clippy + 跨界安全 |
| `zoo_framework/statemachine/**`、`core/persistence_scheduler.py` | persistence-review（附加） | pickle 存档原子写/校验/备份/兼容 |
| `zoo_framework/utils/**`、平台相关 | cross-platform-review（附加） | Windows/Linux/macOS 差异 |
| 架构/依赖/单例注册/技术选型变更 | architecture-review | 技术架构质量 |
| `docs/**`、`openspec/**` | docs-consistency-review | 文档/规格一致性 + SDD 合规 |

**总耗时**：约 60-90s（按变更范围取最慢 skill，非累加）

### Phase 2: 汇总报告

按严重级别去重排序：

| 级别 | 含义 | 处理 |
|------|------|------|
| 🔴 阻断 | 架构违规、安全/不变量风险、持久化缺陷 | 必须修复 |
| 🟡 警告 | 规范违反、文档/规格不一致 | 建议修复 |
| 🔵 建议 | 可优化项 | 可选 |
| ✅ 通过 | 符合规范 | 确认通过 |

### Phase 3: 按需执行

根据变更类型决定后续步骤：

- **unit-tester** — 如有 .py 变更，ruff + 单目标 pytest 验收（编码前 test-design 用例清单同步核对）
- **doc-writer** — 如有 .py 变更且注释不足，按 doc-comment 规范补齐 docstring
- **perf-guardian** — 如触及热路径（锁/FIFO/事件管道/调度器），跑针对性性能对照
- **spec-syncer** — 如涉 `openspec/`，核对规格与实现一致、change 是否可归档

### Phase 4: 记忆更新

审查产生架构决策/需求结论时，按需更新：

- **architect-memory** — 架构决策以 ADR 格式追加到 `docs/memory/architect-decisions.md`（红线/选型/待办/教训更新骨架 `architect-memory.md`）
- **pm-memory** — 需求上下文/文档一致性/SDD 合规记录追加到 `docs/memory/pm-memory.md`（活跃）或 `pm-memory-archive.md`（已归档 change）

> 记忆文件较大，读写均遵循各 skill 的 Grep 索引定位 + 行区间精读约束，禁止全文读取。

### Phase 5: 输出报告

```markdown
## Review 最终报告

### 审查结果（reviewer 按位置路由）
- ✅ python-syntax-review: 通过
- ✅ security-review: 通过
- ✅ docs-consistency-review: 代码与文档/规格一致

### 综合评级
- 总体：✅ 通过
- 建议操作：可以提交

### 后续执行
- unit-tester：✅ 单目标 pytest 通过
- doc-writer：✅ 注释完整
- perf-guardian：跳过（无热路径变更）
```

## 与机械门禁的关系

| 机制 | 触发 | 耗时 | 用途 |
|------|------|------|------|
| pre-commit / CI | 提交/推送自动 | — | 机械底线（ruff / pytest / bandit） |
| `/review` | 用户按需调用 | ~60-90s | 全面深度审查（reviewer 全维度 + 记忆更新） |
