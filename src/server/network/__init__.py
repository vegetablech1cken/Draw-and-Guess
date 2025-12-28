"""
网络通信模块

处理 Socket 连接、消息收发、协议解析等网络功能。

设计目标：
- 提供基础的 TCP 服务器，支持多个客户端并发连接
- 使用基于 JSON 的应用层协议（参见 src/shared/protocols.py）
- 按消息类型路由到游戏房间逻辑（参见 src/server/game/__init__.py）
- 支持房间的广播、单发与会话管理
"""

from __future__ import annotations

import socket
import threading
import json
import traceback
from typing import Dict, Optional, Tuple

from src.shared.constants import (
	DEFAULT_HOST,
	DEFAULT_PORT,
	BUFFER_SIZE,
	MSG_CONNECT,
	MSG_DISCONNECT,
	MSG_JOIN_ROOM,
	MSG_LEAVE_ROOM,
	MSG_DRAW,
	MSG_GUESS,
	MSG_CHAT,
	MSG_START_GAME,
	MSG_END_GAME,
	MSG_NEXT_ROUND,
)
from src.shared.protocols import Message
from src.server.game import GameRoom


class ClientSession:
	"""客户端会话，封装连接与玩家信息"""

	def __init__(self, conn: socket.socket, addr: Tuple[str, int]):
		self.conn = conn
		self.addr = addr
		self.player_id: Optional[str] = None
		self.player_name: Optional[str] = None
		self.room_id: Optional[str] = None
		self._recv_buffer = bytearray()

	def fileno(self) -> int:
		return self.conn.fileno()

	def close(self) -> None:
		try:
			self.conn.close()
		except Exception:
			pass


