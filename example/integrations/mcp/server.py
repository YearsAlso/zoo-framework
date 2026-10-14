"""用 Zoo Framework 做 MCP server 的本地任务执行后端 —— 长存活、带状态、不阻塞进程.

MCP server 常被要求「调一次工具就把活干完」；一旦工具要做长耗时的事，直接 ``await`` 会把
整个 server 卡住。本示例把任务投进框架的事件管道，由一个常驻 Worker 在**后台线程**消费，
工具调用立即返回。：

* **长存活**：常驻 Worker 与 server 生命周期同寿，工具调用之间它一直在跑。
* **带状态**：进度写入状态机（重启后可从落盘状态继续），工具可随时查询。
* **不阻塞**：``submit_job`` 只是投递事件后立即返回，asyncio 事件循环不被占用。

第三方依赖（**不是** ``zoo-framework`` 的安装面）::

    pip install mcp

运行：本文件是 **stdio** MCP server，由 MCP 客户端（如 ``client_demo.py`` 或任意
支持 stdio 的宿主）拉起，不直接手工运行::

    python client_demo.py        # 拉起 server 并调用两个工具，打印结果

**stdio 传输的铁律**：stdout 只允许走 JSON-RPC，任何 ``print`` / 日志写到 stdout 都会
破坏协议。故本示例把框架日志重定向到 stderr、自身的输出也一律走 stderr。

何时**不该**用本框架：见同目录 ``README.md`` 的「何时不该用本框架」一节。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading

import mcp.types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from zoo_framework.core import Master, event
from zoo_framework.event.event_provider import EventProvider
from zoo_framework.fifo.node import EventNode
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.workers import BaseWorker

SCOPE = "MCP"
TICKS_KEY = "backend.ticks"
JOBS_KEY = "backend.jobsHandled"


def _to_stderr(*args) -> None:
    """所有自身输出走 stderr —— stdout 专属 JSON-RPC 协议."""
    print(*args, file=sys.stderr, flush=True)


def _redirect_framework_logs_to_stderr() -> None:
    """把框架装到 stdout 的日志处理器改指 stderr.

    框架的日志配置（``@configure("log")``）会挂一个指向 stdout 的处理器；在 stdio
    MCP server 里这会污染协议流，因此在 Master 起好之后改指 stderr。
    """
    for handler in logging.getLogger().handlers:
        stream = getattr(handler, "stream", None)
        if isinstance(handler, logging.StreamHandler) and stream is sys.stdout:
            handler.stream = sys.stderr


class TickerWorker(BaseWorker):
    """常驻 Worker：server 活着它就一直跑，是「长存活后台执行」的可观察证据."""

    def __init__(self):
        super().__init__({"is_loop": True, "delay_time": 1.0, "name": "mcp_ticker_worker"})

    def _execute(self):
        state_machine = StateMachineManager()
        if not state_machine.have_loaded():
            # 状态尚未从 zooStates.pic 恢复（StateMachineWorker 首轮才载入）；
            # 先不推进，避免把「恢复前的 0」当成初始值。
            return
        ticks = (state_machine.get_state(SCOPE, TICKS_KEY) or 0) + 1
        state_machine.set_state(SCOPE, TICKS_KEY, ticks)
        _to_stderr(f"[mcp_ticker_worker] tick #{ticks}")


@event("mcp_job")
def on_job(req):
    """工具投递的任务在后台被处理（由框架内置的 EventWorker 消费）.

    Args:
        req: 事件请求对象；载荷在 ``req.content``。
    """
    state_machine = StateMachineManager()
    handled = (state_machine.get_state(SCOPE, JOBS_KEY) or 0) + 1
    state_machine.set_state(SCOPE, JOBS_KEY, handled)
    _to_stderr(f"[on_job] handled {req.content!r} (total {handled})")


async def list_tools(_ctx, _params):
    """声明本 server 暴露的工具."""
    return types.ListToolsResult(
        tools=[
            types.Tool(
                name="submit_job",
                description="投递一个后台任务并立即返回（任务由常驻 Worker 异步处理）。",
                input_schema={
                    "type": "object",
                    "properties": {"job": {"type": "string"}},
                    "required": ["job"],
                },
            ),
            types.Tool(
                name="server_status",
                description="查询后台进度：常驻 Worker 的 tick 数与已处理任务数。",
                input_schema={"type": "object", "properties": {}},
            ),
        ]
    )


async def call_tool(_ctx, req: types.CallToolRequestParams):
    """处理工具调用；耗时工作交给后台，本函数立即返回."""
    arguments = req.arguments or {}
    if req.name == "submit_job":
        job = str(arguments.get("job", "job"))
        EventProvider().push(EventNode(topic="mcp_job", content=job))
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=f"accepted: {job}")]
        )
    if req.name == "server_status":
        state_machine = StateMachineManager()
        payload = {
            "ticks": state_machine.get_state(SCOPE, TICKS_KEY) or 0,
            "jobsHandled": state_machine.get_state(SCOPE, JOBS_KEY) or 0,
        }
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload))]
        )
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=f"unknown tool: {req.name}")],
        is_error=True,
    )


server = Server(
    "zoo-mcp-integration",
    version="0.1.0",
    on_list_tools=list_tools,
    on_call_tool=call_tool,
)


async def main() -> None:
    """拉起框架（后台线程），随后以 stdio 提供 MCP 服务."""
    master = Master()
    # Master() 构造时已装好日志处理器；立刻改指 stderr，避免启动期日志污染 stdout。
    _redirect_framework_logs_to_stderr()
    master.register_worker("TickerWorker", TickerWorker)
    thread = threading.Thread(target=master.run, name="zoo-master", daemon=True)
    thread.start()

    # 给调度一拍：StateMachineWorker 从落盘文件载入状态。
    await asyncio.sleep(1.5)
    _to_stderr("[server] zoo master running; serving MCP over stdio")

    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        master.shutdown()
        thread.join(timeout=10)
        _to_stderr("[server] zoo master stopped")


if __name__ == "__main__":
    asyncio.run(main())
