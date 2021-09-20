import _thread
import asyncio
import json
import threading
import time

import websocket

from core import singleton
from core.aop import websocket_events
from utils import LogUtils, WsUtils


@singleton
class WebsocketDevice:
    _closed = True
    ws = None
    
    def __init__(self):
        self.messages = [
        ]
    
    def init(self):
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp("ws://127.0.0.1:5000/ws",
                                                    on_open=self.on_open,
                                                    on_message=self.on_message,
                                                    on_error=self.on_error,
                                                    on_close=self.on_close)
        return self.ws
    
    def push_messages(self, messages: list):
        self.messages.extend(messages)
    
    def push_message(self, message):
        self.messages.append(message)
    
    @property
    def is_open(self):
        return not self._closed
    
    def on_message(self, ws, message):
        print(message)
        try:
            message = json.loads(message)
            if message.get('resultType') == "json":
                topic = message.get('topic')
                recv = json.loads(message.get('result'))
                if websocket_events.get(topic):
                    websocket_events[topic](recv)
        except Exception as e:
            LogUtils.error(str(e), WebsocketDevice.__name__)
    
    def on_error(self, ws, error):
        print(error)
    
    def on_close(self, ws, close_status_code, close_msg):
        self._closed = True
        print("### closed ###")
    
    def on_open(self, ws):
        def run(*args):
            for message in self.messages:
                # time.sleep(1)
                ws.send(message)
            time.sleep(1)
            # ws.close()
        
        _thread.start_new_thread(run, ())
        self._closed = False
