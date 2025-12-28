"""
服务器游戏逻辑模块

实现房间、玩家、回合与计分等核心逻辑，
供网络层调用以驱动游戏流程。
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.shared.constants import (
	MAX_PLAYERS,
	MIN_PLAYERS,
	ROUND_TIME,
	DRAW_TIME,
)


@dataclass
class PlayerState:
	"""玩家状态"""

	player_id: str
	name: str
	score: int = 0
	is_connected: bool = True


@dataclass
class RoundState:
	"""回合状态"""

	round_index: int = 0
	drawer_id: Optional[str] = None
	word: Optional[str] = None
	start_ts: Optional[float] = None
	guesses: Dict[str, str] = field(default_factory=dict)
	solved_by: Optional[str] = None
	is_active: bool = False

	def time_left(self) -> int:
		if not self.is_active or self.start_ts is None:
			return 0
		deadline = self.start_ts + DRAW_TIME
		return max(0, int(deadline - time.time()))


@dataclass
class GameState:
	"""房间游戏状态"""

	players: Dict[str, PlayerState] = field(default_factory=dict)
	current_round: RoundState = field(default_factory=RoundState)
	is_started: bool = False
	rounds_played: int = 0


class GameRoom:
	"""游戏房间，管理玩家与回合"""

	def __init__(self, room_id: str, words_path: Optional[Path] = None):
		self.room_id = room_id
		self.state = GameState()
		self._words = self._load_words(words_path)
		self._drawer_cycle: List[str] = []

	# 玩家管理
	def add_player(self, player_id: str, name: str) -> bool:
		if player_id in self.state.players:
			return False
		if len(self.state.players) >= MAX_PLAYERS:
			return False
		self.state.players[player_id] = PlayerState(player_id=player_id, name=name)
		self._rebuild_drawer_cycle()
		return True

	def remove_player(self, player_id: str) -> None:
		if player_id in self.state.players:
			del self.state.players[player_id]
			self._rebuild_drawer_cycle()
			# 若画手离开，结束当前回合
			if self.state.current_round.drawer_id == player_id:
				self._force_end_round()

	def _rebuild_drawer_cycle(self) -> None:
		self._drawer_cycle = list(self.state.players.keys())
		random.shuffle(self._drawer_cycle)

	# 游戏控制
	def start_game(self) -> bool:
		if self.state.is_started:
			return False
		if len(self.state.players) < MIN_PLAYERS:
			return False
		self.state.is_started = True
		self.state.rounds_played = 0
		return self.start_round()

	def start_round(self) -> bool:
		if not self.state.is_started:
			return False
		if not self._drawer_cycle:
			self._rebuild_drawer_cycle()
		drawer_id = self._next_drawer()
		word = self._pick_word()
		self.state.current_round = RoundState(
			round_index=self.state.rounds_played + 1,
			drawer_id=drawer_id,
			word=word,
			start_ts=time.time(),
			is_active=True,
		)
		return True

	def _next_drawer(self) -> Optional[str]:
		if not self._drawer_cycle:
			return None
		# 轮转取画手
		pid = self._drawer_cycle.pop(0)
		self._drawer_cycle.append(pid)
		return pid

	def submit_guess(self, player_id: str, guess_text: str) -> Tuple[bool, int]:
		"""提交猜词，返回 (是否正确, 获得分数)"""
		rnd = self.state.current_round
		if not rnd.is_active:
			return False, 0
		if player_id == rnd.drawer_id:
			return False, 0
		if player_id not in self.state.players:
			return False, 0
		if rnd.solved_by:
			return False, 0

		rnd.guesses[player_id] = guess_text
		if self._normalize(guess_text) == self._normalize(rnd.word or ""):
			rnd.solved_by = player_id
			gained = self._score_for_first_solver(rnd)
			self.state.players[player_id].score += gained
			# 画手奖励
			if rnd.drawer_id and rnd.drawer_id in self.state.players:
				self.state.players[rnd.drawer_id].score += gained // 2
			# 回合结束
			self._finish_round()
			return True, gained
		return False, 0

	def next_round(self) -> bool:
		if not self.state.is_started:
			return False
		self.state.rounds_played += 1
		# 若时间到或已有人答对，直接开启下一回合
		return self.start_round()

	def end_game(self) -> None:
		self.state.is_started = False
		self._force_end_round()

	# 状态/工具
	def get_public_state(self) -> Dict:
		s = self.state
		r = s.current_round
		return {
			"room_id": self.room_id,
			"is_started": s.is_started,
			"round_index": r.round_index,
			"drawer_id": r.drawer_id,
			"time_left": r.time_left(),
			"players": {
				pid: {"name": p.name, "score": p.score}
				for pid, p in s.players.items()
			},
			"solved": bool(r.solved_by),
		}

	def reset_room(self) -> None:
		self.state = GameState()
		self._rebuild_drawer_cycle()

	# 内部方法
	def _finish_round(self) -> None:
		self.state.current_round.is_active = False

	def _force_end_round(self) -> None:
		self.state.current_round.is_active = False
		self.state.current_round.solved_by = None

	@staticmethod
	def _normalize(text: str) -> str:
		return (text or "").strip().lower()

	@staticmethod
	def _load_words(words_path: Optional[Path]) -> List[str]:
		base = words_path or Path(__file__).parents[3] / "data" / "words.txt"
		items: List[str] = []
		try:
			with open(base, "r", encoding="utf-8") as f:
				for line in f:
					t = line.strip()
					if not t or t.startswith("#"):
						continue
					items.append(t)
		except (FileNotFoundError, OSError, UnicodeDecodeError):
			items = ["苹果", "猫", "房子", "太阳"]
		return items

	def _pick_word(self) -> Optional[str]:
		if not self._words:
			return None
		return random.choice(self._words)

	def _score_for_first_solver(self, rnd: RoundState) -> int:
		# 根据剩余时间给分，最多 10 分，最少 3 分
		left = rnd.time_left()
		if left >= DRAW_TIME * 0.7:
			return 10
		if left >= DRAW_TIME * 0.4:
			return 7
		if left > 0:
			return 5
		return 3


__all__ = [
	"PlayerState",
	"RoundState",
	"GameState",
	"GameRoom",
]

