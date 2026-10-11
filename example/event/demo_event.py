"""最小事件管道示例 —— 声明 reactor → 投递事件 → 看它被响应.

把本文件当模块导入（或直接 `python demo_event.py`）都会注册一个 reactor；
`__main__` 块里走一遍最小闭环：构造 `EventNode` → `EventProvider.push` →
`EventWorker`（框架内置 Worker）排队事件 → reactor 收到并打印。
"""

from zoo_framework.core import event
from zoo_framework.utils import LogUtils


class DemoEvent:
    @staticmethod
    @event("change_test_number")
    def on_change_test_number(data):
        LogUtils.info("DemoEvent", f"on_change_test_number:{data}")


if __name__ == "__main__":
    # 最小闭环演示：EventWorker 是事件管道的消费者（框架内置 Worker，
    # 需注册并排队后才真正轮询管道）。
    # master.run() 会**阻塞**在调度循环上，所以生产者放到后台线程投递。
    import threading

    from zoo_framework.core import Master
    from zoo_framework.event.event_provider import EventProvider
    from zoo_framework.fifo.node import EventNode
    from zoo_framework.workers import EventWorker

    def produce():
        # 给调度循环留出起跑时间，再往 default 通道投递 3 个事件
        import time

        time.sleep(2)
        provider = EventProvider()
        for i in range(3):
            provider.push(EventNode(topic="change_test_number", content=f"#{i}"))
            LogUtils.info("DemoEvent", f"pushed event #{i}")

    master = Master()
    master.register_worker("EventWorker", EventWorker)
    threading.Thread(target=produce, daemon=True).start()
    master.run()
