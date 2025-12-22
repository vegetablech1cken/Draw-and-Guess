"""
文本输入框组件

提供文本输入功能。
"""

import pygame
from typing import Optional, Tuple

from src.shared.constants import WHITE, BLACK, GRAY


class InputBox:
    """文本输入框类"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        font_size: int = 24,
        placeholder: str = "",
    ):
        """
        初始化输入框

        Args:
            x: X坐标
            y: Y坐标
            width: 宽度
            height: 高度
            font_size: 字体大小
            placeholder: 占位符文本
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.color_inactive = GRAY
        self.color_active = BLACK
        self.color = self.color_inactive
        self.active = False
        self.text = ""
        self.placeholder = placeholder
        self.font = pygame.font.Font(None, font_size)
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event: pygame.event.Event) -> Optional[str]:
        """
        处理事件

        Args:
            event: Pygame事件

        Returns:
            如果按下回车，返回输入的文本，否则返回None
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            # 点击输入框激活/取消激活
            if self.rect.collidepoint(event.pos):
                self.active = True
                self.color = self.color_active
            else:
                self.active = False
                self.color = self.color_inactive

        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_RETURN:
                # 按回车提交
                text = self.text
                self.text = ""
                return text
            elif event.key == pygame.K_BACKSPACE:
                # 删除字符
                self.text = self.text[:-1]
            else:
                # 添加字符
                self.text += event.unicode

        return None

    def draw(self, screen: pygame.Surface):
        """
        绘制输入框

        Args:
            screen: 目标屏幕表面
        """
        # 绘制背景
        pygame.draw.rect(screen, WHITE, self.rect)
        # 绘制边框
        pygame.draw.rect(screen, self.color, self.rect, 2)

        # 绘制文本
        if self.text:
            text_surface = self.font.render(self.text, True, BLACK)
        elif not self.active:
            # 显示占位符
            text_surface = self.font.render(self.placeholder, True, GRAY)
        else:
            text_surface = None

        if text_surface:
            screen.blit(
                text_surface,
                (self.rect.x + 5, self.rect.y + (self.rect.height - text_surface.get_height()) // 2),
            )

        # 绘制光标
        if self.active:
            self.cursor_timer += 1
            if self.cursor_timer >= 30:
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0

            if self.cursor_visible:
                cursor_x = self.rect.x + 5
                if self.text:
                    text_width = self.font.size(self.text)[0]
                    cursor_x += text_width
                pygame.draw.line(
                    screen,
                    BLACK,
                    (cursor_x, self.rect.y + 5),
                    (cursor_x, self.rect.y + self.rect.height - 5),
                    2,
                )
