from core import worker
from device import WebsocketDevice
from device import WifiDevice
from .base_thread import BaseThread
from utils import WsUtils


@worker()
class WifiThread(BaseThread):
    def __init__(self):
        BaseThread.__init__(self, {
            "is_loop": True,
            "delay_time": 15,
            "name": "WifiThread"
        })
    
    def _destroy(self, result):
        pass
    
    def _execute(self):
        self.device = WifiDevice()
        is_connected = self.device.is_connected()
        message = WsUtils.build_websocket_contents({"signalValue": 0, "connect": False},
                                                   "system-wifi-signal")
        # 如果已经连接，检测信号强度
        if is_connected is True:
            wifi_info = self.device.get_wifi_info()
            signal = 0
            if wifi_info is None:
                signal = 0
            elif wifi_info.signal is None:
                signal = 0
            else:
                signal = wifi_info.signal
            
            message = WsUtils.build_websocket_contents({"signalValue": signal, "connect": is_connected},
                                                       "system-wifi-signal")
        
        ws_dev = WebsocketDevice()
        ws_dev.push_message(message)
