"""
数据模型模块

定义游戏中的数据结构，如玩家、房间、游戏状态等。
"""

from .player import Player
from .room import Room

__all__ = ["Player", "Room"]
