"""拉起 ``server.py``（stdio MCP server）并调用其工具，打印结果.

这是集成示例的「可运行证据」：它证明工具调用会立即返回（不阻塞），而任务由后台常驻
Worker 异步处理，且进度可查询。

第三方依赖（**不是** ``zoo-framework`` 的安装面）::

    pip install mcp

运行（在本文件所在目录）::

    python client_demo.py

期望输出：``tools: [...]`` → ``submit_job -> accepted: ...`` → 等待数秒后
``server_status -> {"ticks": N, "jobsHandled": 1}``（ticks 持续增长、jobsHandled 为 1）。
"""

from __future__ import annotations

import asyncio
import os
import sys

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))


async def main() -> None:
    params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(HERE, "server.py")],
        cwd=HERE,
        env=dict(os.environ),  # 继承当前环境（含 PYTHONPATH），让 server 子进程能找到包
    )
    async with (
        stdio_client(params) as (read_stream, write_stream),
        ClientSession(read_stream, write_stream) as session,
    ):
        await session.initialize()

        tools = await session.list_tools()
        print("tools:", [tool.name for tool in tools.tools], flush=True)

        accepted = await session.call_tool("submit_job", {"job": "compile-report"})
        print("submit_job ->", accepted.content[0].text, flush=True)

        print("...后台 Worker 处理中，等待数秒...", flush=True)
        await asyncio.sleep(6)

        status = await session.call_tool("server_status", {})
        print("server_status ->", status.content[0].text, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
