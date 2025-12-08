"""
客户端主程序入口

启动游戏客户端，连接到服务器并显示游戏界面。
"""

import logging
import sys
from pathlib import Path
import math
from typing import Any, Callable, Dict, List, Optional

# 添加项目根目录到路径（保留以便直接运行脚本时能找到包）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pygame

from src.shared.constants import WINDOW_HEIGHT, WINDOW_TITLE, WINDOW_WIDTH
from src.client.ui.button import Button
from src.client.ui.buttons_config import BUTTONS_CONFIG


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("client.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# Module-level mappings to avoid adding dynamic attributes to Button
BUTTON_ORIG_BG: Dict[int, tuple] = {}
BUTTON_HOVER_BG: Dict[int, tuple] = {}
BUTTON_CALLBACKS: Dict[int, Callable[..., Any]] = {}
BUTTON_ANIMS: Dict[int, Dict[str, Any]] = {}


# Assets and logo path (adjust if you keep logo elsewhere)
ASSETS_DIR = Path(__file__).parent.parent.parent / "assets"
LOGO_PATH = ASSETS_DIR / "images" / "logo.png"

# Logo animation parameters
LOGO_BREATH_AMPLITUDE = 0.06  # 6% size variation
LOGO_BREATH_FREQ = 0.2  # Hz
LOGO_SWING_AMP = 3.0  # degrees
LOGO_SWING_FREQ = 0.1  # Hz

# Button entrance animation parameters
BUTTON_SLIDE_DURATION = 1.0  # seconds
BUTTON_STAGGER = 0.2  # seconds between staggered starts



def load_logo(path: Path, screen_size: tuple):
    """Load original logo surface and compute a base size + anchor.

    Returns (orig_surface or None, (base_w, base_h), anchor_pos)
    """
    try:
        orig = pygame.image.load(str(path)).convert_alpha()
    except Exception as exc:  # pragma: no cover - runtime resource handling
        logger.warning("Failed loading logo %s: %s", path, exc)
        return None, (0, 0), (0, 0)

    sw, sh = screen_size
    base_w = max(16, int(sw * 0.20))  # base logo width = 20% screen width
    orig_w, orig_h = orig.get_size()
    if orig_w <= 0:
        return None, (0, 0), (0, 0)

    base_h = max(1, int(base_w * orig_h / orig_w))
    # anchor at top-right with small margin from the screen edge
    anchor_pos = (sw - int(sw * 0.04), int(sh * 0.04))
    return orig, (base_w, base_h), anchor_pos


def anchor_to_pos(
    anchor: str, dx: int, dy: int, screen_w: int, screen_h: int, btn_w: int, btn_h: int
) -> tuple:
    """Convert anchor+offset to topleft (x,y).

    Supported anchors: 'topleft', 'topright', 'bottomleft', 'bottomright', 'center'
    """
    if anchor == "topleft":
        x, y = dx, dy
    elif anchor == "topright":
        x, y = screen_w - btn_w + dx, dy
    elif anchor == "bottomleft":
        x, y = dx, screen_h - btn_h + dy
    elif anchor == "bottomright":
        x, y = screen_w - btn_w + dx, screen_h - btn_h + dy
    elif anchor == "center":
        x, y = (screen_w - btn_w) // 2 + dx, (screen_h - btn_h) // 2 + dy
    else:
        x, y = dx, dy
    return int(x), int(y)


def resolve_position_and_size(cfg: Dict[str, Any], screen_size: tuple) -> tuple:
    """Resolve (x,y,w,h) from configuration.

    Supports percentage fields (`x_pct`, `y_pct`, `w_pct`, `h_pct`) and
    `anchor` with pixel offsets `dx`/`dy`.
    """
    sw, sh = screen_size

    # width / height by absolute px or percentage
    w = int(cfg.get("w", int(max(80, sw * cfg.get("w_pct", 0) if cfg.get("w_pct") else max(80, 0.2 * sw)))))
    h = int(cfg.get("h", int(sh * cfg.get("h_pct", 0) if cfg.get("h_pct") else 40)))

    # position resolution
    if "x_pct" in cfg:
        x = int(cfg["x_pct"] * sw)
        y = int(cfg.get("y", int(cfg.get("y_pct", 0) * sh if "y_pct" in cfg else 0)))
    elif "y_pct" in cfg and "x" in cfg:
        x = int(cfg.get("x", 0))
        y = int(cfg["y_pct"] * sh)
    elif "anchor" in cfg:
        dx = int(cfg.get("dx", 0))
        dy = int(cfg.get("dy", 0))
        x, y = anchor_to_pos(cfg["anchor"], dx, dy, sw, sh, w, h)
    else:
        x = int(cfg.get("x", 0))
        y = int(cfg.get("y", 0))

    return x, y, w, h


def create_buttons_from_config(
    config_list: List[Dict[str, Any]],
    callbacks_map: Dict[str, Callable[..., Any]],
    screen_size: tuple,
    logo_anchor: Optional[tuple] = None,
) -> List[Button]:
    """Create and return Button instances from configuration.

    This function also registers original/hover colors and callbacks in
    module-level dictionaries for runtime use.
    """
    buttons: List[Button] = []
    for idx, cfg in enumerate(config_list):
        x, y, w, h = resolve_position_and_size(cfg, screen_size)

        # start off-screen to the right
        start_x = screen_size[0] + 20 + idx * 8
        btn = Button(
            x=start_x,
            y=y,
            width=w,
            height=h,
            text=cfg.get("text", ""),
            bg_color=tuple(cfg.get("bg_color", (0, 0, 0))),
            fg_color=tuple(cfg.get("fg_color", (255, 255, 255))),
            font_size=cfg.get("font_size", 24),
            font_name=cfg.get("font_name", None),
        )

        orig = tuple(cfg.get("bg_color", (0, 0, 0)))
        hover = tuple(
            cfg.get(
                "hover_bg",
                (min(255, orig[0] + 40), min(255, orig[1] + 40), min(255, orig[2] + 40)),
            )
        )

        BUTTON_ORIG_BG[id(btn)] = orig
        BUTTON_HOVER_BG[id(btn)] = hover

        cb_name = cfg.get("callback")
        if cb_name and cb_name in callbacks_map:
            BUTTON_CALLBACKS[id(btn)] = callbacks_map[cb_name]

        # compute target_x; respect explicit position from cfg by default.
        # If config sets `align_to_logo: True` and a logo_anchor is provided,
        # align the button's right edge to the logo's right edge minus optional gap.
        if cfg.get("align_to_logo") and logo_anchor is not None:
            logo_right_x = int(logo_anchor[0])
            gap = int(cfg.get("align_gap", 0))
            target_x = logo_right_x - w - gap
        else:
            target_x = x

        # register animation state for slide-in from right
        BUTTON_ANIMS[id(btn)] = {
            "start_x": start_x,
            "target_x": target_x,
            "y": y,
            "duration": BUTTON_SLIDE_DURATION,
            "delay": idx * BUTTON_STAGGER,
            "finished": False,
        }

        buttons.append(btn)

    return buttons


def on_start() -> None:
    logger.info("Start pressed")


def on_settings() -> None:
    logger.info("Settings pressed")


def on_quit() -> None:
    logger.info("Quit pressed")
    pygame.quit()
    sys.exit(0)


CALLBACKS: Dict[str, Callable[..., Any]] = {
    "on_start": on_start,
    "on_settings": on_settings,
    "on_quit": on_quit,
}


def main() -> None:
    """Start the Pygame client and run the main loop."""
    logger.info("%s", "=" * 50)
    logger.info("Draw & Guess 游戏客户端启动中...")
    logger.info("%s", "=" * 50)

    try:
        pygame.init()

        # Create a resizable window and load resources using actual screen size
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(WINDOW_TITLE)

        logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())

        clock = pygame.time.Clock()
        running = True

        buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor)

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    # reload logo for new size, then recreate buttons aligned to logo
                    logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
                    buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor)
                elif event.type == pygame.MOUSEMOTION:
                    mouse_pos = event.pos
                    for b in buttons:
                        if b.is_hovered(mouse_pos):
                            hover_color = BUTTON_HOVER_BG.get(id(b), (70, 160, 255))
                            b.set_colors(bg_color=hover_color)
                        else:
                            orig_color = BUTTON_ORIG_BG.get(id(b))
                            if orig_color is not None:
                                b.set_colors(bg_color=orig_color)
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mouse_pos = event.pos
                    for b in buttons:
                        if b.is_clicked(mouse_pos, event.button):
                            cb = BUTTON_CALLBACKS.get(id(b))
                            if cb:
                                cb()

            screen.fill((255, 255, 255))

            if logo_orig is not None:
                # Animate: breathing (scale) + small swing (rotation)
                base_w, base_h = logo_base_size
                t = pygame.time.get_ticks() / 1000.0
                scale = 1.0 + LOGO_BREATH_AMPLITUDE * math.sin(2 * math.pi * LOGO_BREATH_FREQ * t)
                angle = LOGO_SWING_AMP * math.sin(2 * math.pi * LOGO_SWING_FREQ * t)

                sw_scaled = max(1, int(base_w * scale))
                sh_scaled = max(1, int(base_h * scale))
                try:
                    scaled = pygame.transform.smoothscale(logo_orig, (sw_scaled, sh_scaled))
                except Exception:
                    scaled = pygame.transform.scale(logo_orig, (sw_scaled, sh_scaled))

                rotated = pygame.transform.rotate(scaled, angle)
                rrect = rotated.get_rect()
                # place logo using top-right anchor
                rrect.topright = logo_anchor
                screen.blit(rotated, rrect)

            # Update button slide-in animations
            now = pygame.time.get_ticks() / 1000.0
            for b in buttons:
                anim = BUTTON_ANIMS.get(id(b))
                if anim and not anim.get("finished", False):
                    elapsed = now - anim.get("delay", 0)
                    dur = anim.get("duration", 0.5)
                    if elapsed <= 0:
                        # not started yet; ensure off-screen position
                        b.set_position(anim["start_x"], anim["y"])
                    else:
                        prog = min(1.0, elapsed / dur)
                        # ease out cubic
                        eased = 1 - pow(1 - prog, 3)
                        sx = anim["start_x"]
                        tx = anim["target_x"]
                        cur_x = int(sx + (tx - sx) * eased)
                        b.set_position(cur_x, anim["y"])
                        if prog >= 1.0:
                            anim["finished"] = True

            for b in buttons:
                b.draw(screen)

            pygame.display.flip()
            clock.tick(60)

    except Exception as exc:  # pragma: no cover - main runtime errors
        logger.error("客户端错误: %s", exc, exc_info=True)
    finally:
        pygame.quit()
        logger.info("客户端已关闭")


if __name__ == "__main__":
    main()
