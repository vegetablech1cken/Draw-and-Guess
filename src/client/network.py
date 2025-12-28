"""
简单的客户端网络封装：负责连接服务器、收发消息并提供事件队列。
"""
from __future__ import annotations

import socket
import threading
import uuid
from queue import SimpleQueue, Empty
from typing import List, Optional

from src.shared.constants import BUFFER_SIZE, DEFAULT_HOST, DEFAULT_PORT, MSG_CHAT, MSG_CONNECT, MSG_JOIN_ROOM
from src.shared.protocols import Message


class NetworkClient:
    """线程驱动的轻量客户端，用于房间聊天等同步。"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.sock: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        self._buf = bytearray()
        self.events: SimpleQueue[Message] = SimpleQueue()
        self.player_id: Optional[str] = None
        self.player_name: Optional[str] = None
        self.room_id: str = "default"

    @property
    def connected(self) -> bool:
        return bool(self.sock) and self._running.is_set()

    def connect(self, player_name: str, player_id: Optional[str] = None, room_id: str = "default") -> bool:
        """连接服务器并加入房间。"""
        if self.connected:
            return True
        self.player_id = player_id or str(uuid.uuid4())
        self.player_name = player_name or "玩家"
        self.room_id = room_id
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self._running.set()
            self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._recv_thread.start()
            # 注册并加入房间
            self._send(Message(MSG_CONNECT, {"player_id": self.player_id, "name": self.player_name}))
            self._send(Message(MSG_JOIN_ROOM, {"room_id": self.room_id}))
            return True
        except OSError:
            self.close()
            return False

    def send_chat(self, text: str) -> None:
        if not text:
            return
        if not self.connected:
            return
        self._send(Message(MSG_CHAT, {"text": text}))

    def drain_events(self) -> List[Message]:
        items: List[Message] = []
        while True:
            try:
                items.append(self.events.get_nowait())
            except Empty:
                break
        return items

    def close(self) -> None:
        self._running.clear()
        try:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                self.sock.close()
        finally:
            self.sock = None

    # 内部方法
    def _send(self, msg: Message) -> None:
        if not self.sock:
            return
        try:
            payload = msg.to_json() + "\n"
            self.sock.sendall(payload.encode("utf-8"))
        except OSError:
            self.close()

    def _recv_loop(self) -> None:
        try:
            while self._running.is_set() and self.sock:
                data = self.sock.recv(BUFFER_SIZE)
                if not data:
                    break
                self._buf.extend(data)
                while True:
                    try:
                        idx = self._buf.index(ord("\n"))
                    except ValueError:
                        break
                    raw = self._buf[:idx]
                    del self._buf[: idx + 1]
                    self._handle_raw(raw)
        except OSError:
            pass
        finally:
            self.close()

    def _handle_raw(self, raw: bytes) -> None:
        try:
            text = raw.decode("utf-8", errors="ignore")
            msg = Message.from_json(text)
            self.events.put(msg)
        except Exception:
            # 忽略无法解析的消息
            pass


__all__ = ["NetworkClient"]
