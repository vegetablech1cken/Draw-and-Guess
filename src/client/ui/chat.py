import pygame
from typing import List, Tuple, Optional


class ChatPanel:
    """
    简易聊天面板：显示最近的聊天消息。

    功能特性：
    - 存储并显示玩家输入的聊天内容
    - 自动滚动显示最新的消息（最多 200 条历史记录）
    - 根据面板高度自动调整显示的行数
    """

    def __init__(self, rect: pygame.Rect, font_size: int = 18, font_name: Optional[str] = None) -> None:
        """初始化聊天面板

        Args:
            rect: 聊天面板的矩形区域
            font_size: 字体大小
            font_name: 字体名称（如 "Microsoft YaHei"），默认系统字体
        """
        self.rect = rect

        # 尝试加载指定字体，失败则使用默认字体
        try:
            self.font = pygame.font.SysFont(font_name or None, font_size)
        except Exception:
            self.font = pygame.font.SysFont(None, font_size)

        # 消息列表：每个消息是 (用户名, 文本) 元组
        self.messages: List[Tuple[str, str]] = []  # (user, text)
        # 根据面板高度自动计算最多显示的行数（每行高度 + 4 像素间距）
        self.max_lines = max(3, rect.height // (self.font.get_height() + 4))

        # 颜色定义
        self.bg_color = (250, 250, 250)      # 浅灰色背景
        self.border_color = (200, 200, 200)  # 灰色边框

    def add_message(self, user: str, text: str) -> None:
        """添加一条新消息到聊天面板

        Args:
            user: 发送者名字（如 "你", "对方", "系统"）
            text: 消息内容
        """
        self.messages.append((user, text))  # 添加消息到列表末尾
        # 限制历史消息数量不超过 200 条（防止内存溢出）
        if len(self.messages) > 200:
            self.messages = self.messages[-200:]  # 保留最新的 200 条

    def draw(self, screen: pygame.Surface) -> None:
        """每帧渲染聊天面板到屏幕

        - 绘制圆角背景与阴影
        - 绘制边框
        - 显示最近的 max_lines 条消息（带行内气泡效果）

        Args:
            screen: pygame 屏幕 Surface 对象
        """
        # 阴影
        shadow = pygame.Rect(self.rect.x + 3, self.rect.y + 3, self.rect.width, self.rect.height)
        pygame.draw.rect(screen, (210, 210, 210), shadow, border_radius=8)
        # 背景圆角
        pygame.draw.rect(screen, self.bg_color, self.rect, border_radius=8)
        # 边框
        pygame.draw.rect(screen, self.border_color, self.rect, 2, border_radius=8)

        # 计算显示范围：只显示最后 max_lines 条消息
        y = self.rect.y + 8
        start = max(0, len(self.messages) - self.max_lines)

        bubble_pad_x = 10
        bubble_pad_y = 4
        for i, (user, text) in enumerate(self.messages[start:]):
            line = f"{user}: {text}"
            surf = self.font.render(line, True, (40, 40, 40))
            # 气泡背景（交替浅色）
            bubble_rect = pygame.Rect(self.rect.x + 6, y - 2, self.rect.width - 12, surf.get_height() + bubble_pad_y * 2)
            bubble_color = (245, 248, 255) if i % 2 == 0 else (252, 252, 252)
            pygame.draw.rect(screen, bubble_color, bubble_rect, border_radius=6)
            pygame.draw.rect(screen, (230, 230, 230), bubble_rect, 1, border_radius=6)
            # 文本
            screen.blit(surf, (self.rect.x + bubble_pad_x, y))
            y += surf.get_height() + bubble_pad_y * 2
