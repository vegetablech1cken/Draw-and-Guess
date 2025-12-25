import pygame
from typing import Tuple


class Canvas:
    """
    简易画布组件：支持绘制、擦除、清空、颜色与画笔大小切换。
    
    本组件用于绘图游戏的画布区域，支持：
    - 鼠标左键拖动绘制平滑曲线
    - 快速切换颜色与画笔大小
    - 擦除模式（用背景色覆盖）
    - 一键清空画布
    
    使用方式：
    - 在主循环中调用 `handle_event(event)` 处理鼠标事件
    - 每帧调用 `draw(screen)` 进行渲染
    - 通过 `set_color`, `set_brush_size`, `set_mode` 控制画笔
    """

    def __init__(self, rect: pygame.Rect, bg_color: Tuple[int, int, int] = (255, 255, 255)) -> None:
        """初始化画布组件
        
        Args:
            rect: 画布在屏幕上的矩形区域（决定位置与大小）
            bg_color: 背景颜色，默认白色 (255, 255, 255)
        """
        self.rect = rect
        self.bg_color = bg_color
        # 创建一个与画布相同大小的 Surface，用于存储绘制内容
        self.surface = pygame.Surface((rect.width, rect.height)).convert()
        self.surface.fill(self.bg_color)  # 初始化为背景色
        
        # 画笔属性
        self.brush_color: Tuple[int, int, int] = (0, 0, 0)  # 初始为黑色
        self.brush_size: int = 5  # 初始笔宽度
        self.mode: str = "draw"  # 模式：\"draw\"（绘制）或 \"erase\"（擦除）
        
        # 鼠标状态跟踪
        self._drawing: bool = False  # 是否正在绘制
        self._last_pos: Tuple[int, int] | None = None  # 上一次鼠标位置（用于绘制直线）

    def to_local(self, pos: Tuple[int, int]) -> Tuple[int, int]:
        """将屏幕坐标转换为画布本地坐标
        
        Args:
            pos: 屏幕坐标 (x, y)
        
        Returns:
            画布内的本地坐标
        """
        return pos[0] - self.rect.x, pos[1] - self.rect.y

    def set_color(self, color: Tuple[int, int, int]) -> None:
        """设置画笔颜色
        
        Args:
            color: RGB 颜色值，例 (255, 0, 0) 表示红色
        """
        self.brush_color = color

    def set_brush_size(self, size: int) -> None:
        """设置画笔大小
        
        Args:
            size: 笔的半径大小（像素），自动确保至少为 1
        """
        self.brush_size = max(1, int(size))

    def set_mode(self, mode: str) -> None:
        """切换绘制模式
        
        Args:
            mode: \"draw\"（绘制）或 \"erase\"（擦除）
        """
        if mode in ("draw", "erase"):
            self.mode = mode

    def clear(self) -> None:
        """清空画布，恢复到初始背景色"""
        self.surface.fill(self.bg_color)

    def _paint_at(self, local_pos: Tuple[int, int]) -> None:
        """在指定位置绘制一个点（圆形笔触）
        
        内部方法：在擦除模式下使用背景色，在绘制模式下使用画笔色
        
        Args:
            local_pos: 画布本地坐标
        """
        color = self.bg_color if self.mode == "erase" else self.brush_color
        pygame.draw.circle(self.surface, color, local_pos, self.brush_size)

    def _line_to(self, local_from: Tuple[int, int], local_to: Tuple[int, int]) -> None:
        """从一点绘制直线到另一点（平滑鼠标拖动）
        
        内部方法：连接两个位置形成元滑的线条
        
        Args:
            local_from: 起点坐标
            local_to: 终点坐标
        """
        color = self.bg_color if self.mode == "erase" else self.brush_color
        pygame.draw.line(self.surface, color, local_from, local_to, self.brush_size * 2)

    def handle_event(self, event: pygame.event.Event) -> None:
        """处理鼠标事件（绘制的核心交互）
        
        - 左键按下：开始绘制，记录起点
        - 鼠标移动：如正在绘制则绘制直线连接各点
        - 左键释放：停止绘制
        
        Args:
            event: pygame 事件对象
        """
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            # 左键按下：检查点击是否在画布区域内
            if self.rect.collidepoint(event.pos):
                self._drawing = True
                lp = self.to_local(event.pos)  # 转换为本地坐标
                self._last_pos = lp
                self._paint_at(lp)  # 绘制起始点
        elif event.type == pygame.MOUSEMOTION:
            # 鼠标移动：如果正在绘制，则绘制直线连接各点
            if self._drawing:
                lp = self.to_local(event.pos)
                if self._last_pos is not None:
                    self._line_to(self._last_pos, lp)  # 绘制平滑线条
                else:
                    self._paint_at(lp)
                self._last_pos = lp
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            # 左键释放：停止绘制
            self._drawing = False
            self._last_pos = None

    def draw(self, screen: pygame.Surface) -> None:
        """每帧渲染画布到屏幕
        
        - 将内部 surface 复制到屏幕
        - 绘制专业风格的边框和阴影效果
        
        Args:
            screen: pygame 屏幕 Surface 对象
        """
        # 绘制阴影（深灰色，偏移 3px）
        shadow_rect = pygame.Rect(self.rect.x + 3, self.rect.y + 3, self.rect.width, self.rect.height)
        pygame.draw.rect(screen, (180, 180, 180), shadow_rect)
        
        # 绘制画布主体
        screen.blit(self.surface, self.rect.topleft)
        
        # 绘制专业风格的边框（蓝灰色，3像素宽）
        pygame.draw.rect(screen, (150, 170, 200), self.rect, 3)
