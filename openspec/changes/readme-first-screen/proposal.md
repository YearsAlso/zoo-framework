# readme-first-screen 提案

## Why

README 首屏（前 40 行）只有 logo + 8 个徽章 + 语言跳转，第一段定位信息在 22 行才开始；项目最差异化的叙事 "Built for AI-agent-generated code"（2026 年唯一有搜索热度的方向）被放在第 313 行。同时存在两类残留：作者待办注释泄漏（双语 README 的 ScreenToGif / asciinema 录制指引）与测试数量三处互相矛盾（367 / 662 / 实测 837）。首屏 10 秒内无法回答"这是什么、解决我什么痛点"，转化第一关失守。

## What Changes

- **README.md / README.zh.md 首屏重写**（各自前约 60 行）：徽章下移但保留（信任信号不删）；紧随其后压入"一句话定位（in-process / no broker / 为 AI 生成代码而设计）→ 解决什么（保留现有'二十行变几百行'文案）→ demo 图占位（仅干净注释标记）→ 30 秒最小示例（≤25 行完整可运行）"。
- **"Built for AI-agent-generated code" 一节上移**至首屏后的前三个小节之内（Comparison 之后、Installation 之前）。
- **删除全部作者待办注释块**（双语两处：录制工具指引），保留 `<!-- TODO(demo): docs/assets/demo.gif -->` 单行占位标记。
- **测试数量单一化**：全部改为"见 CI badge"，仅保留 will-run 数字为实测收集数（当前 837，apply 时以当次 `pytest --collect-only` 实测为准）；`367` 与 `662` 从 README 双语 + CONTRIBUTING 双语中消除。
- **docs/README.md 首页改为用户指南入口**：导航顺序改为「这是什么 → 5 分钟上手 → 核心概念 → API / 常见问题」，"架构设计 / 贡献指南 / 调试指南"降级为"贡献者文档"子章节；修正隐喻图与 README 口径（Master = 生命周期入口，非"园长"）。
- SHALL NOT 修改 zoo_framework/ 与 tests/ 下任何文件； SHALL NOT 引入 i18n 插件；不录 demo GIF（为他们预留位置）。

## Capabilities

### New Capabilities

- `readme-first-screen`：README 首屏的转化契约——首屏 8 行内的信息结构（定位 / 读者 / demo 位置）、发布物中禁止泄漏的作者待办、全仓库测试数量声明的单一真源规则、双语 halves 的平行性要求。

### Modified Capabilities

（无。）

## Impact

- 受影响文件：`README.md`、`README.zh.md`、`CONTRIBUTING.md`（仅两处测试数量行）、`docs/README.md`。
- 用户可见变化即时生效（文档站下次 docs.yml 构建跟随）。
- 关联 issue：#109（本 change 的工作单）。
