"""
通信协议定义

定义客户端和服务器之间的通信协议格式。
"""

import json
from typing import Any, Dict


class Message:
    """消息基类"""

    def __init__(self, msg_type: str, data: Dict[str, Any] = None):
        """
        初始化消息

        Args:
            msg_type: 消息类型
            data: 消息数据
        """
        self.type = msg_type
        self.data = data or {}

    def to_json(self) -> str:
        """将消息转换为 JSON 字符串"""
        return json.dumps({"type": self.type, "data": self.data})

    @classmethod
    def from_json(cls, json_str: str) -> "Message":
        """从 JSON 字符串创建消息"""
        obj = json.loads(json_str)
        return cls(obj["type"], obj.get("data", {}))

    def __repr__(self):
        return f"Message(type={self.type}, data={self.data})"


# TODO: 实现具体的消息类型
class ChatMessage(Message):
    """聊天消息：包含房间、用户与文本。"""

    def __init__(self, room: str, user: str, text: str):
        super().__init__("chat", {"room": room, "user": user, "text": text})

