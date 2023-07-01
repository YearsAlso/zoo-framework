import json
import time


class WsUtils:
    @classmethod
    def build_websocket_contents(cls, result, topic):
        result = json.dumps(result)
        return json.dumps(
            {"topic": topic, "param": result, "tags": "", "timestamp": int(time.time()), "sourceId": "timers",
             "targetId": "app", "paramsType": "json", })

    @classmethod
    def build_websocket_heart_check(cls):
        return json.dumps(
            {"topic": "connect", "param": "test", "tags": "", "timestamp": int(time.time()), "sourceId": "timers",
             "targetId": "service", "paramsType": "txt", })
