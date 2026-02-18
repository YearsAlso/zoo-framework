"""
ws_utils - zoo_framework/utils/ws_utils.py

模块功能描述：
TODO: 添加模块功能描述
    """WsUtils - 类功能描述

    TODO: 添加类功能详细描述
    """

作者: XiangMeng
版本: 0.5.1-beta
"""

import json
import time


class WsUtils:
    @classmethod
    def build_websocket_contents(cls, result, topic):
        result = json.dumps(result)
        return json.dumps(
            {
                "topic": topic,
                "param": result,
                "tags": "",
                "timestamp": int(time.time()),
                "sourceId": "timers",
                "targetId": "app",
                "paramsType": "json",
            }
        )

    @classmethod
    def build_websocket_heart_check(cls):
        return json.dumps(
            {
                "topic": "connect",
                "param": "test",
                "tags": "",
                "timestamp": int(time.time()),
                "sourceId": "timers",
                "targetId": "service",
                "paramsType": "txt",
            }
        )
