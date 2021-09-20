from core import worker
from device import WebsocketDevice
from device import MobileSignalDevice
from threads.base_thread import BaseThread
from utils import WsUtils


@worker()
class MobileSignalThread(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 30,
            "name": "MobileSignalThread"
        })
    
    def send_message(self, message):
        ws_dev = WebsocketDevice()
        ws_dev.push_message(message)
    
    def _execute(self):
        mobile_device = MobileSignalDevice()
        is_connected = mobile_device.is_connected()
        signal_decibel = mobile_device.signal_decibel()
        message = WsUtils.build_websocket_contents({"signalValue": signal_decibel, "connect": is_connected}, "system-mobile-signal")
        self.send_message(message)
