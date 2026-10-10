# readme-first-screen 设计

## Context

- README.md 现结构：1-20 行 logo + 8 徽章 + 跳转；22 行 "What it is"（已有 in-process / no broker / 定位明确的好文案）；313 行 "Built for AI-agent-generated code"；356 行 "367-case"；390 行 "662 cases"；139-148 行双语（英文半 + 中文半 129-138 行）各一组作者待办注释。
- CONTRIBUTING.md:41 / :318 有 "662 cases should pass"（C1 change 的 10 条清单中未覆盖 CONTRIBUTING 两处——本 change 拿下）。
- docs/README.md 首页已有正确的定位句，但导航以开发者文档为主，且 Mermaid 图把 Master 画成"园长"、FIFO 画成"饲养员队列"，与 README 的核心概念表（Master = lifecycle entry point）口径不一致。
- 实测测试收集数：**837**（本会话两次实测一致）。注意提示词包勘误的 825 也过期了——apply 时以当次实测为准。
- 双语平行是 CONTRIBUTING 明文契约（"grep -in 双半命中"）。
- B1 `scaffold-demo-worker` 尚未实施，Quick Start 段落的 `zfc --create` 行为说明保持现状（B4 `readme-quickstart-truth` 负责重写 Quick Start 全段）；本 change 只重写首屏，Quick Start 代码块本身不动。
- `ruff format` 会归一 Markdown 内嵌 Python 块（CONTRIBUTING 已明文此坑）——最小示例代码块写成 ruff-compatible 格式。

## Goals / Non-Goals

**Goals:**
- 首屏 10 秒内回答"是什么 / 解决什么 / 凭什么选它 / 看起来什么样"。
- 测试数量全仓库一个口径（实测值或"见 CI badge"），永不静默过期。

**Non-Goals:**
- 不动 Quick Start 正文与 CLI 行为描述（B4 负责）。
- 不录 GIF / 不动 docs/assets（后续 change）。
- 不改 `docs/ROADMAP.md` / BUSINESS_PLAN（C2 负责重写）。
- 不引入 mkdocs i18n 插件。

## Decisions

### D1 首屏结构（双语相同顺序）

```
logo（缩小 240px）+ 徽章 + 语言跳转     ← 保留，但 logo 从 400px 减到 240px，压缩到 3 行内
---
一句话定位（提出 in-process / no broker / 为 AI 生成代码而设计）
它解决什么（保留现有 "二十行变几百行" 段落）
<!-- TODO(demo): docs/assets/demo.gif -->  ← 干净单行占位
30 秒最小示例（≤25 行完整可运行，现有 Quick Start 的 main.py 代码块前移复用）
How it compares（对比表——"凭什么不用 Celery"）
```

现有代码块（`MyWorker` 25 行，已可运行、已含 is_loop/delay_time/name 注释）直接作为最小示例，在此之前它本来就在 85-119 行，前移约 60 行。Alternative：新写一个更短的 10 行示例被否——现有示例含"Worker 必须注册为类"的正确演示，10 行版会丢失。

### D2 "Built for AI-agent-generated code" 上移到首屏后

位置：对比表之后、Installation 之前。理由：它是差异化叙事（三层意思的第三层），且 367-case 句在节内——上移的同时顺势把数字改掉。

### D3 测试数量单一化："见 CI badge" 优先，不再裸写数字

四处（README 双半 ×2 + CONTRIBUTING 双半 ×2）改为 "见 CI badge" / "see the Tests badge"。理由：任何裸写数字都会过期（这是三个版本数字的根因）；CI badge 是唯一随仓库自动更新的真源。**留 0 处裸数字**，与提示词包"值必须等于实测数"的验收不同——选择了更抗漂移的方案，在 evidence 中说明该偏离。C1 的文档一致性测试落地时，断言改为"README/CONTRIBUTING 不含裸写用例数"，比"等于当前收集数"更稳定。

### D4 docs/README.md 导航重排而不重写

定位句与核心概念解释已正确，仅调序：用户指南（这是什么 / 5 分钟上手=DEVELOPMENT / 核心概念 / API / 常见问题=DEBUGGING 拆分）在前，开发与贡献文档降级为子章节；Mermaid 图三个节点文案改为与 README 概念表一致（Master="生命周期入口"等）；标题从"开发文档"改为"文档首页"。

### D5 待办注释的唯一合法形态

`<!-- TODO(demo): docs/assets/demo.gif -->` 单行出现在双语文档的固定位置（原 139-148 / 129-138 注释块替换处）。`grep -n "ScreenToGif\|asciinema\|录制" README*.md` ZERO 命中。

## Risks / Trade-offs

- [双语重写后两半漂移] → 重写时逐节成对改；完工跑 `grep -in` 平行检查。
- [ruff format 改内嵌代码块导致提交钩子拒绝] → 预写 ruff-compatible 格式，遇拒绝接受一次重写再提交（CONTRIBUTING 已注意事项）。
- [徽章挪动影响 README 渲染] → 徽章位置只动行序不动行内容；GitHub 渲染与 mkdocs 站点（docs/README.md 独立）都验证。

## Migration Plan

1. 单 PR → dev：README 双语首屏重写 + AI-agent 节上移 + 数量统一化 + docs/README.md 导航重排。
2. 验收命令（双语 × 各项见 tasks）。
3. 回滚：revert 单 commit。

## Open Questions

（无。）
