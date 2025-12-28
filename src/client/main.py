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
import json

from src.shared.constants import WINDOW_HEIGHT, WINDOW_TITLE, WINDOW_WIDTH
from src.client.ui.button import Button
from src.client.ui.buttons_config import BUTTONS_CONFIG
from src.client.ui.canvas import Canvas
from src.client.ui.toolbar import Toolbar
from src.client.ui.text_input import TextInput
from src.client.ui.chat import ChatPanel


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
SETTINGS_PATH = Path(__file__).parent.parent.parent / "data" / "settings.json"

# Logo animation parameters
LOGO_BREATH_AMPLITUDE = 0.06  # 6% size variation
LOGO_BREATH_FREQ = 0.2  # Hz
LOGO_SWING_AMP = 3.0  # degrees
LOGO_SWING_FREQ = 0.1  # Hz

# Button entrance animation parameters
BUTTON_SLIDE_DURATION = 1.0  # seconds
BUTTON_STAGGER = 0.2  # seconds between staggered starts

# App state
APP_STATE: Dict[str, Any] = {
    "screen": "menu",  # menu | play | settings
    "ui": None,
    "settings": {
        "player_name": "玩家",
        "difficulty": "普通",  # 简单 | 普通 | 困难
        "volume": 80,
        "theme": "light",  # light | dark
        # 网络设置（局域网）
        "server_host": "127.0.0.1",
        "server_port": 5555,
        "room": "lobby",
    },
}


def load_settings() -> None:
    """从 JSON 文件加载设置（如果存在）。"""
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in ("player_name", "difficulty", "volume", "theme", "server_host", "server_port", "room"):
                    if k in data:
                        APP_STATE["settings"][k] = data[k]
    except Exception as exc:
        logger.warning("加载设置失败: %s", exc)


def save_settings() -> None:
    """将当前设置保存到 JSON 文件。"""
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(APP_STATE["settings"], f, ensure_ascii=False, indent=2)
    except Exception as exc:
        logger.warning("保存设置失败: %s", exc)



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
    APP_STATE["screen"] = "play"
    APP_STATE["ui"] = None  # 重置 UI，强制重新构建


def on_settings() -> None:
    logger.info("Settings pressed")
    APP_STATE["screen"] = "settings"


def on_quit() -> None:
    logger.info("Quit pressed")
    pygame.quit()
    sys.exit(0)


CALLBACKS: Dict[str, Callable[..., Any]] = {
    "on_start": on_start,
    "on_settings": on_settings,
    "on_quit": on_quit,
}


