"""
简化的游戏客户端

集成网络、UI和游戏逻辑的简单客户端。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pygame
import logging

from src.shared.constants import (
    WINDOW_WIDTH,
    WINDOW_HEIGHT,
    WINDOW_TITLE,
    FPS,
    DEFAULT_HOST,
    DEFAULT_PORT,
    WHITE,
    BLACK,
    BRUSH_COLORS,
)
from src.client.ui import Canvas, InputBox, Button
from src.client.game import NetworkClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class GameClient:
    """游戏客户端类"""

    def __init__(self):
        """初始化游戏客户端"""
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption(WINDOW_TITLE)
        self.clock = pygame.time.Clock()
        self.running = True
        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        # 游戏状态
        self.state = "connecting"  # connecting, lobby, playing
        self.player_name = ""
        self.is_drawer = False
        self.current_word = None
        self.players = []
        self.chat_messages = []

        # 网络客户端
        self.network = None

        # UI组件
        self.canvas = Canvas(50, 50, 700, 500)
        self.input_box = InputBox(50, 570, 500, 40, placeholder="输入你的猜测...")
        self.start_button = Button(
            570, 570, 180, 40, "开始游戏", bg_color=(50, 150, 50)
        )
        self.clear_button = Button(
            770, 50, 100, 40, "清空画布", bg_color=(150, 50, 50)
        )

        # 颜色选择器
        self.color_buttons = []
        for i, color in enumerate(BRUSH_COLORS[:6]):
            btn = Button(770 + (i % 2) * 55, 100 + (i // 2) * 55, 50, 50, "")
            btn.set_colors(bg_color=color)
            self.color_buttons.append((btn, color))

    def connect_to_server(self, player_name: str):
        """
        连接到服务器

        Args:
            player_name: 玩家名称
        """
        self.network = NetworkClient(DEFAULT_HOST, DEFAULT_PORT)

        # 注册消息处理器
        self.network.register_handler("connected", self.on_connected)
        self.network.register_handler("player_joined", self.on_player_joined)
        self.network.register_handler("player_left", self.on_player_left)
        self.network.register_handler("draw", self.on_draw)
        self.network.register_handler("game_started", self.on_game_started)
        self.network.register_handler("chat", self.on_chat)
        self.network.register_handler("guess_result", self.on_guess_result)
        self.network.register_handler("player_guessed", self.on_player_guessed)

        if self.network.connect(player_name):
            self.player_name = player_name
            self.state = "lobby"
            return True
        return False

    def on_connected(self, data: dict):
        """处理连接成功"""
        self.players = data.get("players", [])
        logger.info("连接成功")

    def on_player_joined(self, data: dict):
        """处理玩家加入"""
        player = data.get("player")
        if player:
            self.players.append(player)
            self.add_chat_message(f"系统: {player['name']} 加入了游戏")

    def on_player_left(self, data: dict):
        """处理玩家离开"""
        player_name = data.get("player_name")
        self.add_chat_message(f"系统: {player_name} 离开了游戏")

    def on_draw(self, data: dict):
        """处理绘图数据"""
        self.canvas.draw_from_network(
            data["x"], data["y"], data["prev_x"], data["prev_y"], data["color"], data["size"]
        )

    def on_game_started(self, data: dict):
        """处理游戏开始"""
        self.state = "playing"
        self.is_drawer = data.get("is_drawer", False)
        self.current_word = data.get("word")
        self.canvas.clear()
        self.canvas.enable(self.is_drawer)

        if self.is_drawer:
            self.add_chat_message(f"系统: 你是画家！词语是：{self.current_word}")
        else:
            drawer_name = data.get("drawer_name", "未知")
            self.add_chat_message(f"系统: {drawer_name} 正在画画，快来猜吧！")

    def on_chat(self, data: dict):
        """处理聊天消息"""
        player_name = data.get("player_name")
        message = data.get("message")
        self.add_chat_message(f"{player_name}: {message}")

    def on_guess_result(self, data: dict):
        """处理猜测结果"""
        if data.get("correct"):
            self.add_chat_message("系统: 恭喜你猜对了！")

    def on_player_guessed(self, data: dict):
        """处理其他玩家猜对"""
        player_name = data.get("player_name")
        self.add_chat_message(f"系统: {player_name} 猜对了！")

    def add_chat_message(self, message: str):
        """
        添加聊天消息

        Args:
            message: 消息内容
        """
        self.chat_messages.append(message)
        if len(self.chat_messages) > 10:
            self.chat_messages.pop(0)

    def handle_events(self):
        """处理事件"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False

            # 处理输入框事件
            text = self.input_box.handle_event(event)
            if text and self.network:
                if self.state == "playing" and not self.is_drawer:
                    self.network.send_guess(text)
                elif self.state == "lobby":
                    self.network.send_chat(text)

            # 处理鼠标事件
            if event.type == pygame.MOUSEBUTTONDOWN:
                mouse_pos = event.pos

                # 开始按钮
                if self.start_button.is_clicked(mouse_pos, event.button):
                    if self.state == "lobby" and self.network:
                        self.network.start_game()

                # 清空画布按钮
                if self.clear_button.is_clicked(mouse_pos, event.button):
                    if self.is_drawer:
                        self.canvas.clear()

                # 颜色选择
                for btn, color in self.color_buttons:
                    if btn.is_clicked(mouse_pos, event.button):
                        self.canvas.set_color(color)

                # 画布绘图
                if self.canvas.is_point_inside(mouse_pos):
                    self.canvas.start_drawing(mouse_pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                self.canvas.stop_drawing()

            elif event.type == pygame.MOUSEMOTION:
                if self.canvas.drawing:
                    draw_data = self.canvas.draw_line(event.pos)
                    if draw_data and self.network:
                        x1, y1, x2, y2, color, size = draw_data
                        self.network.send_draw(x2, y2, x1, y1, color, size)

    def draw(self):
        """绘制界面"""
        self.screen.fill(WHITE)

        # 绘制画布
        self.canvas.draw(self.screen)

        # 绘制输入框
        self.input_box.draw(self.screen)

        # 绘制按钮
        if self.state == "lobby":
            self.start_button.draw(self.screen)

        if self.is_drawer:
            self.clear_button.draw(self.screen)

            # 绘制颜色选择器
            for btn, _ in self.color_buttons:
                btn.draw(self.screen)

        # 绘制状态信息
        if self.state == "playing":
            if self.is_drawer:
                status_text = f"你是画家！词语：{self.current_word}"
            else:
                status_text = "猜猜画的是什么？"
            text_surface = self.font.render(status_text, True, BLACK)
            self.screen.blit(text_surface, (50, 10))
        elif self.state == "lobby":
            status_text = "等待开始游戏..."
            text_surface = self.font.render(status_text, True, BLACK)
            self.screen.blit(text_surface, (50, 10))

        # 绘制玩家列表
        y = 100
        for player in self.players:
            player_text = f"{player['name']}: {player['score']}分"
            text_surface = self.small_font.render(player_text, True, BLACK)
            self.screen.blit(text_surface, (880, y))
            y += 30

        # 绘制聊天消息
        y = 400
        for message in self.chat_messages[-5:]:  # 只显示最后5条
            text_surface = self.small_font.render(message, True, BLACK)
            self.screen.blit(text_surface, (880, y))
            y += 25

        pygame.display.flip()

    def run(self):
        """运行游戏循环"""
        # 连接到服务器
        player_name = input("请输入你的名字: ")
        if not self.connect_to_server(player_name):
            logger.error("无法连接到服务器")
            return

        # 主循环
        while self.running:
            self.handle_events()
            self.draw()
            self.clock.tick(FPS)

        # 清理
        if self.network:
            self.network.disconnect()
        pygame.quit()


if __name__ == "__main__":
    client = GameClient()
    client.run()
