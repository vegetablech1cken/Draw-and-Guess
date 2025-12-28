"""
服务器数据模型

定义服务器侧的核心数据结构：玩家、房间、回合、猜词记录等。
这些模型与网络/游戏逻辑解耦，方便复用与测试。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from src.shared.constants import MAX_PLAYERS, MIN_PLAYERS, DRAW_TIME


@dataclass
class Player:
	"""玩家模型"""

	player_id: str
	name: str
	score: int = 0
	is_connected: bool = True
	is_ready: bool = False

	def to_dict(self) -> Dict:
		return asdict(self)


@dataclass
class GuessRecord:
	"""猜词记录"""

	player_id: str
	text: str
	timestamp: float
	is_correct: bool = False

	def to_dict(self) -> Dict:
		return asdict(self)


@dataclass
class Round:
	"""回合模型"""

	index: int = 0
	drawer_id: Optional[str] = None
	word: Optional[str] = None
	start_ts: Optional[float] = None
	duration: int = DRAW_TIME
	solved_by: Optional[str] = None
	guesses: List[GuessRecord] = field(default_factory=list)
	is_active: bool = False

	def time_left(self) -> int:
		if not self.is_active or self.start_ts is None:
			return 0
		return max(0, int(self.start_ts + self.duration - time.time()))

	def to_dict(self, hide_word: bool = True) -> Dict:
		return {
			"index": self.index,
			"drawer_id": self.drawer_id,
			"word": None if hide_word else self.word,
			"time_left": self.time_left(),
			"solved_by": self.solved_by,
			"is_active": self.is_active,
			"guesses": [g.to_dict() for g in self.guesses],
		}


@dataclass
class Room:
	"""房间模型"""

	room_id: str
	players: Dict[str, Player] = field(default_factory=dict)
	current_round: Round = field(default_factory=Round)
	created_at: float = field(default_factory=time.time)
	max_players: int = MAX_PLAYERS
	min_players: int = MIN_PLAYERS
	is_started: bool = False

	def add_player(self, player_id: str, name: str) -> bool:
		if player_id in self.players:
			return False
		if len(self.players) >= self.max_players:
			return False
		self.players[player_id] = Player(player_id=player_id, name=name)
		return True

	def remove_player(self, player_id: str) -> None:
		self.players.pop(player_id, None)

	def mark_ready(self, player_id: str, ready: bool = True) -> None:
		if player_id in self.players:
			self.players[player_id].is_ready = ready

	def can_start(self) -> bool:
		return len(self.players) >= self.min_players and all(
			player.is_ready for player in self.players.values()
		)

	def snapshot(self, hide_word: bool = True) -> Dict:
		return {
			"room_id": self.room_id,
			"is_started": self.is_started,
			"players": {pid: p.to_dict() for pid, p in self.players.items()},
			"round": self.current_round.to_dict(hide_word=hide_word),
		}


__all__ = [
	"Player",
	"GuessRecord",
	"Round",
	"Room",
]

