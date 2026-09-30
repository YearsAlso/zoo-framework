---
name: pm-memory
description: 产品经理记忆 Skill — 在需求评审/文档一致性审核/SDD（OpenSpec）合规检查后，将需求上下文、文档一致性历史、SDD 合规记录、变更影响与用户偏好追加到 docs/memory/pm-memory.md（活跃）或 pm-memory-archive.md（已归档），供后续变更决策参考
---

# PM Memory — 产品经理记忆

维护 Zoo Framework 项目的产品经理（PM）记忆库。由 `pm` agent 专职维护（reviewer 审查发现文档差异/SDD 合规结论后转交）；software-engineer 编码前应读取记忆了解需求上下文与用户偏好。

**文件拆分**：记忆拆为活跃 + 归档两个文件，降低单文件体积：

| 文件 | 内容 | 读取方式 |
|------|------|----------|
| `docs/memory/pm-memory.md` | 活跃：需求上下文 / 文档一致性基线 / 变更影响 / SDD 合规 / Change 台账 / 遗留待办 / 用户偏好 | 体积中等，优先 Grep 索引定位，必要时按节读取 |
| `docs/memory/pm-memory-archive.md` | 已归档 ✅ 的 change 记录（需求上下文/基线/影响/合规四件套） | 仅回溯历史时查，**必须 Grep 定位后按行精读** |

## 触发时机

- docs-consistency-review 审查后产生文档差异/一致性结论
- 需求评审完成（需求上下文、范围边界确定）
- SDD（OpenSpec）合规检查发现流程问题
- 用户表达明确的偏好/约束（影响后续开发决策）

## 记忆文档结构（docs/memory/pm-memory.md）

```
# 产品经理记忆

## 需求上下文
### {需求/模块名}
- 背景：{业务背景}
- 范围：{包含/不包含}
- 用户偏好/约束：{明确表达过的偏好}

## 文档一致性历史
- {yyyy-MM-dd}：{差异描述} → 处理：{更新文档/修复代码/需确认}（涉及文件）

## SDD 合规记录
- {yyyy-MM-dd}：{变更} → {合规/违规} {说明}

## Change 台账
| Change | 状态 | 关联 capability | 归档日期 |
|--------|------|----------------|---------|
| openspec/changes/<id>/ | 进行中/已归档 | ... | ... |

## 变更影响记录
- {yyyy-MM-dd}：{变更} → 影响 {文档/公共 API 契约/配置键/持久化格式/跨平台行为}
```

## 执行流程

### Step 1: 定位现有记忆（索引优先，禁止全文读取）

记忆文件体积较大，**禁止全文读取**。按以下方式定位：

1. **查重复记录**：`Grep '{需求/模块关键词}' docs/memory/pm-memory.md` 命中既有记录的行区间，判断是否已存在（**避免重复**）
2. **精读核实**：对命中的行区间用 Read 精读（仅读命中片段，不读全文）
3. **回溯历史**：需查已归档 change 时，`Grep '{change id}' docs/memory/pm-memory-archive.md`

### Step 2: 判断记录价值
仅记录**影响后续决策**的信息：
- 需求范围边界、用户明确偏好 → 记录
- 文档-代码差异及其处理结论 → 记录（防止重复争议）
- 一次性执行细节 → 不记录

### Step 3: 追加记录
- 新需求上下文 → 追加到 `pm-memory.md` 的"需求上下文"
- 差异结论 → 追加到 `pm-memory.md` 的"文档一致性历史"
- 新 change → 追加到 `pm-memory.md` 的"Change 台账"
- **change 归档时**：将完整四件套（需求上下文/基线/影响/合规）追加到 `docs/memory/pm-memory-archive.md`，并从 `pm-memory.md` 移除已归档条目（保留活跃区精简）

### Step 4: 输出确认
```
## PM 记忆已更新
- 新增：{条目类型}：{内容摘要}
```

## 工作约束

- 只维护 `docs/memory/pm-memory.md`（活跃）与 `docs/memory/pm-memory-archive.md`（归档），不修改其他文档
- 记录必须真实基于本次审查/需求，禁止虚构
- 用户偏好只记录**用户明确表达**的内容，不推断
- 若本次无新增内容，仅输出："✅ 无新增 PM 记忆，无需更新"
