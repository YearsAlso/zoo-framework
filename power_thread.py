from core import worker
from device import WebsocketDevice
from device.power_serial_device import PowerSerialDevice
from .base_thread import BaseThread
from utils import WsUtils, LogUtils


@worker()
class PowerThread(BaseThread):
    
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 30,
            "name": "PowerThread"
        })
    
    def send_message(self, message):
        ws_dev = WebsocketDevice()
        ws_dev.push_message(message)
    
    def _execute(self):
        charging = 0
        electricity = False
        
        try:
            serial_port = PowerSerialDevice()
            serial_port.get_result()
            charging = serial_port.is_charging()
            electricity = serial_port.get_electricity()
        except Exception as e:
            LogUtils.error(str(e))
        
        message = WsUtils.build_websocket_contents({"powerValue": electricity, "charging": charging}, "system-power")
        self.send_message(message)
