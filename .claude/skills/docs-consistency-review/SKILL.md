---
name: docs-consistency-review
description: 文档一致性与 SDD 合规审查 Skill — 比对代码实现与 docs/、openspec/specs/ 文档一致性，审核 SDD（Propose→Design→Implement→Verify→Archive）流程合规，分析变更影响范围，供 reviewer 在 docs/openspec 变更及综合审查时调用
---

# Docs Consistency Review — 文档一致性与 SDD 合规审查

审查代码实现与 `docs/`、`openspec/specs/` 的一致性，并监督 SDD（OpenSpec）流程合规。reviewer 在 `docs/**`、`openspec/**` 变更及综合审查时调用本 skill。

## 审查内容

### 1. 文档/规格一致性审核

比对代码实现与文档描述，聚焦四类：
- **架构一致性**：分层、包职责、依赖方向、`@cage`/注册机制、扩展缝（`SchedulerModel`/`StateIndex`/`PersistenceStrategy`/`Plugin`）与 `docs/ARCHITECTURE.md` 描述是否吻合
- **行为规格一致性**：`openspec/specs/<capability>/spec.md` 的 SHALL/MUST 条款与代码实际行为是否一致（本项目权威可信源）
- **配置契约一致性**：`ParamsPath` 键、`example/config.json`、CLI 脚手架产物与文档描述是否一致
- **持久化一致性**：状态机存档/pickle 路径、备份策略与文档描述是否一致

**差异处理**：
- 文档/规格正确，代码有偏差 → 修复代码
- 代码正确，文档/规格未更新 → 更新文档（由 software-engineer 编码时同步；openspec 规格文本同步建议转交 spec-syncer）
- 文档/规格模糊无法判断 → 向用户提问确认（遵循 ask-dont-assume）

### 2. SDD（OpenSpec）流程合规检查

审核本次变更是否符合 SDD 规范：
- 非平凡变更是否走 Propose → Design → Spec Deltas → Tasks → Apply → Validate → Archive 流程
- 是否存在对应的 openspec change（`openspec/changes/<id>/`）
- 实现是否与 spec delta/design 一致
- `openspec validate <id> --strict` 是否通过
- 变更后是否更新了 `docs/` 文档（代码与文档同改原则）

**Spec 内容要求（每个 Requirement 必须可验证）**：业务背景、功能范围、接口/装饰器契约、数据/状态模型、边界条件、跨平台影响

### 3. 变更影响分析

分析本次变更的影响范围：
- 影响哪些 `docs/`、`openspec/specs/` 文档需要更新
- 是否影响公共 API 契约（`zoo_framework` 导出符号 / 装饰器语义 / WorkerResult 字段）
- 是否影响配置键语义 / 持久化格式（需迁移说明）
- 是否影响跨平台行为（需三平台验证）

## 执行流程

### Step 1: 获取变更范围
```bash
git diff main...HEAD --name-only
```

### Step 2: 确定相关文档
根据变更文件路径，确定需要比对的文档：
- `zoo_framework/core/**`、`workers/**` → ARCHITECTURE.md + 对应 capability 的 openspec spec
- `zoo_framework/event/**`、`fifo/**`、`reactor/**` → `openspec/specs/event-dispatch`、`worker-scheduling`、`async-worker-runtime`
- `zoo_framework/statemachine/**`、`persistence_scheduler.py` → `openspec/specs/state-machine`、`worker-lifecycle`
- `zoo_framework/params/**` → `openspec/specs/config-resolution`（scoped-container change）
- `zoo_framework/__main__.py`、templates → `openspec/specs/cli-scaffolding`、`project-scaffolding`
- `utils/**`、平台相关 → `openspec/specs/cross-platform-io`

### Step 3: 逐项比对
打开相关文档/规格，逐项比对代码实现与文档描述；同时用 Grep 定位 `docs/memory/pm-memory.md` 中 PM 记忆记录的已知差异基线（需回溯历史时查 `pm-memory-archive.md`），禁止全文读取。

### Step 4: 输出报告

```
## 文档一致性审查报告

### 变更概览
- 变更文件：N 个
- 变更类型：新功能 / Bug 修复 / 重构 / 文档

### SDD 合规检查
- ✅ 流程合规 / ⚠️ 非平凡变更缺少 openspec change

### 文档/规格一致性审核
- ✅ 架构一致性：...
- ✅ 行为规格一致性（openspec SHALL）：...
- ✅ 配置契约一致性：...
- ✅ 持久化一致性：...

### 差异项
| 文件:行号 | 文档/规格描述 | 代码实现 | 建议 |
|-----------|--------------|---------|------|
|           |              |         | 更新文档/规格 / 修复代码 / 需确认 |

### 影响分析
- 📋 需更新的文档/规格：...
- ⚠️ 公共 API/持久化格式影响：...
- 🌐 跨平台影响：...

### 结论
✅ / ⚠️ / ❌
```

## 工作约束

- 审查时不修改业务代码和文档，只输出审查报告和差异分析
- 发现差异时给出明确处理建议（更新文档/规格 / 修复代码 / 需确认）
- 报告必须包含 `文件:行号` 级别的精确定位
- 发现文档一致性差异/需求上下文结论时，转交 pm 按 pm-memory skill 追加记录；openspec 规格文本层面的同步转交 spec-syncer
