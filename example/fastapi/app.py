"""把 Zoo Framework 嵌进 FastAPI 服务 —— 后台 Worker 与 HTTP 请求在同一个进程里.

这不是框架自带的依赖：示例自带第三方依赖，不属于 `zoo-framework` 的安装面。

安装与运行（在本文件所在目录）：

    pip install fastapi uvicorn
    uvicorn app:app --port 8000      # 等价写法：python -m uvicorn app:app --port 8000

验证：

    curl -X POST localhost:8000/tick     # 投递一次任务
    curl localhost:8000/state            # 看后台 Worker 跑了几轮、事件被处理了几次

停止：Ctrl-C。lifespan 的关闭分支会调用 `Master.shutdown()`（幂等且线程安全），
Worker 的销毁钩子与状态落盘都在那一步发生。

为什么本目录没有 `__init__.py`：目录名 `fastapi` 与第三方包同名，若把它做成包，
在 `example/` 目录下 `import fastapi` 会被本目录遮蔽。不作为包即可避免。
"""

from __future__ import annotations

import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI

from zoo_framework.core import Master, event
from zoo_framework.event.event_provider import EventProvider
from zoo_framework.fifo.node import EventNode
from zoo_framework.workers import BaseWorker

# Worker 线程与请求处理线程都会读写下面两个共享点；示例加锁是为了让共享边界显式，
# 不是框架的要求（框架保证的是"同一个 Worker 不会被重复派发"，不保证业务数据）。
_lock = threading.Lock()
_rounds = {"n": 0}
_handled: list[str] = []


class HeartbeatWorker(BaseWorker):
    """常驻后台 Worker：服务活着它就按排期跑，与有没有 HTTP 请求无关."""

    def __init__(self):
        super().__init__(
            {
                "is_loop": True,  # 跨调度轮次持续运行
                "delay_time": 1.0,
                "name": "heartbeat_worker",
            }
        )

    def _execute(self):
        """每轮把计数加一并打印——这是"框架真的在调度"的可观察证据."""
        with _lock:
            _rounds["n"] += 1
            current = _rounds["n"]
        print(f"[heartbeat_worker] round #{current}", flush=True)


@event("tick")
def on_tick(req):
    """POST /tick 投递的事件在这里被处理（由框架内置的 EventWorker 消费）.

    Args:
        req: 事件请求对象；载荷在 ``req.content``（不是原始载荷本身）。
    """
    with _lock:
        _handled.append(str(req.content))
    print(f"[on_tick] handled {req.content!r}", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时拉起 Master，关闭时优雅停机."""
    master = Master()
    master.register_worker("HeartbeatWorker", HeartbeatWorker)

    # Master.run() 会阻塞在调度循环上，所以放进后台线程；
    # shutdown() 通过 call_soon_threadsafe 停掉事件循环，可从任意线程调用。
    thread = threading.Thread(target=master.run, name="zoo-master", daemon=True)
    thread.start()
    try:
        yield
    finally:
        master.shutdown()
        thread.join(timeout=10)


app = FastAPI(title="Zoo Framework in FastAPI", lifespan=lifespan)


@app.post("/tick")
def tick():
    """投递一次任务：HTTP 请求 → 事件管道 → 响应器."""
    payload = f"tick-{time.time_ns()}"
    EventProvider().push(EventNode(topic="tick", content=payload))
    return {"accepted": payload}


@app.get("/state")
def state():
    """观察闭环：后台 Worker 的轮数，以及已被处理的事件."""
    with _lock:
        return {"heartbeat_rounds": _rounds["n"], "handled": list(_handled)}