def build_play_ui(screen_size: tuple) -> Dict[str, Any]:
    """根据屏幕尺寸构建游戏界面组件。"""
    sw, sh = screen_size
    pad = 16
    sidebar_w = 260
    chat_h = 140
    input_h = 40
    topbar_h = 44

    canvas_rect = pygame.Rect(
        pad,
        pad + topbar_h,
        sw - sidebar_w - pad * 3,
        sh - chat_h - input_h - pad * 4 - topbar_h,
    )
    toolbar_rect = pygame.Rect(canvas_rect.right + pad, pad + topbar_h, sidebar_w, canvas_rect.height)
    chat_rect = pygame.Rect(pad, canvas_rect.bottom + pad, sw - pad * 2, chat_h)
    send_w = 90
    input_rect = pygame.Rect(pad, chat_rect.bottom + pad, sw - pad * 3 - send_w, input_h)

    # 组件
    canvas = Canvas(canvas_rect)

    # 颜色与画笔大小来自常量
    from src.shared.constants import BRUSH_COLORS, BRUSH_SIZES

    toolbar = Toolbar(toolbar_rect, colors=BRUSH_COLORS, sizes=BRUSH_SIZES, font_name="Microsoft YaHei")
    chat = ChatPanel(chat_rect, font_size=18, font_name="Microsoft YaHei")
    text_input = TextInput(input_rect, font_name="Microsoft YaHei", font_size=22, placeholder="输入猜词或聊天... Enter发送 / Shift+Enter换行")
    # 发送按钮
    send_btn = Button(
        x=input_rect.right + pad,
        y=input_rect.y,
        width=send_w,
        height=input_h,
        text="发送",
        bg_color=(60, 140, 250),
        fg_color=(255, 255, 255),
        font_size=20,
        font_name="Microsoft YaHei",
    )

    # 回调绑定
    toolbar.on_color = canvas.set_color
    toolbar.on_brush = canvas.set_brush_size
    toolbar.on_mode = canvas.set_mode
    toolbar.on_clear = canvas.clear

    # 初始化工具栏选中状态为画布当前值
    try:
        toolbar.set_selected_color(canvas.brush_color)
        toolbar.set_selected_size(canvas.brush_size)
    except Exception:
        pass

    # 网络：连接并加入房间
    from src.client.network.chat_client import ChatClient
    net = ChatClient(APP_STATE["settings"].get("server_host", "127.0.0.1"), int(APP_STATE["settings"].get("server_port", 5555)))
    player_name = APP_STATE["settings"].get("player_name", "玩家")
    room_id = APP_STATE["settings"].get("room", "lobby")
    connected = net.connect_and_join(room_id, player_name)
    if connected:
        def _on_chat(user: str, text: str) -> None:
            chat.add_message(user or "", text or "")
        net.on_chat = _on_chat
    else:
        chat.add_message("系统", "未连接到服务器，消息仅本地显示")

    def _on_submit(msg: str) -> None:
        safe = msg.replace("\n", " ")
        chat.add_message("你", safe)
        try:
            net.send_chat(safe)
        except Exception:
            pass

    text_input.on_submit = _on_submit

    # 返回菜单按钮（右上角）
    back_btn = Button(
        x=sw - 100 - pad,
        y=pad,
        width=100,
        height=32,
        text="返回菜单",
        bg_color=(100, 100, 100),
        fg_color=(255, 255, 255),
        font_size=20,
        font_name="Microsoft YaHei",
    )

    # HUD 状态（计时与词库）
    hud_state = {
        "topbar_h": topbar_h,
        "round_time_total": 60,
        "round_time_left": 60,
        "is_drawer": True,  # 单机预览默认作为画手
        "current_word": None,
        "last_tick": pygame.time.get_ticks(),
    }

    # 尝试加载单词
    try:
        words_path = Path(__file__).parent.parent.parent / "data" / "words.txt"
        if words_path.exists():
            import random

            with open(words_path, "r", encoding="utf-8") as f:
                words = [w.strip() for w in f if w.strip()]
            if words:
                hud_state["current_word"] = random.choice(words)
    except Exception as _:
        pass

    return {
        "canvas": canvas,
        "toolbar": toolbar,
        "chat": chat,
        "input": text_input,
        "send_btn": send_btn,
        "back_btn": back_btn,
        "hud": hud_state,
        "net": net,
    }


