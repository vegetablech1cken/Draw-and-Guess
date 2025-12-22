"""
绘图画布组件

提供绘图功能的画布。
"""

import pygame
from typing import Optional, Tuple, List

from src.shared.constants import WHITE, BLACK, DEFAULT_BRUSH_SIZE


class Canvas:
    """绘图画布类"""

    def __init__(self, x: int, y: int, width: int, height: int):
        """
        初始化画布

        Args:
            x: 画布X坐标
            y: 画布Y坐标
            width: 画布宽度
            height: 画布高度
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.surface = pygame.Surface((width, height))
        self.surface.fill(WHITE)
        self.enabled = False
        self.current_color = BLACK
        self.brush_size = DEFAULT_BRUSH_SIZE
        self.drawing = False
        self.last_pos: Optional[Tuple[int, int]] = None

    def enable(self, enabled: bool = True):
        """
        启用/禁用画布

        Args:
            enabled: 是否启用
        """
        self.enabled = enabled

    def clear(self):
        """清空画布"""
        self.surface.fill(WHITE)

    def set_color(self, color: Tuple[int, int, int]):
        """
        设置画笔颜色

        Args:
            color: RGB颜色元组
        """
        self.current_color = color

    def set_brush_size(self, size: int):
        """
        设置画笔大小

        Args:
            size: 画笔大小
        """
        self.brush_size = max(1, min(50, size))

    def start_drawing(self, pos: Tuple[int, int]):
        """
        开始绘图

        Args:
            pos: 鼠标位置
        """
        if not self.enabled:
            return

        # 转换为画布坐标
        local_pos = (pos[0] - self.rect.x, pos[1] - self.rect.y)
        if 0 <= local_pos[0] < self.rect.width and 0 <= local_pos[1] < self.rect.height:
            self.drawing = True
            self.last_pos = local_pos

    def draw_line(
        self, pos: Tuple[int, int]
    ) -> Optional[Tuple[int, int, int, int, Tuple[int, int, int], int]]:
        """
        绘制线条

        Args:
            pos: 鼠标位置

        Returns:
            绘图数据元组 (x1, y1, x2, y2, color, size) 或 None
        """
        if not self.drawing or not self.enabled:
            return None

        # 转换为画布坐标
        local_pos = (pos[0] - self.rect.x, pos[1] - self.rect.y)
        if 0 <= local_pos[0] < self.rect.width and 0 <= local_pos[1] < self.rect.height:
            if self.last_pos:
                # 绘制线条
                pygame.draw.line(
                    self.surface,
                    self.current_color,
                    self.last_pos,
                    local_pos,
                    self.brush_size,
                )

                # 保存绘图数据用于网络同步
                draw_data = (
                    self.last_pos[0],
                    self.last_pos[1],
                    local_pos[0],
                    local_pos[1],
                    self.current_color,
                    self.brush_size,
                )

                self.last_pos = local_pos
                return draw_data

            self.last_pos = local_pos

        return None

    def stop_drawing(self):
        """停止绘图"""
        self.drawing = False
        self.last_pos = None

    def draw_from_network(
        self, prev_x: int, prev_y: int, x: int, y: int, color: List[int], size: int
    ):
        """
        根据网络数据绘制

        Args:
            prev_x: 起始X坐标
            prev_y: 起始Y坐标
            x: 目标X坐标
            y: 目标Y坐标
            color: 颜色列表
            size: 画笔大小
        """
        pygame.draw.line(
            self.surface,
            tuple(color),
            (prev_x, prev_y),
            (x, y),
            size,
        )

    def draw(self, screen: pygame.Surface):
        """
        绘制画布到屏幕

        Args:
            screen: 目标屏幕表面
        """
        # 绘制画布背景（边框）
        pygame.draw.rect(screen, BLACK, self.rect, 2)
        # 绘制画布内容
        screen.blit(self.surface, self.rect)

    def is_point_inside(self, pos: Tuple[int, int]) -> bool:
        """
        检查点是否在画布内

        Args:
            pos: 位置坐标

        Returns:
            是否在画布内
        """
        return self.rect.collidepoint(pos)
