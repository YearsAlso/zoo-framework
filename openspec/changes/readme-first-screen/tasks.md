# readme-first-screen 任务清单

## 1. README.md / README.zh.md 首屏（双语逐节成对）

- [x] 1.1 重写双语首屏：logo 400→240px，定位句（in-process / no broker / AI-agent）、问题场景段、`<!-- TODO(demo) -->` 单行占位依次压缩到 8 行内（验证：spec Scenario "首屏三件事" 通过——分隔线后 22-30 行）
- [x] 1.2 将现有 Quick Start 的 MyWorker 代码块前移为"30 秒最小示例"，Quick Start 段保留 zfc 流程且不重复该代码（验证：临时目录独立运行跑通；实测发现重定向下 CPython 块缓冲延迟输出——在双语 README 补充说明而非改代码，见 tasks 下方注记）
- [x] 1.3 "Built for AI-agent-generated code" 双语节上移至对比表之后 Installation 之前（验证：英文 121 行 / 中文 114 行，均 < Installation 行号）
- [x] 1.4 删除双语作者待办注释块，仅留单行 `TODO(demo)` 标记；Quick Start 代码块中 "demo image placeholder" 相关注释一并清理（验证：`grep -in "ScreenToGif\|asciinema" README*.md` 零命中）

## 2. 测试数量单一化

- [x] 2.1 README 双语 2 处（"367-case regression suite" / "pytest # 662 cases"）、CONTRIBUTING 双语 2 处（"662 cases should pass" / "662 条用例应全部通过"）全部改为"见 CI badge"表述（验证：`grep -cn "367\|662" README*.md CONTRIBUTING.md` 全为 0）
- [x] 2.2 双语两半表述平行（验证：中英两处 `grep -in "badge"` 成对命中）

## 3. docs/README.md 首页重排

- [x] 3.1 导航重排：用户指南入口（这是什么 / 5 分钟上手 / 核心概念 / API / 常见问题）在前，架构 / 调试 / 贡献降级为贡献者子章节（验证：导航区两表分层——用户指南前、贡献者文档后）
- [x] 3.2 Mermaid 图隐喻修正：Master"园长"→生命周期入口、FIFO"饲养员队列"→每通道队列，与 README 核心概念表对齐（验证：新图为语义化标注，无"园长"独词）

## 4. 回归与归档

- [x] 4.1 双语平行性抽检：改动的各节 `grep -in` 中英成对命中；§2 首屏三节标题层级修正后 `grep -c "^### "` 双语 13/13（验证：成对命中清单）
- [x] 4.2 ruff format 对内嵌代码块：预跑 `ruff format` 三文件全部 "already formatted"，钩子不会拒绝提交（验证：commit 通过）
- [x] 4.3 `openspec validate readme-first-screen --strict` 通过（验证：退出码 0）

## 实测注记（apply 中发现）

最小示例在 stdout 重定向场景下因 CPython 块缓冲延迟输出（`-u` 下每秒 1 行，行为正常）。
已在双语 README 的"预期输出"处补一句缓冲说明，未改产品代码——日志降噪与观感问题归
quiet-default-logs（B2）。
