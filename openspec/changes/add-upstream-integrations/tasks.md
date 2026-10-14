# Tasks: add-upstream-integrations

> 落点已定为单数 `example/integrations/<upstream>/`（Q1 已裁定）；三上游为 FastAPI/Starlette、MCP、pymodbus（Q2 已裁定）。
> 所有示例与文案均**不改 `zoo_framework/`**；第三方依赖只写示例文件头注释，不进主包 `pyproject.toml`。

## 1. 前置确认

- [x] 1.1 确认 Q1 落点：维护者裁定沿用单数 `example/integrations/<upstream>/`，不新建复数 `examples/`（见 `design.md` D2）
- [x] 1.2 确认 Q2 第三个上游：维护者裁定为 pymodbus（与既有 Modbus 原生任务同源），非 HomeAssistant（见 `design.md` D1）
- [x] 1.3 确认上游说明文字措辞须经维护者过目后方可提交上游（对应规格「上游文档贡献 MUST 以被文档提及为目标」）

## 2. 主选上游：FastAPI（含 Starlette 同族）

- [x] 2.1 `example/integrations/fastapi/app.py`：常驻 Worker + 事件管道 + 状态机落盘，演示**重启后进度从落盘值继续**；实跑证据：RUN1 `tick #1..#11 / jobsHandled 1`，RUN2 `tick #12..#23 / jobsHandled 2`（重启不归零）
- [x] 2.2 `example/integrations/fastapi/upstream-doc-snippet.md`：5 行说明文字（何时用 / 何时不该），可直接投 FastAPI/Starlette 的 Background Tasks 页
- [x] 2.3 `example/integrations/fastapi/README.md`：含「何时不该用本框架」一节（跨机器 → Celery；cron → APScheduler；多进程 → 未实现；一次性收尾 → 直接用 `BackgroundTasks`；投递保证 → 需 broker）
- [x] 2.4 `example/README.md`：新增「集成示例（`integrations/`）」小节与三行表格（演示什么 / 怎么跑 / 期望输出），并写明单数 `example/` 落点理由
- [x] 2.5 文案未声称未实现能力；已与 `README.zh.md` 限制表 / `llms.txt` 的 *When not to use it* 逐项比对

## 3. 次选上游：MCP

- [x] 3.1 `example/integrations/mcp/server.py` + `client_demo.py`：stdio MCP server（官方 Python SDK 2.x 的 handler API），工具投递即返回，常驻 Worker 后台处理；实跑证据：RUN1 `server_status -> {"ticks": 8, "jobsHandled": 1}`，RUN2 `{"ticks": 15, "jobsHandled": 2}`
- [x] 3.2 `example/integrations/mcp/upstream-doc-snippet.md`（5 行）+ README 的「何时不该用本框架」一节
- [x] 3.3 `example/README.md` 表格新增该集成行

## 4. 第三个上游：pymodbus

- [x] 4.1 `example/integrations/pymodbus/poller.py`：进程内模拟 Modbus TCP 设备 + 常驻 Worker 轮询寄存器 + 状态落盘（纯 Python，不依赖原生扩展）；实跑证据：RUN1 `poll #1..#8`（含 `threshold breached #1..#4`），RUN2 `poll #9..#12`（重启续跑）
- [x] 4.2 `example/integrations/pymodbus/upstream-doc-snippet.md`（5 行）+ README 的「何时不该用本框架」一节（含硬实时/亚秒级不适用的诚实说明）
- [x] 4.3 `example/README.md` 表格新增该集成行

## 5. 诚实口径与规格核对

- [x] 5.1 三份说明文字逐条核对：多进程、cron、跨机器、健康指标链路四项均按「未实现/不支持」表述；另补「持久化的是状态而非队列、不做投递保证」与「不适合硬实时」两条边界
- [x] 5.2 `git status --porcelain`：改动仅 `example/README.md`（M）、`example/integrations/`（新增）、`openspec/changes/add-upstream-integrations/`（新增）；`zoo_framework/`、`tests/` 零命中
- [x] 5.3 `pyproject.toml` 未改（无新增依赖；fastapi/uvicorn/mcp/pymodbus 只写示例文件头注释）

## 6. 上游文档贡献（对外动作）

- [ ] 6.1 向上游提交文档 PR —— **未做**：维护者指示本机不提交/不推送、PR 由主对话统一发起（HTTPS 到 GitHub 不通）。文案已就绪待投
- [x] 6.2 三份 `upstream-doc-snippet.md` 随各自集成目录交付（MCP 的落点 Q3 仍待维护者确认）

## 7. 验收与归档前置

- [x] 7.1 三个示例实跑并留执行证据（见 2.1 / 3.1 / 4.1；证据为原始输出片段）
- [x] 7.2 `openspec validate add-upstream-integrations --strict`：`Change 'add-upstream-integrations' is valid`
- [x] 7.3 `pytest tests/test_doc_consistency.py -q` → 180 passed；全量 `pytest -q` → **1195 passed**（与基线一致）

> 实施补充（design 未预见，已在示例内消化、未改框架）：
> 1. **状态载入竞态**：常驻 Worker 可能在 `StateMachineWorker` 首轮载入落盘状态**之前**先跑一轮，
>    导致把「恢复前的 0」当初始值（实测 pymodbus 出现 `poll #1` 紧接 `poll #16`）。示例改用公开
>    的 `StateMachineManager().have_loaded()` 守卫：未载入前不推进计数。这是**示例侧的用法**，
>    未触碰框架代码。
> 2. **MCP SDK 为 2.x**：`mcp` 在 PyPI 上解析到官方 `modelcontextprotocol/python-sdk` 2.3.0，其 API
>    已从 `@server.list_tools()` 装饰器改为 `Server(on_list_tools=…, on_call_tool=…)` 处理器形态；
>    示例按 2.x 写，并在 README 注明依赖与 stdio 的 stdout 纯净约束。
> 3. **pymodbus 为 3.16**：旧 `ModbusSequentialDataBlock` 已弃用，示例改用 `SimData`/`SimDevice`；
>    文件头把依赖钉到 `pymodbus>=3.16,<4`。
