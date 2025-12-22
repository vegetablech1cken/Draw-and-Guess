"""
玩家数据模型

定义玩家的属性和方法。
"""

from typing import Optional
import time


class Player:
    """玩家类"""

    def __init__(self, player_id: str, name: str, conn=None):
        """
        初始化玩家

        Args:
            player_id: 玩家唯一ID
            name: 玩家名称
            conn: 客户端连接对象
        """
        self.id = player_id
        self.name = name
        self.conn = conn
        self.score = 0
        self.room_id: Optional[str] = None
        self.is_drawing = False
        self.last_activity = time.time()

    def update_activity(self):
        """更新最后活动时间"""
        self.last_activity = time.time()

    def add_score(self, points: int):
        """
        增加分数

        Args:
            points: 要增加的分数
        """
        self.score += points

    def reset_score(self):
        """重置分数"""
        self.score = 0

    def to_dict(self):
        """
        转换为字典格式

        Returns:
            包含玩家信息的字典
        """
        return {
            "id": self.id,
            "name": self.name,
            "score": self.score,
            "is_drawing": self.is_drawing,
        }

    def __repr__(self):
        return f"Player(id={self.id}, name={self.name}, score={self.score})"