def build_settings_ui(screen_size: tuple) -> Dict[str, Any]:
    """构建设置界面组件。"""
    sw, sh = screen_size
    pad = 32
    
    # 返回菜单按钮
    back_btn = Button(
        x=pad,
        y=pad,
        width=120,
        height=40,
        text="← 返回菜单",
        bg_color=(100, 100, 100),
        fg_color=(255, 255, 255),
        font_size=20,
        font_name="Microsoft YaHei",
    )
    
    # 玩家名字输入框
    player_name_label = "玩家名字"
    player_name_input = TextInput(
        rect=pygame.Rect(pad + 200, pad, 300, 40),
        font_name="Microsoft YaHei",
        font_size=20,
        placeholder=APP_STATE["settings"]["player_name"],
    )
    # 初始填充为当前玩家名并绑定提交保存
    try:
        player_name_input.text = APP_STATE["settings"].get("player_name", "玩家")
    except Exception:
        pass
    def _update_player_name(name: str) -> None:
        APP_STATE["settings"]["player_name"] = name.strip() or APP_STATE["settings"].get("player_name", "玩家")
        save_settings()
    player_name_input.on_submit = _update_player_name
    
    # 服务器地址输入
    server_input = TextInput(
        rect=pygame.Rect(pad + 200, pad + 50, 300, 40),
        font_name="Microsoft YaHei",
        font_size=20,
        placeholder=APP_STATE["settings"].get("server_host", "127.0.0.1"),
    )
    try:
        server_input.text = APP_STATE["settings"].get("server_host", "127.0.0.1")
    except Exception:
        pass
    def _update_server_host(host: str) -> None:
        APP_STATE["settings"]["server_host"] = host.strip() or APP_STATE["settings"].get("server_host", "127.0.0.1")
        save_settings()
    server_input.on_submit = _update_server_host

    # 房间ID输入
    room_input = TextInput(
        rect=pygame.Rect(pad + 520, pad + 50, 300, 40),
        font_name="Microsoft YaHei",
        font_size=20,
        placeholder=APP_STATE["settings"].get("room", "lobby"),
    )
    try:
        room_input.text = APP_STATE["settings"].get("room", "lobby")
    except Exception:
        pass
    def _update_room(room: str) -> None:
        APP_STATE["settings"]["room"] = room.strip() or APP_STATE["settings"].get("room", "lobby")
        save_settings()
    room_input.on_submit = _update_room
    
    # 难度选择按钮
    easy_btn = Button(
        x=pad + 200,
        y=pad + 100,
        width=100,
        height=40,
        text="简单",
        bg_color=(76, 175, 80),
        fg_color=(255, 255, 255),
        font_size=20,
        font_name="Microsoft YaHei",
    )
    
    normal_btn = Button(
        x=pad + 310,
        y=pad + 100,
        width=100,
        height=40,
        text="普通",
        bg_color=(33, 150, 243),
        fg_color=(255, 255, 255),
        font_size=20,
        font_name="Microsoft YaHei",
    )
    
    hard_btn = Button(
        x=pad + 420,
        y=pad + 100,
        width=100,
        height=40,
        text="困难",
        bg_color=(244, 67, 54),
        fg_color=(255, 255, 255),
        font_size=20,
        font_name="Microsoft YaHei",
    )
    
    # 音量滑块范围
    volume_slider_rect = pygame.Rect(pad + 150, pad + 250, 350, 25)

    # 主题切换按钮
    light_btn = Button(
        x=pad + 150,
        y=pad + 320,
        width=120,
        height=36,
        text="浅色主题",
        bg_color=(180, 200, 220),
        fg_color=(255, 255, 255),
        font_size=18,
        font_name="Microsoft YaHei",
    )
    dark_btn = Button(
        x=pad + 280,
        y=pad + 320,
        width=120,
        height=36,
        text="深色主题",
        bg_color=(80, 90, 110),
        fg_color=(255, 255, 255),
        font_size=18,
        font_name="Microsoft YaHei",
    )
    
    # 快捷键说明
    shortcuts_info = {
        "1-9": "快速选择颜色",
        "[": "减小笔刷大小",
        "]": "增大笔刷大小",
        "E": "切换橡皮/画笔",
        "K": "清空画布",
        "N": "下一回合",
    }
    
    return {
        "back_btn": back_btn,
        "player_name_input": player_name_input,
        "server_input": server_input,
        "room_input": room_input,
        "easy_btn": easy_btn,
        "normal_btn": normal_btn,
        "hard_btn": hard_btn,
        "volume_slider_rect": volume_slider_rect,
        "light_btn": light_btn,
        "dark_btn": dark_btn,
        "shortcuts_info": shortcuts_info,
    }


