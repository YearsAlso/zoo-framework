---
name: doc-template
description: 文档编写规范 Skill — 编写/更新任何文档前先检查 docs/template/ 是否有匹配模板，有则按模板结构生成，无则提示并建议创建；维护文档类型→模板映射表；设计阶段产出 openspec proposal/design，software-engineer 编码时同步更新 docs/ 与 openspec/specs 均须遵循
---

# Doc Template — 文档编写规范

Zoo Framework 项目的文档编写规范。**强制流程：编写/更新任何文档前，先检查 `docs/template/` 下是否有匹配的文档模板；有模板则按模板结构生成，无模板则提示并建议创建**。

## 使用场景

- **设计阶段**：产出 `openspec/changes/<id>/proposal.md`、`design.md`、`specs/<capability>/spec.md`、`tasks.md`（走 `/opsx:propose`）
- **编码阶段**：software-engineer 编码后同步更新 `docs/` 受影响文档与 `openspec/specs/` delta
- **任何文档编写**：README、变更说明、架构说明、审计报告等

## 模板映射表

| 文档类型 | 模板文件（docs/template/） | 适用产出 |
|---------|---------------------------|---------|
| 行为规格 | openspec 内置模板（`openspec/`） | `openspec/specs/<capability>/spec.md`（SHALL/MUST，zh-CN 正文 + 英文结构标题） |
| 技术架构/方案 | `技术架构模板.md` | 分层、依赖、关键模式、扩展缝 |
| 审计报告 | `审计报告模板.md` | reviewer 分级发现落盘（docs/audit-reports/） |
| Bug 排查记忆 | `bug-investigation-memory-template.md` | docs/memory/bug-investigation-memory.md |
| 变更说明/发布 | `变更说明模板.md` | CHANGELOG、release-notes |

> 模板缺失时（本项目 `docs/template/` 尚未建立）：按下方"无模板处理"提示创建，不自行乱编结构。

## 强制流程

### Step 1: 检查模板
编写/更新文档前，先执行：
```bash
ls docs/template/
```
判断是否存在与文档类型匹配的模板文件。

### Step 2: 按模板生成（有模板）
- 打开对应模板，按模板的章节结构填写内容
- 模板中的占位符（如 `{能力名}`、`{配置键}`）必须全部替换为实际内容
- 不保留模板示例数据（示例仅作格式参考）
- 若模板与实际文档类型不完全匹配，按模板主结构编写并在结尾说明偏差

### Step 3: 无模板处理（无模板）
- 不自行编造结构，先提示用户："⚠️ docs/template/ 下无 {文档类型} 模板，建议先创建模板（可参考 docs/ 下现有 {同类文档}）"
- 如需立即编写，参考 `docs/`（ARCHITECTURE.md / DEVELOPMENT.md / OPTIMIZATION_PLAN.md / ROADMAP.md）或 `openspec/specs/` 现有同类文档的结构编写，并建议后续补充模板

### Step 4: 更新映射表
若创建了新的模板，同步更新 `docs/template/README.md` 的映射表。

## OpenSpec 文档语言约定（重要）

- `openspec/config.yaml` 规定：spec 正文为 **zh-CN**，但**结构性标题（如 `## ADDED Requirements`、`### Requirement:`）与 `SHALL`/`MUST` 关键词保持英文**
- 每个 change 的产物齐备：proposal → design → specs delta → tasks，`openspec validate <id> --strict` 通过后方可归档

## 工作约束

- 只做文档结构对齐与内容编写，不修改业务代码
- 编写的文档内容必须与代码/规格实际行为一致，禁止虚构未实现的功能
- openspec 规格文本的实际合并/归档交 `/opsx:sync`、`/opsx:archive` 与 `spec-syncer` agent，本 skill 只规范"怎么写"
