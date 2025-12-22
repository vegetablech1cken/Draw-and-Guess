"""
客户端网络连接

处理与服务器的通信。
"""

import socket
import threading
import logging
import json
from typing import Optional, Callable, Dict

from src.shared.constants import BUFFER_SIZE

logger = logging.getLogger(__name__)


class NetworkClient:
    """网络客户端类"""

    def __init__(self, host: str, port: int):
        """
        初始化客户端

        Args:
            host: 服务器地址
            port: 服务器端口
        """
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.player_id: Optional[str] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.message_handlers: Dict[str, Callable] = {}

    def connect(self, player_name: str) -> bool:
        """
        连接到服务器

        Args:
            player_name: 玩家名称

        Returns:
            是否成功连接
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True

            # 启动接收消息的线程
            self.receive_thread = threading.Thread(target=self._receive_messages)
            self.receive_thread.daemon = True
            self.receive_thread.start()

            # 发送连接消息
            self.send_message({"type": "connect", "data": {"name": player_name}})

            logger.info(f"已连接到服务器 {self.host}:{self.port}")
            return True

        except Exception as e:
            logger.error(f"连接服务器失败: {e}")
            self.connected = False
            return False

    def disconnect(self):
        """断开连接"""
        self.connected = False
        if self.socket:
            try:
                self.socket.close()
            except Exception:
                pass
        logger.info("已断开与服务器的连接")

    def _receive_messages(self):
        """接收服务器消息"""
        while self.connected:
            try:
                data = self.socket.recv(BUFFER_SIZE)
                if not data:
                    break

                # 解析消息
                try:
                    message = json.loads(data.decode("utf-8"))
                    self._handle_message(message)
                except json.JSONDecodeError:
                    logger.error(f"无效的JSON数据: {data}")
                except Exception as e:
                    logger.error(f"处理消息错误: {e}")

            except Exception as e:
                if self.connected:
                    logger.error(f"接收消息错误: {e}")
                break

        self.connected = False

    def _handle_message(self, message: dict):
        """
        处理服务器消息

        Args:
            message: 消息字典
        """
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "connected":
            # 处理连接成功消息
            self.player_id = data.get("player_id")
            logger.info(f"连接成功，玩家ID: {self.player_id}")

        # 调用注册的消息处理器
        if msg_type in self.message_handlers:
            try:
                self.message_handlers[msg_type](data)
            except Exception as e:
                logger.error(f"消息处理器错误 ({msg_type}): {e}")

    def register_handler(self, msg_type: str, handler: Callable):
        """
        注册消息处理器

        Args:
            msg_type: 消息类型
            handler: 处理函数
        """
        self.message_handlers[msg_type] = handler

    def send_message(self, message: dict):
        """
        发送消息到服务器

        Args:
            message: 消息字典
        """
        if not self.connected or not self.socket:
            logger.warning("未连接到服务器")
            return

        try:
            data = json.dumps(message).encode("utf-8")
            self.socket.sendall(data)
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            self.connected = False

    def send_draw(self, x: int, y: int, prev_x: int, prev_y: int, color: tuple, size: int):
        """
        发送绘图数据

        Args:
            x: 当前X坐标
            y: 当前Y坐标
            prev_x: 上一个X坐标
            prev_y: 上一个Y坐标
            color: 颜色RGB
            size: 画笔大小
        """
        self.send_message(
            {
                "type": "draw",
                "data": {
                    "x": x,
                    "y": y,
                    "prev_x": prev_x,
                    "prev_y": prev_y,
                    "color": list(color),
                    "size": size,
                },
            }
        )

    def send_guess(self, guess: str):
        """
        发送猜测

        Args:
            guess: 猜测的词语
        """
        self.send_message({"type": "guess", "data": {"guess": guess}})

    def send_chat(self, message: str):
        """
        发送聊天消息

        Args:
            message: 消息内容
        """
        self.send_message({"type": "chat", "data": {"message": message}})

    def start_game(self):
        """请求开始游戏"""
        self.send_message({"type": "start_game", "data": {}})