def update_and_draw_hud(screen: pygame.Surface, ui: Dict[str, Any]) -> None:
    """更新倒计时并绘制顶部 HUD（计时、词、模式与画笔状态）。"""
    hud = ui.get("hud", {})
    if not hud:
        return
    now = pygame.time.get_ticks()
    dt_ms = now - hud.get("last_tick", now)
    hud["last_tick"] = now
    # 更新倒计时（每秒减少）
    hud["round_time_left"] = max(0, hud.get("round_time_left", 60) - dt_ms / 1000.0)

    # 背景条
    pad = 16
    top_h = int(hud.get("topbar_h", 44))
    rect = pygame.Rect(pad, pad, screen.get_width() - pad * 2 - 260 - pad, top_h)
    pygame.draw.rect(screen, (245, 245, 245), rect)
    pygame.draw.rect(screen, (200, 200, 200), rect, 2)

    # 内容：时间、词、模式、颜色与大小
    try:
        font = pygame.font.SysFont("Microsoft YaHei", 20)
    except Exception:
        font = pygame.font.SysFont(None, 20)

    # 时间
    t_left = int(hud.get("round_time_left", 60))
    time_txt = font.render(f"剩余时间: {t_left}s", True, (60, 60, 60))
    screen.blit(time_txt, (rect.x + 12, rect.y + (top_h - time_txt.get_height()) // 2))

    # 当前词（作为画手预览）
    word = hud.get("current_word") or "(未选择)"
    word_txt = font.render(f"当前词: {word}", True, (60, 60, 60))
    screen.blit(word_txt, (time_txt.get_rect(topleft=(rect.x + 12, rect.y)).right + 24, rect.y + (top_h - word_txt.get_height()) // 2))

    # 模式与画笔
    canvas: Canvas = ui["canvas"]
    mode_txt = font.render("模式: 橡皮" if canvas.mode == "erase" else "模式: 画笔", True, (60, 60, 60))
    screen.blit(mode_txt, (rect.right - 360, rect.y + (top_h - mode_txt.get_height()) // 2))

    # 颜色与大小展示
    color_rect = pygame.Rect(rect.right - 220, rect.y + 10, 24, top_h - 20)
    pygame.draw.rect(screen, canvas.brush_color, color_rect)
    pygame.draw.rect(screen, (180, 180, 180), color_rect, 1)
    size_txt = font.render(f"大小: {canvas.brush_size}", True, (60, 60, 60))
    screen.blit(size_txt, (color_rect.right + 12, rect.y + (top_h - size_txt.get_height()) // 2))


def main() -> None:
    """Start the Pygame client and run the main loop."""
    logger.info("%s", "=" * 50)
    logger.info("Draw & Guess 游戏客户端启动中...")
    logger.info("%s", "=" * 50)

    try:
        pygame.init()
        # 加载持久化设置
        load_settings()

        # Create a resizable window and load resources using actual screen size
        screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.RESIZABLE)
        pygame.display.set_caption(WINDOW_TITLE)

        logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
        APP_STATE["ui"] = None

        clock = pygame.time.Clock()
        running = True

        buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor)

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    screen = pygame.display.set_mode(event.size, pygame.RESIZABLE)
                    # 重建当前界面的布局
                    if APP_STATE["screen"] == "menu":
                        logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
                        buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor)
                    elif APP_STATE["screen"] == "play":
                        APP_STATE["ui"] = build_play_ui(screen.get_size())
                    elif APP_STATE["screen"] == "settings":
                        APP_STATE["ui"] = build_settings_ui(screen.get_size())
                else:
                    # 根据当前界面分发事件
                    if APP_STATE["screen"] == "menu":
                        if event.type == pygame.MOUSEMOTION:
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
                            # 进入 play 时构建 UI
                            if APP_STATE["screen"] == "play" and APP_STATE["ui"] is None:
                                APP_STATE["ui"] = build_play_ui(screen.get_size())
                            # 进入 settings 时构建 UI
                            elif APP_STATE["screen"] == "settings" and APP_STATE["ui"] is None:
                                APP_STATE["ui"] = build_settings_ui(screen.get_size())
                    elif APP_STATE["screen"] == "play":
                        ui = APP_STATE["ui"]
                        if ui is None:
                            ui = build_play_ui(screen.get_size())
                            APP_STATE["ui"] = ui
                        # 先处理鼠标事件到组件（工具栏、画布、输入框）
                        if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEMOTION:
                            ui["toolbar"].handle_event(event)
                            ui["canvas"].handle_event(event)
                            ui["input"].handle_event(event)
                            # 返回菜单按钮
                            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                                # 发送按钮点击：提交输入内容
                                if ui.get("send_btn") and ui["send_btn"].is_clicked(event.pos, event.button):
                                    txt = ui["input"].text.strip()
                                    if txt:
                                        cb = ui["input"].on_submit
                                        if cb:
                                            cb(txt)
                                        ui["input"].text = ""
                                if ui["back_btn"].is_clicked(event.pos, event.button):
                                    APP_STATE["screen"] = "menu"
                                    APP_STATE["ui"] = None  # 清除 UI
                                    logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
                                    buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor)
                        else:
                            # 其他事件（键盘等）
                            ui["input"].handle_event(event)
                            ui["canvas"].handle_event(event)
                        # 快捷键（输入框未激活时）
                        if event.type == pygame.KEYDOWN and not ui["input"].active:
                            from src.shared.constants import BRUSH_COLORS, BRUSH_SIZES
                            if event.key in (pygame.K_e,):
                                ui["canvas"].set_mode("erase" if ui["canvas"].mode == "draw" else "draw")
                            elif event.key in (pygame.K_k,):
                                ui["canvas"].clear()
                            elif event.key in (pygame.K_LEFTBRACKET,):  # [
                                # 降低画笔大小
                                cur = ui["canvas"].brush_size
                                sizes = sorted(BRUSH_SIZES)
                                smaller = max(s for s in sizes if s < cur) if any(s < cur for s in sizes) else cur
                                ui["canvas"].set_brush_size(smaller)
                                ui["toolbar"].set_selected_size(smaller)
                            elif event.key in (pygame.K_RIGHTBRACKET,):  # ]
                                cur = ui["canvas"].brush_size
                                sizes = sorted(BRUSH_SIZES)
                                larger = min(s for s in sizes if s > cur) if any(s > cur for s in sizes) else cur
                                ui["canvas"].set_brush_size(larger)
                                ui["toolbar"].set_selected_size(larger)
                            elif pygame.K_1 <= event.key <= pygame.K_9:
                                idx = event.key - pygame.K_1
                                if 0 <= idx < len(BRUSH_COLORS):
                                    chosen = BRUSH_COLORS[idx]
                                    ui["canvas"].set_color(chosen)
                                    ui["toolbar"].set_selected_color(chosen)
                            elif event.key in (pygame.K_n,):
                                # 下一回合：重置计时与换词
                                hud = ui.get("hud")
                                if hud:
                                    hud["round_time_left"] = hud.get("round_time_total", 60)
                                    try:
                                        words_path = Path(__file__).parent.parent.parent / "data" / "words.txt"
                                        if words_path.exists():
                                            import random
                                            with open(words_path, "r", encoding="utf-8") as f:
                                                words = [w.strip() for w in f if w.strip()]
                                            if words:
                                                hud["current_word"] = random.choice(words)
                                    except Exception:
                                        pass
                    elif APP_STATE["screen"] == "settings":
                        ui = APP_STATE["ui"]
                        if ui is None:
                            ui = build_settings_ui(screen.get_size())
                            APP_STATE["ui"] = ui
                        # 处理设置界面事件
                        ui["player_name_input"].handle_event(event)
                        ui["server_input"].handle_event(event)
                        ui["room_input"].handle_event(event)
                        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                            mouse_pos = event.pos
                            # 返回按钮
                            if ui["back_btn"].is_clicked(mouse_pos, event.button):
                                APP_STATE["screen"] = "menu"
                                APP_STATE["ui"] = None  # 清除 UI
                                logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
                                buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor)
                            # 难度选择
                            elif ui["easy_btn"].is_clicked(mouse_pos, event.button):
                                APP_STATE["settings"]["difficulty"] = "简单"
                                save_settings()
                            elif ui["normal_btn"].is_clicked(mouse_pos, event.button):
                                APP_STATE["settings"]["difficulty"] = "普通"
                                save_settings()
                            elif ui["hard_btn"].is_clicked(mouse_pos, event.button):
                                APP_STATE["settings"]["difficulty"] = "困难"
                                save_settings()
                            # 主题切换
                            elif ui["light_btn"].is_clicked(mouse_pos, event.button):
                                APP_STATE["settings"]["theme"] = "light"
                                save_settings()
                            elif ui["dark_btn"].is_clicked(mouse_pos, event.button):
                                APP_STATE["settings"]["theme"] = "dark"
                                save_settings()
                        # 音量滑块拖动
                        elif event.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[0]:
                            if ui["volume_slider_rect"].collidepoint(event.pos):
                                rel_x = event.pos[0] - ui["volume_slider_rect"].x
                                vol = max(0, min(100, int(rel_x / ui["volume_slider_rect"].width * 100)))
                                APP_STATE["settings"]["volume"] = vol
                                save_settings()

            screen.fill((245, 248, 255))  # 淡蓝白色背景，更柔和

            if APP_STATE["screen"] == "menu":
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
                            b.set_position(anim["start_x"], anim["y"])
                        else:
                            prog = min(1.0, elapsed / dur)
                            eased = 1 - pow(1 - prog, 3)
                            sx = anim["start_x"]
                            tx = anim["target_x"]
                            cur_x = int(sx + (tx - sx) * eased)
                            b.set_position(cur_x, anim["y"])
                            if prog >= 1.0:
                                anim["finished"] = True

                for b in buttons:
                    b.draw(screen)
            elif APP_STATE["screen"] == "play":
                ui = APP_STATE["ui"]
                if ui is None:
                    ui = build_play_ui(screen.get_size())
                    APP_STATE["ui"] = ui
                
                # 游戏背景色
                screen.fill((250, 250, 252))  # 淡灰白色
                
                # 渲染各组件
                update_and_draw_hud(screen, ui)
                ui["canvas"].draw(screen)
                ui["toolbar"].draw(screen)
                ui["chat"].draw(screen)
                ui["input"].draw(screen)
                ui["send_btn"].draw(screen)
                ui["back_btn"].draw(screen)
            elif APP_STATE["screen"] == "settings":
                ui = APP_STATE["ui"]
                if ui is None:
                    ui = build_settings_ui(screen.get_size())
                    APP_STATE["ui"] = ui
                
                # 根据主题绘制设置界面背景
                theme = APP_STATE["settings"].get("theme", "light")
                if theme == "dark":
                    bg_color = (28, 30, 35)
                    panel_bg = (40, 44, 52)
                    panel_border = (80, 90, 110)
                    title_color = (200, 220, 255)
                    label_color = (210, 210, 210)
                    value_color = (220, 220, 220)
                else:
                    bg_color = (240, 242, 250)
                    panel_bg = (255, 255, 255)
                    panel_border = (180, 200, 220)
                    title_color = (50, 80, 150)
                    label_color = (60, 60, 60)
                    value_color = (80, 80, 80)
                screen.fill(bg_color)
                
                # 绘制设置面板（白色背景，有边框）
                panel_rect = pygame.Rect(20, 20, screen.get_width() - 40, screen.get_height() - 40)
                pygame.draw.rect(screen, panel_bg, panel_rect)
                pygame.draw.rect(screen, panel_border, panel_rect, 3)
                
                try:
                    font_title = pygame.font.SysFont("Microsoft YaHei", 40)
                    font_label = pygame.font.SysFont("Microsoft YaHei", 24)
                    font_value = pygame.font.SysFont("Microsoft YaHei", 20)
                except Exception:
                    font_title = pygame.font.SysFont(None, 40)
                    font_label = pygame.font.SysFont(None, 24)
                    font_value = pygame.font.SysFont(None, 20)
                
                # 标题
                title = font_title.render("游戏设置", True, title_color)
                screen.blit(title, (50, 30))
                
                # 分隔线
                pygame.draw.line(screen, (200, 200, 200), (50, 90), (screen.get_width() - 50, 90), 2)
                
                # 玩家名字标签与输入框
                label = font_label.render("玩家名字:", True, label_color)
                screen.blit(label, (50, 110))
                ui["player_name_input"].draw(screen)

                # 服务器地址与房间ID
                label = font_label.render("服务器地址:", True, label_color)
                screen.blit(label, (50, 160))
                ui["server_input"].draw(screen)
                label = font_label.render("房间ID:", True, label_color)
                screen.blit(label, (520, 160))
                ui["room_input"].draw(screen)
                
                # 难度标签与按钮
                label = font_label.render("游戏难度:", True, label_color)
                screen.blit(label, (50, 180))
                ui["easy_btn"].draw(screen)
                ui["normal_btn"].draw(screen)
                ui["hard_btn"].draw(screen)
                
                # 当前难度显示
                difficulty = APP_STATE["settings"]["difficulty"]
                diff_colors = {"简单": (76, 175, 80), "普通": (33, 150, 243), "困难": (244, 67, 54)}
                diff_color = diff_colors.get(difficulty, (100, 100, 100))
                diff_label = font_value.render(f"当前难度: {difficulty}", True, diff_color)
                screen.blit(diff_label, (450, 195))
                
                # 音量标签与滑块
                label = font_label.render("音量:", True, label_color)
                screen.blit(label, (50, 270))
                
                # 音量滑块背景
                slider_rect = ui["volume_slider_rect"]
                pygame.draw.rect(screen, (220, 220, 220), slider_rect)
                pygame.draw.rect(screen, (150, 170, 220), slider_rect, 2)
                
                # 音量进度条
                vol = APP_STATE["settings"]["volume"]
                progress_rect = pygame.Rect(slider_rect.x, slider_rect.y, slider_rect.width * vol / 100, slider_rect.height)
                pygame.draw.rect(screen, (100, 150, 255), progress_rect)
                
                # 音量滑块游标
                slider_x = slider_rect.x + (vol / 100.0) * slider_rect.width
                pygame.draw.circle(screen, (50, 100, 200), (int(slider_x), int(slider_rect.centery)), 10)
                pygame.draw.circle(screen, (100, 150, 255), (int(slider_x), int(slider_rect.centery)), 8)
                
                # 音量百分比显示
                vol_label = font_value.render(f"音量: {vol}%", True, value_color)
                screen.blit(vol_label, (450, 280))

                # 主题切换标签与按钮
                theme_label = font_label.render("主题:", True, label_color)
                screen.blit(theme_label, (50, 325))
                ui["light_btn"].draw(screen)
                ui["dark_btn"].draw(screen)
                
                # 快捷键说明区域
                pygame.draw.line(screen, (200, 200, 200), (50, 320), (screen.get_width() - 50, 320), 2)
                
                shortcuts_title = font_label.render("快捷键说明", True, (50, 80, 150))
                screen.blit(shortcuts_title, (50, 380))
                
                shortcuts_info = ui.get("shortcuts_info", {})
                font_small = pygame.font.SysFont("Microsoft YaHei", 16)
                shortcut_y = 420
                col1_x = 50
                col2_x = screen.get_width() // 2
                col = 0
                
                for key, desc in shortcuts_info.items():
                    text = f"{key}: {desc}"
                    shortcut_text = font_small.render(text, True, (80, 80, 80))
                    x = col1_x if col % 2 == 0 else col2_x
                    y = shortcut_y + (col // 2) * 25
                    screen.blit(shortcut_text, (x, y))
                    col += 1
                
                # 返回按钮
                ui["back_btn"].draw(screen)

            pygame.display.flip()
            clock.tick(60)

    except Exception as exc:  # pragma: no cover - main runtime errors
        logger.error("客户端错误: %s", exc, exc_info=True)
    finally:
        pygame.quit()
        logger.info("客户端已关闭")


if __name__ == "__main__":
    main()
