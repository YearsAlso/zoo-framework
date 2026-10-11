"""最小完整示例 —— README「30 秒看完整个东西」示例的落盘版.

复制 → `python minimal.py` → 每秒一行 `Hello from MyWorker! Count: N`，
Ctrl-C 停止。不需要 config.json（Master() 默认找 `./config.json`，没有也能跑）。
"""

from zoo_framework.core import Master
from zoo_framework.workers import BaseWorker


class MyWorker(BaseWorker):
    """一个循环执行的任务单元."""

    def __init__(self):
        super().__init__(
            {
                "is_loop": True,  # 跨调度轮次持续运行
                "delay_time": 1.0,  # 每轮执行后等待的秒数
                "name": "MyWorker",
            }
        )
        self.counter = 0

    def _execute(self):
        self.counter += 1
        print(f"Hello from MyWorker! Count: {self.counter}")


if __name__ == "__main__":
    master = Master()
    master.register_worker("MyWorker", MyWorker)  # 注册的是**类**，不是实例
    master.run()
