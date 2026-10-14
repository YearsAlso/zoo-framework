# Design: add-upstream-integrations

## Context

见 `proposal.md`（Why）。与本设计相关的既有事实：

- 仓库示例根目录是**单数** `example/`，其中已有 `example/fastapi/app.py`——一个把 `Master` 挂进 FastAPI `lifespan` 的最小示例（`example/README.md` 有说明），以及 `minimal.py` / `main.py` / `event/demo_event.py`。`example/` 的约束由既有能力 `example-hygiene` 规约（每个示例可独立运行、`example/README.md` 逐一说明）。
- `openspec/specs/native-task-execution` 与 `native/reference/modbus_rtu.py`、`native/src/modbus.rs` 表明框架已有一条与 Modbus 相关的原生任务线。
- `.claude/rules/ask-dont-assume.md`：方案选择优先级为「架构一致性 > 业务逻辑连续性 > 开发量最小」；不得为省事牺牲架构一致性。
- 诚实口径的既有出处：`README.zh.md` 的同类方案对比表与 FAQ、`llms.txt` 的 "When not to use it"、`ADOPTERS.md` 的 "honest gap"。集成文案必须与它们同源。

## Goals / Non-Goals

**Goals:**

- 选出 2–3 个上游并给出可复核的选择理由（含「为什么不选其它」），把最终取舍留给维护者。
- 让每个集成示例落在**一个**明确的示例根目录下，不与既有 `example/` 形成两棵树。
- 让每个交付物携带：可运行示例 + 可直接投给上游的说明文字 + 「何时不该用本框架」。
- 明确「被上游文档提及」优于「被上游依赖」这一点为何成立、以及它如何指导文案与 PR 形态。

**Non-Goals:**

- 不要求任何上游把本框架写入 `dependencies`（远期结果，非本变更目标）。
- 不改 `zoo_framework/`（issue 非目标）；不新增主包依赖。
- 不做插件 API / 插件市场（issue 非目标；实测 FastAPI、APScheduler 都不靠它）。
- 不在本变更内**实际**向上游仓库发起 PR（需要维护者身份与措辞确认；本变更交付示例与文案草稿，PR 是后续动作）。

## Decisions

### D1：上游选择（已定）——FastAPI（含 Starlette 同族）＋ MCP ＋ pymodbus

**筛选口径**（按「谁真的需要一个进程内、无 broker、带状态的任务执行器」＋ 本 issue 特有的「被文档提及」可达成性）：

| 上游 | 月下载 | 契合度 | 文档可插入性（是否有现成的「背景任务 / 替代方案」页） | 综合推荐 |
|---|---|---|---|---|
| starlette / uvicorn | 5.01 亿 / 4.99 亿 | ⭐⭐⭐⭐⭐ | 高（Starlette 定义 `BackgroundTasks`，其文档页明确指向 Celery 一类重方案） | **主选（与 FastAPI 同族）** |
| fastapi | 3.82 亿 | ⭐⭐⭐⭐⭐ | 高（Background Tasks 文档页已在讨论「重活别放这里、用 Celery」） | **主选** |
| mcp | 2.35 亿 | ⭐⭐⭐⭐ | 中（文档偏规范/示例形态） | **次选** |
| homeassistant | 64 万 | ⭐⭐⭐⭐ | 低（核心仅异步、审查严格，没有「背景任务替代方案」页可插） | 不选（维护者裁定第三个位置用 pymodbus） |
| pymodbus | 132 万 | ⭐⭐⭐⭐ | 中（与已实现的 Modbus 原生任务同源） | **选定（第三个）** |
| langgraph | 4477 万 | ⭐⭐⭐⭐ | 低（定位与「图编排 vs 进程内生命周期」互补，但文档插入点不明确） | 不选 |
| langchain | 1.70 亿 | ⭐⭐⭐⭐ | 低（工具循环的本地运行时可讲，但面太宽、插入点不明确） | 不选 |
| flask | 1.36 亿 | ⭐⭐⭐ | 低（无内建后台任务 → 没有既有页可插，需新写一页） | 不选 |
| django | 4114 万 | ⭐⭐⭐ | 低（有管理命令但文档对第三方提及严格，需新写一页） | 不选 |

**推荐结论：**

