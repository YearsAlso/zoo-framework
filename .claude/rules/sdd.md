# SDD 规范驱动开发约束（OpenSpec 落地版）

## 原则

**任何非平凡变更（影响 > 1 个文件，或涉及架构决策，或变更业务逻辑）必须走 SDD 流程：先出规范，再编码。**

本项目 SDD 流程由 **OpenSpec** 承载（`openspec/` 目录，配套 `/opsx:propose` ~ `/opsx:archive` 命令）。本规则与 `ask-dont-assume.md` 互补：ask-dont-assume 管"不脑补需求"，本规则管"变更的流程纪律"。

## SDD 工作流（OpenSpec 原生流程）

```
Propose（proposal.md）→ Design（design.md）→ Spec Deltas（specs/）→ Tasks（tasks.md）→ Apply（实现）→ Validate → Archive
```

| 阶段 | 操作 | 产出 |
|------|------|------|
| 1. Propose | 编写变更提案（背景/范围/影响） | `openspec/changes/<id>/proposal.md` |
| 2. Design | 基于提案编写技术设计 | `openspec/changes/<id>/design.md` |
| 3. Spec Deltas | 描述对能力规格的增改（ADDED/MODIFIED/REMOVED Requirement） | `openspec/changes/<id>/specs/<capability>/spec.md` |
| 4. Tasks | 拆解实施任务清单 | `openspec/changes/<id>/tasks.md` |
| 5. Apply | 按 tasks 实现代码 + 测试 | 代码变更 |
| 6. Validate | `openspec validate <id> --strict` 通过 | 校验结论 |
| 7. Archive | 归档变更，规格合入主specs | `openspec/changes/archive/<date>-<id>/` + 更新 `openspec/specs/` |

语言约定：`openspec/config.yaml` 规定正文为 zh-CN，结构性标题与 SHALL/MUST 关键词保持英文。

## 触发条件

以下情况**必须**走 SDD（OpenSpec change）流程：

- 新增功能 / 模块 / Worker 类型 / 事件机制
- 修改调度模型（`SchedulerModel` / `WorkerDispatchCore` / waiter 体系）
- 修改事件分发协议（`response_mechanism`、优先级计算、重试语义）
- 修改持久化格式（pickle 存档结构、`PersistenceScheduler` 备份/校验策略）
- 修改接口契约（公共 API 签名、`@worker`/`@event`/`@cage` 装饰器语义、CLI 脚手架产物）
- 引入新的第三方依赖（`pyproject.toml` dependencies）
- 重构超过 2 个文件
- 变更影响配置解析语义（`ParamsPath` / `_exports` / aliases 行为）

以下情况**可以**跳过 SDD 流程：

- 单文件 bug 修复（改 < 20 行，逻辑不变）
- 注释 / 文档更新
- 纯配置变更（`example/config.json` 值调整，不涉及键语义）
- 测试代码变更

## Spec 内容要求

每个 spec delta 的 Requirement 必须可验证（SHALL/MUST 陈述），并覆盖：

- **业务背景**：为什么要做这个变更（proposal.md）
- **功能范围**：包含和不包含的功能边界（proposal.md / design.md）
- **接口契约**：公共 API、装饰器语义、CLI 行为
- **数据/状态模型**：涉及的参数键、状态机结构、持久化数据
- **边界条件**：异常场景、错误处理、幂等性、并发语义
- **跨平台影响**：Windows / Linux / macOS 行为差异（对应 `cross-platform-io` 规格）

## 文档一致性要求

1. 实现完成后，必须运行 `pm` agent 进行文档比对审核（合入后由 `spec-syncer` agent 核对规格与实现一致）
2. 审核确认 `openspec/specs/`（行为规格权威源）与 `docs/`（说明性文档）同代码实现一致
3. 如果文档与代码存在差异，必须先更新文档再合入代码
4. `openspec/specs/` 是可信源，代码变更必须与规格描述一致

## 禁止行为

- ❌ 非平凡变更不走 SDD（OpenSpec change）流程
- ❌ 实现完成后不更新 `openspec/specs/` / `docs/` 相关文档
- ❌ 代码与规格/文档描述不一致时合入代码
- ❌ 跳过 `openspec validate --strict` 直接归档
