# 提案：add-upstream-integrations

## Why

Issue [#138](https://github.com/YearsAlso/zoo-framework/issues/138)。用实测数据检验了「框架冷门是因为没有插件生态」这个假设，**假设不成立**（2026-10 数据）：

| 框架 | 月下载 | 插件生态 / 核心 |
|---|---|---|
| FastAPI | 3.82 亿 | 0.01 |
| APScheduler | 3439 万 | 0.01 |
| celery | 4319 万 | 0.30 |
| pytest | 7.62 亿 | 0.94 |

FastAPI 与 APScheduler 的插件生态都只有核心的约 1%，却都是各自品类的事实标准。真正的机制是**被上游依赖 / 被上游文档引用**：`uvicorn[standard]` 的 optional extras 里放了一个 2,550 star 的 `watchfiles`，就为它拉出 3.04 亿月下载；`pydantic` 强依赖 `pydantic-core`，后者被拉出 8.08 亿。

结论：争取生态的正确动作不是招插件作者，而是**让 2–3 个上游的文档提到本框架**。`docs/contributing/roadmap.md` 已把本项列在 **Next**，完成判据是「至少一条上游文档（或官方示例仓）链接到本框架，并给出可复现的集成步骤」。

## What Changes

- 选定 **3 个上游**做深：**FastAPI（含 Starlette 同族）、MCP、pymodbus**（选择理由与「为什么不选其它」见 `design.md` D1；pymodbus 取代 issue 建议的 HomeAssistant，理由见该节）。
- 为每个选定上游产出一个**真实可运行**的集成示例，落在**唯一的示例根目录**下：`example/integrations/<upstream>/`（落点已定为单数 `example/`，见 `design.md` D2；**有意偏离 issue 正文的复数 `examples/` 写法**，理由见 D2）。
- 每个示例配一段 **3–5 行、可直接投进对方文档**的说明文字（说明何时该用本框架替代上游内建方案、何时不该）。
- 每个示例附「**何时不该用本框架**」一节，沿用 README 限制表 / `llms.txt` 的诚实口径（跨机器 → Celery；cron → APScheduler；多进程 → 未实现；健康指标链路 → 未接通）。
- 至少向 1 个上游提交一份**文档 PR**（目标是让对方文档的「背景任务 / 集成」一节提到本框架，**不是**要求对方 `dependencies` 依赖本框架）。
- **不改 `zoo_framework/` 代码**。集成若需适配层，MUST 放在示例目录内并说明理由（issue 非目标）。

## Capabilities

### New Capabilities

- `upstream-integration`: 上游集成示例的落点与命名、每个示例的可运行性契约与执行证据、随示例交付的「上游文档说明文字」与「何时不该用」的诚实口径要求、以及「集成 MUST NOT 改框架代码」的边界。

### Modified Capabilities

无。（本变更不改动既有能力的行为；落点若最终选择新建复数根 `examples/`，则需追加对 `example-hygiene` 的 MODIFIED delta——见 `design.md` 开放问题 Q1。）

## Impact

- **新增（示例）**：`example/integrations/<upstream>/`（每个上游一个目录，含可运行入口 + README + 说明文字；具体文件随 `tasks.md` 展开）
- **新增（文档）**：`example/README.md` 的集成示例指路；每目录内「可直接投给上游」的说明文字草稿
- **不改**：`zoo_framework/`、`tests/`、`pyproject.toml`（第三方依赖写在示例文件头注释里，不进主包安装面）
- **外部动作**：向上游仓库提文档 PR（PR 前先与维护者确认选定组合与措辞）
- **风险**：上游是否接受文档 PR 不受本框架控制；措辞若夸大框架能力会损害信誉——故诚实口径为硬约束
