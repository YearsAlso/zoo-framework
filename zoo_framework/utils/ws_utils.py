"""ws_utils - zoo_framework/utils/ws_utils.py

WebSocket工具模块,提供WebSocket相关功能.

功能:
- WebSocket连接管理
- 消息发送和接收
- 连接状态监控
- 错误处理

作者: XiangMeng
版本: 0.5.1-beta

import asyncio
import json
from typing import Any


class WsUtils:
    """WebSocket工具类

    提供WebSocket操作相关的实用方法.
    """

    @classmethod
    async def send_json(cls, websocket, data: dict[str, Any]) -> bool:
        """发送JSON数据"""
        try:
            await websocket.send(json.dumps(data))
            return True
        except Exception:
            return False

    @classmethod
    async def receive_json(cls, websocket) -> dict[str, Any] | None:
        """接收JSON数据"""
        try:
            message = await websocket.recv()
            return json.loads(message)
        except Exception:
            return None

    @classmethod
    async def ping(cls, websocket) -> bool:
        """发送ping消息"""
        try:
            await websocket.ping()
            return True
        except Exception:
            return False

    @classmethod
    def create_message(cls, type: str, data: dict[str, Any]) -> dict[str, Any]:
        """创建标准消息格式"""
        return {
            'type': type,
            'data': data,
            'timestamp': asyncio.get_event_loop().time()
        }

    @classmethod
    def validate_message(cls, message: dict[str, Any]) -> bool:
        """验证消息格式"""
        required_keys = ['type', 'data', 'timestamp']
        return all(key in message for key in required_keys)
"""
