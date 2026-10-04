import json
import time
from typing import Any


class WsUtils:
    @classmethod
    def build_websocket_contents(cls, result: Any, topic: str) -> str:
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
    def build_websocket_heart_check(cls) -> str:
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