1. **主选 FastAPI（含 Starlette 同族，同一个 5 行文案可微调复用）**——理由：它的 `Background Tasks` 文档页**已经**在讨论「重活交给 Celery」这个问题，本框架恰好是「进程内、无 broker」的那一档答案，插入点天然存在；且 `example/fastapi/app.py` 已证明集成形态可行，本变更把它从「能嵌进去」推进到「演示重启后状态恢复、示范替代 `BackgroundTasks` 的可靠路径」。注意：`BackgroundTasks` 的实际定义方是 **Starlette**，因此文案应同时适配 Starlette 的 Background Tasks 页（同一族，两个 PR 成本几乎相同）。
2. **次选 MCP**——理由：MCP server 需要「长存活、带状态、不阻塞进程」的本地任务执行后端，与本框架形态吻合；受众在增长。文档插入点不如 Web 框架明确，故列次选。
3. **第三个：pymodbus（维护者已定）**——理由：与框架已实现的 Modbus 原生任务线**同源**（`native/reference/modbus_rtu.py` 的 RTU 响应帧解析就是仓库里已实现的样例任务），集成叙事天然自洽；且其文档有 Examples / 相关项目形态的插入点，示例成本最低。代价是受众规模（132 万）远小于前两者。
   - **为何不选 HomeAssistant（维护者加注）**：形态契合度最高（长期存活、进程内、无 broker、需状态持久化、跑在边缘设备），但**核心仅接受 asyncio、集成需 manifest/自定义组件、审查门槛最高**，且没有「背景任务替代方案」页可插——「被文档提及」的可达成性最低，外部成本与回报不成比例。故第三个位置选代码关联最硬的 pymodbus。

**为什么不选其它（逐条）：** langchain / langgraph——概念上与「进程内生命周期」互补但重叠（langgraph 也主张「长期存活、有状态」），文档插入点不明确，先做会稀释「2–3 个做深」的纪律；flask / django——无内建后台任务抽象，没有既有页可插，只能新写文档，成本高于收益，且 django 文档对第三方提及严格；uvicorn——是服务器，没有「背景任务」抽象层，不是集成的正确对象（它的价值在 optional extras，那是「被依赖」路径，不是本变更目标）。

### D2：落点（已定）——沿用既有单数 `example/`，新增 `example/integrations/<upstream>/`，不新建复数 `examples/`

**决策**：集成示例落在 `example/integrations/<upstream>/`（单数根）。issue 正文写的是复数 `examples/...`，本变更**有意偏离正文措辞**，以仓库现状为准。

**曾考虑但否决的方案：**

| 方案 | 收益 | 风险 | 结论 |
|---|---|---|---|
| A. 新建复数 `examples/` 只放集成 | 与 issue 正文路径一致 | 仓库出现两个平行示例根（`example/` 与 `examples/`），语义无区分、易误用；README/`llms.txt`/`example-hygiene` 需同时提两处 | **否决** |
| B. **沿用 `example/`，新增 `example/integrations/<upstream>/`** | 单一示例根，与 `example-hygiene` 的既有约束同源；`example/README.md` 单点指路 | 与 issue 正文路径有一字之差（复数 vs 单数） | **采纳（维护者裁定）** |
| C. 把 `example/` 整体重命名为 `examples/` | 与 issue 正文一致且只留一个根 | 破坏 `example/agent` 子模块路径、README/CONTRIBUTING/文档站大量引用，动静远超收益 | **否决** |

**理由**：架构一致性优先——仓库已把「示例契约」规约在单数 `example/` 上（能力 `example-hygiene`），新增第二棵树会与之冲突，且没有换来任何能力；C 的改名会波及子模块路径与全部文档引用，属于本 issue 范围之外的治理项。与 issue 正文的一字之差在 `example/README.md` 与说明文字里写清即可消除歧义。

### D3：为什么「被上游文档提及」比「被上游依赖」更容易达成、且同样有效

