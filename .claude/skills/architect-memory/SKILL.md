---
name: architect-memory
description: 架构师记忆 Skill — 在架构审查/技术选型/分层决策完成后，将架构决策以 ADR 格式追加到 docs/memory/architect-decisions.md，维护架构红线、历史决策、技术选型约束与待办事项；与 docs/memory/architect-reasoning.md 推演记录、architecture-principles 原则体系联动，供后续架构决策参考
---

# Architect Memory — 架构师记忆

维护 Zoo Framework 项目的架构决策记忆库。由 `architect` agent 专职维护（reviewer 审查发现架构决策后转交）；software-engineer 在架构变更编码前应读取记忆确认不违反既定决策。

**文件拆分**：记忆拆为骨架 + ADR 全量两个文件，降低单文件体积：

| 文件 | 内容 | 读取方式 |
|------|------|----------|
| `docs/memory/architect-memory.md` | 骨架：架构红线 / 技术选型约束 / 架构待办 / 架构教训 | 文件小，可直接读取 |
| `docs/memory/architect-decisions.md` | ADR-001 起全量决策（编号连续） | 文件大，**必须 Grep 定位后按行精读，禁止全文读取** |

## 与推演记录、原则体系的联动

| 资产 | 文件 | 分工 |
|------|------|------|
| 架构记忆骨架（本 skill） | `docs/memory/architect-memory.md` | 红线/选型约束/待办/教训（高频硬约束） |
| 架构决策全量（本 skill） | `docs/memory/architect-decisions.md` | 已确定的 ADR 决策（事实，编号连续） |
| 推演记录 | `docs/memory/architect-reasoning.md` | 前瞻推演：长期影响 + 短期需求变化可能性（预测） |
| 架构原则 | `architecture-principles` skill | 设计时的硬性约束底线（规则） |

- **决策落地时**：架构决策确认后写入 `architect-decisions.md` 的 ADR，同时其推演过程归入推演记录
- **决策引用时**：新需求设计前同时翻看 ADR（既定决策）与推演记录（历史预测），二者冲突时以 ADR 为准并复盘修正推演

## 触发时机

- architecture-review 审查后产生架构决策/风险结论
- 技术选型确定（新增/更换第三方库、是否引入 Rust 核心）
- 分层/单例注册/横切关注点的重要约定确立
- 架构红线被违反并修复后（记录教训）

## ADR 记录结构（docs/memory/architect-decisions.md）

```
# 架构师记忆

## 架构红线（不可违反）
- {红线条目，如：core 内核禁止依赖具体 Worker 业务实现}

## 架构决策记录（ADR）
### ADR-{序号}：{决策标题}
- 日期：{yyyy-MM-dd}
- 背景：{为什么需要决策}
- 决策：{做了什么选择}
- 备选方案：{其他考虑过的方案及否决理由}
- 影响：{对现有/未来代码的影响}
- 状态：已接受 / 已废弃（{废弃原因}）

## 技术选型约束
- {选型条目：技术 + 版本 + 选用理由 + 禁止替换条件（如 Python 3.11+、gevent 待移除、Rust no-go 及再评估条件）}

## 架构待办事项
- [ ] {待办：如待重构项、技术债、需人工确认项}
```

## 执行流程

### Step 1: 定位既有记忆（索引优先，禁止全文读取）

`architect-decisions.md` 体积大，**禁止全文读取**。按以下顺序定位：

1. **取最新 ADR 序号**：`Grep '### ADR-' docs/memory/architect-decisions.md`，取最大编号
2. **查重复决策**：`Grep '{决策关键词}' docs/memory/architect-decisions.md` 命中既有 ADR 的行区间，判断是否已记录（**避免重复**）
3. **精读核实**：对命中的行区间用 Read 精读（仅读命中片段，不读全文）
4. **红线/选型/待办**：骨架文件 `architect-memory.md` 较小，可直接读取

### Step 2: 判断记录价值
仅记录**具有持久价值**的决策：
- 影响多个模块的架构约定 → 记录
- 一次性实现细节（如某方法内部实现）→ 不记录
- 与既有决策冲突的新结论 → 记录并标注"取代/修订 ADR-{序号}"

### Step 3: 追加记录
- 新决策 → 追加 `ADR-{新序号}` 条目到 `docs/memory/architect-decisions.md` 末尾（编号 = 当前最大 +1）
- 既有决策被推翻 → 在旧条目状态标记"已废弃（原因）"，追加新条目
- 红线/选型/待办/教训变更 → 更新骨架文件 `docs/memory/architect-memory.md`

### Step 4: 输出确认
```
## 架构记忆已更新
- 新增 ADR-{序号}：{标题}
- 变更：{更新内容摘要}
```

## 工作约束

- 只维护 `docs/memory/architect-memory.md`（骨架）与 `docs/memory/architect-decisions.md`（ADR），不修改其他文档
- 决策记录必须真实基于本次审查/实现，禁止虚构
- 记录保持精炼：背景一句话、决策一句话、影响可执行
- 若本次无新增决策，仅输出："✅ 无新增架构决策，记忆无需更新"
