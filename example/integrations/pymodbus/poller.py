"""用 Zoo Framework 管理 Modbus 设备的轮询与状态 —— 进程内、无需 broker 的采集循环.

本示例与 ``native/reference/modbus_rtu.py`` 里已实现的 Modbus 响应帧解析任务**同源**：
都以 Modbus 协议作为「真实设备 I/O」的载体。这里走**纯 Python** 路径（不依赖原生扩展），
演示框架替 pymodbus 使用者补上的那一层：

* **调度**：一个常驻 Worker 按固定 ``delay_time`` 轮询寄存器，不必自己写 sleep-loop 线程。
* **状态**：最近一次读数与「越限次数」写入状态机，落盘后重启可恢复（``os.replace`` 原子写）。
* **可观测**：设备不可用/读错误会被记入输出，而不是静默丢读。

为做到「复制即跑」，本文件自带一个**模拟设备**（进程内起一个 Modbus TCP server），
不依赖外部硬件；另有一个模拟线程通过 Modbus 写接口更新温度，让读数有变化。

第三方依赖（**不是** ``zoo-framework`` 的安装面；用 pymodbus 3.16 的 SimData/SimDevice）::

    pip install "pymodbus>=3.16,<4"

运行（在本文件所在目录；Ctrl-C 停止）::

    python poller.py

期望输出：每秒一行 ``[register_poll_worker] poll #N temp=.. pressure=..``；
模拟温度循环上升，越过阈值时追加 ``threshold breached (#K)``，``poll #`` 持续递增。

何时**不该**用本框架：见同目录 ``README.md`` 的「何时不该用本框架」一节。
"""

from __future__ import annotations

import contextlib
import threading
import time

from pymodbus.client import ModbusTcpClient
from pymodbus.server import StartTcpServer
from pymodbus.simulator import DataType, SimData, SimDevice

from zoo_framework.core import Master
from zoo_framework.statemachine import StateMachineManager
from zoo_framework.workers import BaseWorker

HOST = "127.0.0.1"
PORT = 5020
UNIT_ID = 1

# 模拟设备：寄存器 0 = 温度(°C)，寄存器 1 = 压力(kPa)，寄存器 10 = 回写轮询计数
TEMP_REG = 0
PRESSURE_REG = 1
POLL_COUNT_REG = 10
REGISTER_COUNT = 16
TEMP_THRESHOLD = 25

# 状态机 scope 与键
SCOPE = "Modbus"
POLLS_KEY = "device.polls"
LATEST_KEY = "device.latest"
BREACH_KEY = "device.thresholdBreaches"


def _drift_temperature() -> None:
    """模拟设备更新温度：用 Modbus 写接口把新读数写进保持寄存器，循环 22→24→26→28."""
    client = ModbusTcpClient(HOST, port=PORT)
    for _ in range(120):  # 约 2 分钟；之后保持最后一次读数
        if not client.connected and not client.connect():
            time.sleep(1.0)
            continue
        temperature = 22 + 2 * (int(time.time()) // 2 % 4)
        client.write_registers(TEMP_REG, [temperature], device_id=UNIT_ID)
        time.sleep(2)
    client.close()


def _serve_simulated_device() -> None:
    """在后台线程起一个模拟 Modbus TCP 设备（pymodbus 3.16 的 SimData/SimDevice）."""
    registers = SimData(
        address=0,
        count=REGISTER_COUNT,
        values=[22, 1013] + [0] * (REGISTER_COUNT - 2),
        datatype=DataType.REGISTERS,
    )
    device = SimDevice(id=UNIT_ID, simdata=[registers])
    StartTcpServer(context=device, address=(HOST, PORT))


class RegisterPollWorker(BaseWorker):
    """常驻 Worker：按框架排期轮询 Modbus 寄存器，把读数与统计落盘."""

    def __init__(self):
        # BaseWorker.__init__ 会回调 _on_create，故依赖属性必须先于 super() 赋好。
        self._client = ModbusTcpClient(HOST, port=PORT)
        super().__init__({"is_loop": True, "delay_time": 1.0, "name": "register_poll_worker"})

    def _on_create(self):
        """建立连接；失败留给 ``_execute`` 重试，不让异常逃逸出生命周期."""
        self._connect()

    def _connect(self) -> bool:
        try:
            return bool(self._client.connect())
        except Exception as exc:  # 设备可能还没起来
            print(f"[register_poll_worker] connect failed: {exc}", flush=True)
            return False

    def _destroy(self, result):
        """停机时释放连接."""
        with contextlib.suppress(Exception):
            self._client.close()

    def _execute(self):
        """读两个寄存器 + 回写轮询计数，把读数与统计写入状态机."""
        if not self._client.connected and not self._connect():
            return

        response = self._client.read_holding_registers(TEMP_REG, count=2, device_id=UNIT_ID)
        if response.isError():
            print(f"[register_poll_worker] read error: {response}", flush=True)
            return

        temperature, pressure = response.registers

        state_machine = StateMachineManager()
        if not state_machine.have_loaded():
            # 框架尚未从 zooStates.pic 恢复状态（StateMachineWorker 首轮才载入）。
            # 先不计数，避免把「恢复前的 0」当成初始值、覆盖掉上次落盘的进度。
            return

        polls = (state_machine.get_state(SCOPE, POLLS_KEY) or 0) + 1
        state_machine.set_state(SCOPE, POLLS_KEY, polls)
        state_machine.set_state(
            SCOPE, LATEST_KEY, {"temperature": temperature, "pressure": pressure}
        )

        breach_note = ""
        if temperature > TEMP_THRESHOLD:
            breaches = (state_machine.get_state(SCOPE, BREACH_KEY) or 0) + 1
            state_machine.set_state(SCOPE, BREACH_KEY, breaches)
            breach_note = f" threshold breached (#{breaches})"

        # 反向写：把轮询计数写回设备寄存器，示意读写双向（不代表真实设备语义）
        self._client.write_registers(POLL_COUNT_REG, [polls], device_id=UNIT_ID)

        print(
            f"[register_poll_worker] poll #{polls} temp={temperature} "
            f"pressure={pressure}{breach_note}",
            flush=True,
        )


def main() -> None:
    threading.Thread(target=_serve_simulated_device, name="modbus-device", daemon=True).start()
    time.sleep(1.0)  # 等设备起监听
    threading.Thread(target=_drift_temperature, name="device-drift", daemon=True).start()

    master = Master()
    master.register_worker("RegisterPollWorker", RegisterPollWorker)
    master.run()  # 阻塞在调度循环，Ctrl-C 停止


if __name__ == "__main__":
    main()
