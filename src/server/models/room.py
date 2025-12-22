"""
房间数据模型

定义游戏房间的属性和方法。
"""

import random
from typing import Dict, List, Optional
from .player import Player


class Room:
    """游戏房间类"""

    def __init__(self, room_id: str, max_players: int = 8):
        """
        初始化房间

        Args:
            room_id: 房间唯一ID
            max_players: 最大玩家数
        """
        self.id = room_id
        self.max_players = max_players
        self.players: Dict[str, Player] = {}
        self.current_word: Optional[str] = None
        self.current_drawer: Optional[str] = None
        self.round_number = 0
        self.is_active = False
        self.guessed_players: List[str] = []

    def add_player(self, player: Player) -> bool:
        """
        添加玩家到房间

        Args:
            player: 玩家对象

        Returns:
            是否成功添加
        """
        if len(self.players) >= self.max_players:
            return False

        self.players[player.id] = player
        player.room_id = self.id
        return True

    def remove_player(self, player_id: str):
        """
        从房间移除玩家

        Args:
            player_id: 玩家ID
        """
        if player_id in self.players:
            player = self.players[player_id]
            player.room_id = None
            del self.players[player_id]

            # 如果是当前画家，结束当前回合
            if self.current_drawer == player_id:
                self.end_round()

    def start_round(self, word: str):
        """
        开始新回合

        Args:
            word: 本回合的词语
        """
        self.round_number += 1
        self.current_word = word
        self.guessed_players = []

        # 选择一个玩家作为画家
        if self.players:
            player_ids = list(self.players.keys())
            self.current_drawer = player_ids[self.round_number % len(player_ids)]

            # 设置画家状态
            for player_id, player in self.players.items():
                player.is_drawing = player_id == self.current_drawer

        self.is_active = True

    def end_round(self):
        """结束当前回合"""
        self.is_active = False
        self.current_word = None
        self.guessed_players = []

        # 重置所有玩家的画家状态
        for player in self.players.values():
            player.is_drawing = False

    def check_guess(self, player_id: str, guess: str) -> bool:
        """
        检查玩家的猜测

        Args:
            player_id: 玩家ID
            guess: 猜测的词语

        Returns:
            是否猜对
        """
        if not self.current_word or player_id == self.current_drawer:
            return False

        if player_id in self.guessed_players:
            return False

        is_correct = guess.strip().lower() == self.current_word.lower()
        if is_correct:
            self.guessed_players.append(player_id)
            # 猜对的玩家得分
            if player_id in self.players:
                points = 100 - len(self.guessed_players) * 10  # 越早猜对分数越高
                self.players[player_id].add_score(max(10, points))

        return is_correct

    def get_player_list(self) -> List[dict]:
        """
        获取房间内所有玩家的信息

        Returns:
            玩家信息列表
        """
        return [player.to_dict() for player in self.players.values()]

    def to_dict(self):
        """
        转换为字典格式

        Returns:
            包含房间信息的字典
        """
        return {
            "id": self.id,
            "max_players": self.max_players,
            "player_count": len(self.players),
            "players": self.get_player_list(),
            "round_number": self.round_number,
            "is_active": self.is_active,
            "current_drawer": self.current_drawer,
        }

    def __repr__(self):
        return (
            f"Room(id={self.id}, players={len(self.players)}/{self.max_players})"
        )
