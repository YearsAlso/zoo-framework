import asyncio

from core import worker
from device import WebsocketDevice
from utils import WsUtils
from .base_thread import BaseThread


@worker()
class WebSocketThread(BaseThread):
    
    def __init__(self):
        BaseThread.__init__(self, props={
            "is_loop": True,
            "delay_time": 3,
            "name": "WebSocketThread"
        })
        self.device = WebsocketDevice()
    
    def build_websocket_heart_check(self):
        return WsUtils.build_websocket_heart_check()
    
    def _execute(self):
        heart_check = self.build_websocket_heart_check()
        self.device.push_message(heart_check)
        if not self.device.is_open:
            ws = self.device.init()
            ws.run_forever()
        # self.device.send_message()
