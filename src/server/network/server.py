"""
Socket 服务器实现

处理客户端连接和消息通信。
"""

import socket
import threading
import logging
import json
import uuid
import random
from typing import Dict, Optional

from src.shared.constants import BUFFER_SIZE
from src.server.models import Player, Room

logger = logging.getLogger(__name__)


class GameServer:
    """游戏服务器类"""

    def __init__(self, host: str, port: int):
        """
        初始化服务器

        Args:
            host: 监听地址
            port: 监听端口
        """
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.players: Dict[str, Player] = {}
        self.rooms: Dict[str, Room] = {}
        self.lock = threading.Lock()

        # 创建默认房间
        self.default_room = Room("default", max_players=8)
        self.rooms["default"] = self.default_room

    def start(self):
        """启动服务器"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            self.running = True

            logger.info(f"服务器启动成功，监听 {self.host}:{self.port}")

            # 启动接受连接的线程
            accept_thread = threading.Thread(target=self._accept_connections)
            accept_thread.daemon = True
            accept_thread.start()

            return True

        except Exception as e:
            logger.error(f"服务器启动失败: {e}")
            return False

    def _accept_connections(self):
        """接受客户端连接"""
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                logger.info(f"新客户端连接: {address}")

                # 为每个客户端创建处理线程
                client_thread = threading.Thread(
                    target=self._handle_client, args=(client_socket, address)
                )
                client_thread.daemon = True
                client_thread.start()

            except Exception as e:
                if self.running:
                    logger.error(f"接受连接错误: {e}")

    def _handle_client(self, client_socket: socket.socket, address):
        """
        处理客户端连接

        Args:
            client_socket: 客户端套接字
            address: 客户端地址
        """
        player_id = None
        try:
            # 接收客户端消息
            while self.running:
                data = client_socket.recv(BUFFER_SIZE)
                if not data:
                    break

                # 解析消息
                try:
                    message = json.loads(data.decode("utf-8"))
                    player_id = self._process_message(
                        message, client_socket, player_id
                    )
                except json.JSONDecodeError:
                    logger.error(f"无效的JSON数据: {data}")
                except Exception as e:
                    logger.error(f"处理消息错误: {e}")

        except Exception as e:
            logger.error(f"客户端连接错误: {e}")
        finally:
            # 清理断开连接的玩家
            if player_id:
                self._remove_player(player_id)
            client_socket.close()
            logger.info(f"客户端断开连接: {address}")

    def _process_message(
        self, message: dict, client_socket: socket.socket, player_id: Optional[str]
    ) -> Optional[str]:
        """
        处理客户端消息

        Args:
            message: 消息字典
            client_socket: 客户端套接字
            player_id: 玩家ID

        Returns:
            玩家ID
        """
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "connect":
            # 处理连接消息
            player_name = data.get("name", "Anonymous")
            player_id = str(uuid.uuid4())
            player = Player(player_id, player_name, client_socket)

            with self.lock:
                self.players[player_id] = player
                # 自动加入默认房间
                self.default_room.add_player(player)

            # 发送连接成功消息
            self._send_message(
                client_socket,
                {
                    "type": "connected",
                    "data": {
                        "player_id": player_id,
                        "room_id": "default",
                        "players": self.default_room.get_player_list(),
                    },
                },
            )

            # 广播新玩家加入
            self._broadcast_to_room(
                "default",
                {
                    "type": "player_joined",
                    "data": {"player": player.to_dict()},
                },
                exclude_player=player_id,
            )

            logger.info(f"玩家 {player_name} 已连接，ID: {player_id}")

        elif msg_type == "draw":
            # 处理绘图消息
            if player_id:
                # 广播绘图数据到房间
                player = self.players.get(player_id)
                if player and player.room_id:
                    self._broadcast_to_room(
                        player.room_id,
                        {"type": "draw", "data": data},
                        exclude_player=player_id,
                    )

        elif msg_type == "guess":
            # 处理猜测消息
            if player_id:
                player = self.players.get(player_id)
                if player and player.room_id:
                    room = self.rooms.get(player.room_id)
                    if room:
                        guess = data.get("guess", "")
                        is_correct = room.check_guess(player_id, guess)

                        # 发送猜测结果
                        self._send_message(
                            client_socket,
                            {
                                "type": "guess_result",
                                "data": {
                                    "correct": is_correct,
                                    "score": player.score,
                                },
                            },
                        )

                        # 广播猜测消息或正确答案
                        if is_correct:
                            self._broadcast_to_room(
                                player.room_id,
                                {
                                    "type": "player_guessed",
                                    "data": {
                                        "player_id": player_id,
                                        "player_name": player.name,
                                    },
                                },
                            )
                        else:
                            # 广播聊天消息
                            self._broadcast_to_room(
                                player.room_id,
                                {
                                    "type": "chat",
                                    "data": {
                                        "player_name": player.name,
                                        "message": guess,
                                    },
                                },
                            )

        elif msg_type == "start_game":
            # 处理开始游戏消息
            if player_id:
                player = self.players.get(player_id)
                if player and player.room_id:
                    self._start_game(player.room_id)

        elif msg_type == "chat":
            # 处理聊天消息
            if player_id:
                player = self.players.get(player_id)
                if player and player.room_id:
                    self._broadcast_to_room(
                        player.room_id,
                        {
                            "type": "chat",
                            "data": {
                                "player_name": player.name,
                                "message": data.get("message", ""),
                            },
                        },
                    )

        return player_id

    def _start_game(self, room_id: str):
        """
        开始游戏

        Args:
            room_id: 房间ID
        """
        room = self.rooms.get(room_id)
        if not room or len(room.players) < 2:
            return

        # 加载词库并选择一个词
        try:
            with open("data/words.txt", "r", encoding="utf-8") as f:
                words = [line.strip() for line in f if line.strip()]
            if not words:
                logger.error("词库文件为空")
                return
            
            word = random.choice(words)
            room.start_round(word)

            # 通知所有玩家游戏开始
            for player_id, player in room.players.items():
                if player.is_drawing:
                    # 告诉画家词语
                    self._send_message(
                        player.conn,
                        {
                            "type": "game_started",
                            "data": {
                                "word": word,
                                "is_drawer": True,
                                "round": room.round_number,
                            },
                        },
                    )
                else:
                    # 告诉其他玩家游戏开始
                    self._send_message(
                        player.conn,
                        {
                            "type": "game_started",
                            "data": {
                                "is_drawer": False,
                                "round": room.round_number,
                                "drawer_name": room.players[
                                    room.current_drawer
                                ].name,
                            },
                        },
                    )

            logger.info(f"房间 {room_id} 游戏开始，词语: {word}")
        except FileNotFoundError:
            logger.error("词库文件 data/words.txt 不存在")
        except Exception as e:
            logger.error(f"开始游戏失败: {e}")

    def _remove_player(self, player_id: str):
        """
        移除玩家

        Args:
            player_id: 玩家ID
        """
        with self.lock:
            player = self.players.get(player_id)
            if player:
                room_id = player.room_id
                if room_id and room_id in self.rooms:
                    room = self.rooms[room_id]
                    room.remove_player(player_id)

                    # 广播玩家离开消息
                    self._broadcast_to_room(
                        room_id,
                        {
                            "type": "player_left",
                            "data": {"player_id": player_id, "player_name": player.name},
                        },
                    )

                del self.players[player_id]
                logger.info(f"玩家 {player.name} 已移除")

    def _send_message(self, client_socket: socket.socket, message: dict):
        """
        发送消息给客户端

        Args:
            client_socket: 客户端套接字
            message: 消息字典
        """
        try:
            data = json.dumps(message).encode("utf-8")
            client_socket.sendall(data)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")

    def _broadcast_to_room(
        self, room_id: str, message: dict, exclude_player: Optional[str] = None
    ):
        """
        广播消息到房间内所有玩家

        Args:
            room_id: 房间ID
            message: 消息字典
            exclude_player: 排除的玩家ID
        """
        room = self.rooms.get(room_id)
        if not room:
            return

        for player_id, player in room.players.items():
            if player_id != exclude_player and player.conn:
                self._send_message(player.conn, message)

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.socket:
            self.socket.close()
        logger.info("服务器已停止")