class NetworkServer:
	"""网络服务器，负责会话管理与消息路由"""

	def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT):
		self.host = host
		self.port = port
		self._sock: Optional[socket.socket] = None
		self._accept_thread: Optional[threading.Thread] = None
		self._running = threading.Event()
		self.sessions: Dict[int, ClientSession] = {}
		# // 简化：单房间实现，可扩展为多房间字典
		self.room = GameRoom(room_id="default")

	# 服务器生命周期
	def start(self) -> None:
		"""启动服务器并进入 Accept 循环"""
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		# // 允许快速重启服务
		self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._sock.bind((self.host, self.port))
		self._sock.listen(32)
		self._running.set()
		self._accept_thread = threading.Thread(target=self._accept_loop, name="accept-loop", daemon=True)
		self._accept_thread.start()

	def stop(self) -> None:
		"""停止服务器并关闭所有会话"""
		self._running.clear()
		try:
			if self._sock:
				# // 触发 accept 退出
				try:
					self._sock.shutdown(socket.SHUT_RDWR)
				except Exception:
					pass
				self._sock.close()
		finally:
			self._sock = None
		# // 关闭所有客户端连接
		for sess in list(self.sessions.values()):
			sess.close()
		self.sessions.clear()

	# 接入与会话线程
	def _accept_loop(self) -> None:
		"""Accept 新连接并为其创建会话线程"""
		while self._running.is_set():
			try:
				conn, addr = self._sock.accept()  # type: ignore[arg-type]
			except OSError:
				# // 套接字已关闭或出错，退出循环
				break
			sess = ClientSession(conn, addr)
			self.sessions[conn.fileno()] = sess
			t = threading.Thread(target=self._session_loop, args=(sess,), daemon=True)
			t.start()

	def _session_loop(self, sess: ClientSession) -> None:
		"""单会话收发循环：按行（\n）读取 JSON 消息并路由"""
		conn = sess.conn
		try:
			while self._running.is_set():
				data = conn.recv(BUFFER_SIZE)
				if not data:
					break
				sess._recv_buffer.extend(data)
				# // 简单分包：按换行符划分消息
				while True:
					try:
						idx = sess._recv_buffer.index(ord("\n"))
					except ValueError:
						break
					raw = sess._recv_buffer[:idx]
					del sess._recv_buffer[: idx + 1]
					self._handle_raw_message(sess, raw)
		except ConnectionResetError:
			pass
		except Exception:
			traceback.print_exc()
		finally:
			self._on_disconnect(sess)

	# 消息处理
	def _handle_raw_message(self, sess: ClientSession, raw: bytes) -> None:
		"""原始字节消息 -> JSON -> Message 并路由"""
		try:
			text = raw.decode("utf-8", errors="ignore")
			msg = Message.from_json(text)
		except Exception:
			# // 非法消息，忽略
			return
		self._route_message(sess, msg)

	def _route_message(self, sess: ClientSession, msg: Message) -> None:
		"""根据消息类型路由到对应处理函数"""
		t = msg.type
		data = msg.data
		if t == MSG_CONNECT:
			# // 注册玩家，要求 data: {player_id, name}
			sess.player_id = str(data.get("player_id") or sess.addr[0])
			sess.player_name = str(data.get("name") or f"Player-{sess.addr[1]}")
			self._send(sess, Message("ack", {"ok": True, "event": MSG_CONNECT}))
		elif t == MSG_JOIN_ROOM:
			# // 加入房间，并添加玩家到 GameRoom
			sess.room_id = str(data.get("room_id") or "default")
			if sess.player_id and sess.player_name:
				added = self.room.add_player(sess.player_id, sess.player_name)
				self._send(sess, Message("ack", {"ok": added, "event": MSG_JOIN_ROOM}))
				self.broadcast(Message("room_state", self.room.get_public_state()))
		elif t == MSG_LEAVE_ROOM:
			# // 离开房间并更新房间状态
			if sess.player_id:
				self.room.remove_player(sess.player_id)
			sess.room_id = None
			self._send(sess, Message("ack", {"ok": True, "event": MSG_LEAVE_ROOM}))
			self.broadcast(Message("room_state", self.room.get_public_state()))
		elif t == MSG_START_GAME:
			# // 启动游戏并广播房间状态
			ok = self.room.start_game()
			self.broadcast(Message("room_state", self.room.get_public_state()))
			self.broadcast(Message("event", {"type": MSG_START_GAME, "ok": ok}))
		elif t == MSG_NEXT_ROUND:
			ok = self.room.next_round()
			self.broadcast(Message("room_state", self.room.get_public_state()))
			self.broadcast(Message("event", {"type": MSG_NEXT_ROUND, "ok": ok}))
		elif t == MSG_END_GAME:
			self.room.end_game()
			self.broadcast(Message("room_state", self.room.get_public_state()))
			self.broadcast(Message("event", {"type": MSG_END_GAME, "ok": True}))
		elif t == MSG_GUESS:
			# // 猜词：data: {text}
			guess_text = str(data.get("text") or "")
			if sess.player_id:
				ok, score = self.room.submit_guess(sess.player_id, guess_text)
				self._send(sess, Message("guess_result", {"ok": ok, "score": score}))
				# // 广播最新房间状态
				self.broadcast(Message("room_state", self.room.get_public_state()))
		elif t == MSG_DRAW:
			# // 绘图：透传画笔数据给其他客户端（不入房间逻辑）
			payload = {"by": sess.player_id, "data": data}
			self.broadcast(Message("draw_sync", payload), exclude=sess)
		elif t == MSG_CHAT:
			# // 聊天广播
			payload = {
				"by": sess.player_id,
				"by_name": sess.player_name,
				"text": str(data.get("text") or ""),
			}
			self.broadcast(Message("chat", payload))
		elif t == MSG_DISCONNECT:
			self._on_disconnect(sess)
		else:
			# // 未知消息类型，可返回错误或忽略
			self._send(sess, Message("error", {"msg": f"unknown type: {t}"}))

	# 发送/广播
	def _send(self, sess: ClientSession, msg: Message) -> None:
		try:
			text = msg.to_json() + "\n"
			sess.conn.sendall(text.encode("utf-8"))
		except Exception:
			self._on_disconnect(sess)

	def broadcast(self, msg: Message, exclude: Optional[ClientSession] = None) -> None:
		for s in list(self.sessions.values()):
			if exclude and s is exclude:
				continue
			self._send(s, msg)

	# 断开清理
	def _on_disconnect(self, sess: ClientSession) -> None:
		try:
			# // 移除会话并更新房间
			if sess.player_id:
				self.room.remove_player(sess.player_id)
			sess.close()
		finally:
			self.sessions.pop(sess.fileno(), None)
			# // 广播房间状态供客户端更新 UI
			try:
				self.broadcast(Message("room_state", self.room.get_public_state()))
			except Exception:
				pass


__all__ = [
	"ClientSession",
	"NetworkServer",
]

