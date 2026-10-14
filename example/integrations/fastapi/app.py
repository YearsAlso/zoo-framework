"""用 Zoo Framework 替代 FastAPI 的 ``BackgroundTasks`` —— 后台任务带状态、可落盘.

``BackgroundTasks`` 是在请求返回后跑的一次性回调：**没有状态、没有观测、进程重启即丢**。
本示例用框架的常驻 Worker（持续跑）+ 事件管道（提交即返回）+ 状态机落盘（``os.replace``
原子写 + 滚动备份），演示它做不到的那一件事：**重启之后，后台进度从落盘状态继续**。

第三方依赖（**不是** ``zoo-framework`` 的安装面，请自行安装）::

    pip install fastapi uvicorn

运行（在本文件所在目录，``config.json`` 会被框架自动读取）::

    python -m uvicorn app:app --port 8010

验证::

    curl -X POST localhost:8010/submit -d '"order-1"' -H "content-type: application/json"
    curl localhost:8010/state
    # Ctrl-C 停掉，再用同一命令启动一次：GET /state 里的 ticks 从落盘值继续增长，
    # jobsHandled 也保留 —— 这是进程重启后仍存的状态。

契约要点：``POST /submit`` 立即返回（与 ``BackgroundTasks`` 一样不阻塞请求），
但真正的处理走框架事件管道，且进度写入状态机，因此重启不会归零。

何时**不该**用本框架：见同目录 ``README.md`` 的「何时不该用本框架」一节。
"""

from __future__ import annotations

import asyncio
import threading
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI

from zoo_framework.core import Master, event
from zoo_framework.event.event_provider import EventProvider
from zoo_framework.fifo.node import EventNode
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.workers import BaseWorker

# 状态机里本示例使用的 scope 与键。框架按「scope + 键路径」读写，落盘后重启可恢复。
SCOPE = "FastAPI"
TICKS_KEY = "backend.ticks"
JOBS_KEY = "backend.jobsHandled"


class HeartbeatWorker(BaseWorker):
    """常驻 Worker：与有没有 HTTP 请求无关，按 ``delay_time`` 持续推进并把进度落盘."""

    def __init__(self):
        super().__init__(
            {
                "is_loop": True,  # 跨调度轮次持续运行
                "delay_time": 1.0,
                "name": "heartbeat_worker",
            }
        )

    def _execute(self):
        """每轮把落盘的 tick 计数加一 —— 重启后计数从上次落盘值继续，而非归零."""
        state_machine = StateMachineManager()
        if not state_machine.have_loaded():
            # 状态尚未从 zooStates.pic 恢复（StateMachineWorker 首轮才载入）；
            # 先不推进，避免把「恢复前的 0」当成初始值。
            return
        ticks = (state_machine.get_state(SCOPE, TICKS_KEY) or 0) + 1
        state_machine.set_state(SCOPE, TICKS_KEY, ticks)
        print(f"[heartbeat_worker] tick #{ticks}", flush=True)


@event("fastapi_job")
def on_job(req):
    """``POST /submit`` 投递的任务在这里被处理（由框架内置的 EventWorker 消费）.

    Args:
        req: 事件请求对象；载荷在 ``req.content``。
    """
    state_machine = StateMachineManager()
    handled = (state_machine.get_state(SCOPE, JOBS_KEY) or 0) + 1
    state_machine.set_state(SCOPE, JOBS_KEY, handled)
    print(f"[on_job] handled {req.content!r} (total {handled})", flush=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时拉起 Master（后台线程），关闭时优雅停机并落盘."""
    master = Master()
    master.register_worker("HeartbeatWorker", HeartbeatWorker)

    # Master.run() 阻塞在调度循环上，放进后台线程；shutdown() 线程安全、幂等。
    thread = threading.Thread(target=master.run, name="zoo-master", daemon=True)
    thread.start()

    # 给调度循环一拍时间：StateMachineWorker 会在这期间从 zooStates.pic 载入状态，
    # 之后 HeartbeatWorker 的计数才从落盘值继续（而不是从 0 起后再被覆盖）。
    await asyncio.sleep(1.5)
    try:
        yield
    finally:
        master.shutdown()
        thread.join(timeout=10)


app = FastAPI(title="Zoo Framework in FastAPI", lifespan=lifespan)


@app.post("/submit")
def submit(payload: str = Body(default="job")):
    """投递一个后台任务：立即返回，由事件管道 + 常驻 Worker 异步处理."""
    EventProvider().push(EventNode(topic="fastapi_job", content=payload))
    return {"accepted": payload}


@app.get("/state")
def state():
    """读取落盘状态：常驻 Worker 的 tick 数与被处理的任务数（重启后仍可读）."""
    state_machine = StateMachineManager()
    return {
        "ticks": state_machine.get_state(SCOPE, TICKS_KEY) or 0,
        "jobsHandled": state_machine.get_state(SCOPE, JOBS_KEY) or 0,
    }
