"""
简易房间聊天服务器（TCP）

功能：
- 监听指定 host/port
- 客户端连接后发送 join_room 消息加入房间
- 收到 chat 消息后在房间内广播
- 断开时从房间移除并广播离开提示

协议：每条消息为一行 JSON（以\n分隔），格式：
{"type": MSG_JOIN_ROOM, "data": {"room": str, "name": str}}
{"type": MSG_CHAT, "data": {"room": str, "user": str, "text": str}}
"""

from __future__ import annotations

import socket
import threading
import json
from typing import Dict, Tuple

from src.shared.constants import DEFAULT_HOST, DEFAULT_PORT, BUFFER_SIZE, MSG_JOIN_ROOM, MSG_LEAVE_ROOM, MSG_CHAT


class ChatServer:
    """支持房间的简易聊天服务器。"""

    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self._srv: socket.socket | None = None
        # rooms: room_id -> {conn: (name, addr)}
        self.rooms: Dict[str, Dict[socket.socket, Tuple[str, Tuple[str, int]]]] = {}
        self._accept_thread: threading.Thread | None = None
        self._running = threading.Event()

    def start(self) -> None:
        """启动服务器并进入接受循环。"""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 允许快速复用端口，便于开发
        try:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception:
            pass
        srv.bind((self.host, self.port))
        srv.listen(64)
        self._srv = srv
        self._running.set()
        th = threading.Thread(target=self._accept_loop, name="accept_loop", daemon=True)
        th.start()
        self._accept_thread = th

    def stop(self) -> None:
        """停止服务器，关闭所有连接。"""
        self._running.clear()
        if self._srv:
            try:
                self._srv.close()
            except Exception:
                pass
        # 关闭所有房间连接
        for room, conns in list(self.rooms.items()):
            for conn in list(conns.keys()):
                try:
                    conn.close()
                except Exception:
                    pass
            self.rooms[room].clear()

    def _accept_loop(self) -> None:
        assert self._srv is not None
        while self._running.is_set():
            try:
                conn, addr = self._srv.accept()
            except OSError:
                break
            th = threading.Thread(target=self._handle_client, args=(conn, addr), daemon=True)
            th.start()

    def _handle_client(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        room_id: str | None = None
        user_name: str = "匿名"
        f = conn.makefile("rwb", buffering=0)
        try:
            while self._running.is_set():
                data = conn.recv(BUFFER_SIZE)
                if not data:
                    break
                # 支持粘包：按行拆分
                for line in data.split(b"\n"):
                    if not line:
                        continue
                    try:
                        obj = json.loads(line.decode("utf-8", errors="ignore"))
                    except Exception:
                        continue
                    msg_type = obj.get("type")
                    payload = obj.get("data", {})
                    if msg_type == MSG_JOIN_ROOM:
                        room_id = str(payload.get("room")) if payload.get("room") else "lobby"
                        user_name = str(payload.get("name")) if payload.get("name") else user_name
                        # 注册到房间
                        room = self.rooms.setdefault(room_id, {})
                        room[conn] = (user_name, addr)
                        # 广播系统提示
                        self._broadcast(room_id, {
                            "type": MSG_CHAT,
                            "data": {"room": room_id, "user": "系统", "text": f"{user_name} 加入房间"},
                        })
                    elif msg_type == MSG_CHAT:
                        rid = str(payload.get("room")) if payload.get("room") else (room_id or "lobby")
                        txt = str(payload.get("text", ""))
                        usr = str(payload.get("user", user_name))
                        self._broadcast(rid, {"type": MSG_CHAT, "data": {"room": rid, "user": usr, "text": txt}})
                    elif msg_type == MSG_LEAVE_ROOM:
                        rid = str(payload.get("room")) if payload.get("room") else room_id
                        nm = str(payload.get("name", user_name))
                        self._remove_conn(rid, conn)
                        self._broadcast(rid or "lobby", {
                            "type": MSG_CHAT,
                            "data": {"room": rid or "lobby", "user": "系统", "text": f"{nm} 离开房间"},
                        })
                    else:
                        # 未知消息类型：忽略
                        continue
        except Exception:
            pass
        finally:
            # 清理连接
            if room_id:
                self._remove_conn(room_id, conn)
                try:
                    self._broadcast(room_id, {
                        "type": MSG_CHAT,
                        "data": {"room": room_id, "user": "系统", "text": f"{user_name} 断开连接"},
                    })
                except Exception:
                    pass
            try:
                f.close()
            except Exception:
                pass
            try:
                conn.close()
            except Exception:
                pass

    def _broadcast(self, room_id: str, obj: Dict) -> None:
        """向指定房间内所有连接广播 JSON 消息（行分隔）。"""
        data = (json.dumps(obj) + "\n").encode("utf-8")
        conns = self.rooms.get(room_id)
        if not conns:
            return
        dead: list[socket.socket] = []
        for conn in conns.keys():
            try:
                conn.sendall(data)
            except Exception:
                dead.append(conn)
        for d in dead:
            self._remove_conn(room_id, d)

    def _remove_conn(self, room_id: str | None, conn: socket.socket) -> None:
        if not room_id:
            return
        conns = self.rooms.get(room_id)
        if not conns:
            return
        if conn in conns:
            try:
                del conns[conn]
            except Exception:
                pass


__all__ = ["ChatServer"]