- **更容易达成**：写入 `dependencies` 意味着上游要为一个第三方承担安装面、版本兼容、供应链与安全审查成本，决策者要说服整个维护团队；而文档里加一行「如果你不想引 broker，可以用 X」只改一个 markdown 文件，是贡献者级别的改动。两者所需的说服半径差一个数量级。
- **同样有效**：生态的真实载体是**发现路径**，不是依赖图本身。`uvicorn[standard]`→`watchfiles` 的 3.04 亿月下载证明的是「被包管理器带出」的可见度；而 FastAPI（1% 插件生态）成为事实标准证明的是「文档与口碑」同样能把人带到入口。有文档指路的项目，使用者会自己 `pip install`——不必让上游替我们安装。
- **指导文案形态**：因此说明文字 MUST 写成「何时用、何时不用」的**中立取舍建议**，而不是推销；MUST 包含「何时不该用本框架」，让它读起来像上游文档作者会愿意合并的内容（承认边界反而提高被采纳概率）。

### D4：适配层边界——集成不得改框架代码

issue 明确「不改 `zoo_framework/`」。若某集成需要适配（如把 `Master` 生命周期挂进对方的 hook），适配代码 MUST 位于示例目录内、MUST NOT 被框架导入、且 MUST 在示例 README 或文件头注释里说明其存在理由（因为它在教读者「你的集成方该怎么写」）。已有的 `example/fastapi/app.py` 正是这一形态（`lifespan` 内起线程跑 `Master.run()`、关闭时 `Master.shutdown()`），可作为其余集成的参照样式。

### D5：诚实口径的落地方式——复用既有出处，不新造口径

「何时不该用本框架」MUST 与以下既有出处同源，避免出现第二套真相：`README.zh.md` 同类方案对比表与 FAQ、`llms.txt` 的 "When not to use it"、`ADOPTERS.md` 的 "honest gap"。三条硬边界（跨机器 → Celery；cron → APScheduler；多进程 → 未实现）以及「健康指标链路未接通」的 ⚠️ 状态 MUST NOT 在集成文案中被描述为可用。

### D6：Capability 归属——新建 `upstream-integration`，而非改 `example-hygiene`

集成示例的**行为契约**（落点唯一、可运行、随附上游文案与诚实口径、跨平台）是此前没有的能力，用 ADDED 新建 `upstream-integration` 最干净。`example-hygiene` 的既有约束对 `example/` 下的新目录自动生效，不需要重复声明。落点已定为单数 `example/`（D2），因此**不需要**对 `example-hygiene` 追加 MODIFIED delta。

## Risks / Trade-offs

- [上游是否合并我们的文档 PR 不受本框架控制] → 交付物只承诺「可运行的示例 + 可直接投递的文案 + 至少一次 PR 动作」；是否被合并记为外部依赖（见 roadmap 完成判据）。
- [文案夸大能力会反噬信誉] → 诚实口径为硬约束（spec 中「未实现的能力不被写入」有专门 Scenario）；文案复用既有诚实出处。
- [pymodbus 受众规模小（132 万），单点收益低于 Web 框架] → 它是「与既有原生 Modbus 任务同源」的低成本补充，不挤占 FastAPI/MCP 的深度；三条叙事各自独立。
- [落点与 issue 正文不一致（单数 vs 复数）引发后续 PR 争议] → D2 已由维护者裁定为单数 `example/`，并在 `example/README.md` 与说明文字里写明原因，消除歧义。
- [集成示例引入的第三方依赖随上游版本漂移而失效] → 依赖只写示例文件头注释、不进主包；示例 README 写明依赖与版本假设，失效时按 example-hygiene 的「可独立运行或有说明」处置。

## Migration Plan

无需迁移（纯新增示例与文案，不改框架行为、不改配置语义）。落地顺序：Q1/Q2 已由维护者裁定（单数 `example/`；三上游为 FastAPI/Starlette + MCP + pymodbus）→ 建 `example/integrations/<upstream>/` → 逐个跑通并留执行证据 → 提上游文档 PR。回滚 = revert 相关提交，无运行时影响。

## Open Questions

- **Q1（已裁定）**：落点用单数 `example/integrations/<upstream>/`（D2）。
- **Q2（已裁定）**：三上游为 FastAPI/Starlette、MCP、pymodbus（D1）。
- **Q3（可后答）**：MCP 具体面向哪一份文档/示例仓（官方 `modelcontextprotocol` 文档还是某个 server 示例仓）——取决于选定后对该项目文档结构的调研，不影响示例与文案的写法。
