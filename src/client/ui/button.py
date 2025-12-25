import pygame


class Button:
    """
    A class representing a button in the UI.

    Supports separate background (`bg_color`) and foreground/text (`fg_color`),
    and accepts an optional `font_name` (either a system font name or a path
    to a .ttf file) to improve rendering of non-ASCII characters.
    """

    def __init__(self, x, y, width, height, text, bg_color=(0, 0, 0), fg_color=(255, 255, 255), font_size=24, font_name=None):
        """
        Initialize the button with position, size, text, colors and font.
        - `bg_color`: background color (button rectangle)
        - `fg_color`: text color
        - `font_name`: optional; either a system font name or path to .ttf file
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.bg_color = bg_color
        self.fg_color = fg_color
        self.font_size = font_size

        # Try to load the requested font. If a path is provided and exists,
        # use pygame.font.Font. Otherwise attempt pygame.font.SysFont, and
        # finally fall back to the default font.
        try:
            if font_name:
                # If provided value looks like a path, try Font()
                import os

                if os.path.exists(font_name):
                    self.font = pygame.font.Font(font_name, font_size)
                else:
                    self.font = pygame.font.SysFont(font_name, font_size)
            else:
                # None -> use system default font
                self.font = pygame.font.SysFont(None, font_size)
        except Exception:
            self.font = pygame.font.Font(None, font_size)

        self.text_surface = self.font.render(text, True, self.fg_color)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

    def draw(self, screen):
        """Draw the button on the given screen with shadow and rounded corners."""
        # 绘制阴影
        shadow_offset = 4
        shadow_rect = pygame.Rect(self.rect.x + shadow_offset, self.rect.y + shadow_offset, self.rect.width, self.rect.height)
        pygame.draw.rect(screen, (150, 150, 150), shadow_rect, border_radius=8)
        
        # 绘制按钮主体（圆角矩形）
        pygame.draw.rect(screen, self.bg_color, self.rect, border_radius=8)
        pygame.draw.rect(screen, (100, 100, 100), self.rect, 2, border_radius=8)  # 边框
        
        # 绘制文本
        screen.blit(self.text_surface, self.text_rect)

    def is_hovered(self, mouse_pos):
        """Check if the button is hovered by the mouse."""
        return self.rect.collidepoint(mouse_pos)

    def is_clicked(self, mouse_pos, mouse_button):
        """Check if the button is clicked (left mouse button)."""
        return self.is_hovered(mouse_pos) and mouse_button == 1

    def update_text(self, new_text):
        """Update the button's text and re-render the surface."""
        self.text = new_text
        self.text_surface = self.font.render(new_text, True, self.fg_color)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

    def set_colors(self, bg_color=None, fg_color=None):
        """Update the button's background and/or foreground color."""
        if bg_color is not None:
            self.bg_color = bg_color
        if fg_color is not None:
            self.fg_color = fg_color
        self.text_surface = self.font.render(self.text, True, self.fg_color)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

    def set_position(self, x, y):
        """Update the button's position."""
        self.rect.topleft = (x, y)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

    def set_size(self, width, height):
        """Update the button's size."""
        self.rect.size = (width, height)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

    def set_font_size(self, font_size):
        """Update the button's font size and re-render the text."""
        self.font_size = font_size
        self.font = pygame.font.Font(None, font_size)
        self.text_surface = self.font.render(self.text, True, self.fg_color)
        self.text_rect = self.text_surface.get_rect(center=self.rect.center)

