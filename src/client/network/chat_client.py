"""
简易房间聊天客户端

连接到服务器，加入房间并发送/接收聊天消息。
协议与服务器一致：行分隔 JSON。
"""

from __future__ import annotations

import socket
import threading
import json
from typing import Callable, Optional

from src.shared.constants import DEFAULT_HOST, DEFAULT_PORT, BUFFER_SIZE, MSG_JOIN_ROOM, MSG_LEAVE_ROOM, MSG_CHAT


class ChatClient:
    """房间聊天客户端。"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.room: str = "lobby"
        self.name: str = "玩家"
        self._sock: Optional[socket.socket] = None
        self._recv_thread: Optional[threading.Thread] = None
        self._running = threading.Event()
        # 收到聊天消息时的回调: (user, text) -> None
        self.on_chat: Optional[Callable[[str, str], None]] = None

    def connect_and_join(self, room: str, name: str) -> bool:
        """连接服务器并加入房间。返回是否成功。"""
        self.room = room or "lobby"
        self.name = name or "玩家"
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self.host, self.port))
            self._sock = sock
            self._running.set()
            # 发送 join
            self._send_json({"type": MSG_JOIN_ROOM, "data": {"room": self.room, "name": self.name}})
            # 启动接收线程
            th = threading.Thread(target=self._recv_loop, name="recv_loop", daemon=True)
            th.start()
            self._recv_thread = th
            return True
        except Exception:
            self._sock = None
            return False

    def send_chat(self, text: str) -> None:
        if not text:
            return
        self._send_json({"type": MSG_CHAT, "data": {"room": self.room, "user": self.name, "text": text}})

    def close(self) -> None:
        try:
            self._running.clear()
            self._send_json({"type": MSG_LEAVE_ROOM, "data": {"room": self.room, "name": self.name}})
        except Exception:
            pass
        try:
            if self._sock:
                self._sock.close()
        except Exception:
            pass
        self._sock = None

    # 内部方法
    def _send_json(self, obj: dict) -> None:
        try:
            if not self._sock:
                return
            data = (json.dumps(obj) + "\n").encode("utf-8")
            self._sock.sendall(data)
        except Exception:
            pass

    def _recv_loop(self) -> None:
        sock = self._sock
        if not sock:
            return
        try:
            buf = b""
            while self._running.is_set():
                chunk = sock.recv(BUFFER_SIZE)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
                    t = obj.get("type")
                    data = obj.get("data", {})
                    if t == MSG_CHAT:
                        usr = str(data.get("user", ""))
                        txt = str(data.get("text", ""))
                        cb = self.on_chat
                        if cb:
                            try:
                                cb(usr, txt)
                            except Exception:
                                pass
        except Exception:
            pass

__all__ = ["ChatClient"]
