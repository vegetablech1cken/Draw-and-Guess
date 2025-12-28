"""
客户端主程序入口

启动游戏客户端，连接到服务器并显示游戏界面。
"""

import logging
import sys
from pathlib import Path
import math
import uuid
from typing import Any, Callable, Dict, List, Optional

# 添加项目根目录到路径（保留以便直接运行脚本时能找到包）
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pygame
import json

# Ensure logger is configured early so modules can use it
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from src.shared.constants import WINDOW_HEIGHT, WINDOW_TITLE, WINDOW_WIDTH
from src.client.network import NetworkClient
from src.client.ui.button import Button
from src.client.ui.buttons_config import BUTTONS_CONFIG
from src.client.ui.canvas import Canvas
from src.client.ui.toolbar import Toolbar
from src.client.ui.text_input import TextInput
from src.client.ui.chat import ChatPanel
# Project root and resource paths
ROOT = Path(__file__).parent.parent.parent
SETTINGS_PATH = ROOT / "settings.json"
LOGO_PATH = ROOT / "assets" / "images" / "logo.png"

# Runtime maps used by create_buttons_from_config / event dispatch
BUTTON_ORIG_BG: Dict[int, tuple] = {}
BUTTON_HOVER_BG: Dict[int, tuple] = {}
BUTTON_CALLBACKS: Dict[int, Callable[..., Any]] = {}
BUTTON_ANIMS: Dict[int, Dict[str, Any]] = {}

# Logo animation defaults
LOGO_BREATH_AMPLITUDE = 0.06
LOGO_BREATH_FREQ = 0.5
LOGO_SWING_AMP = 4.0
LOGO_SWING_FREQ = 0.2
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
        "fullscreen": False,
        "player_id": None,
    },
    "net": None,
    # resize 防抖：在窗口调整结束后再重建 UI，减少频繁重建导致的卡顿
    "pending_resize_until": 0,
    "pending_resize_size": None,
}


def load_settings() -> None:
    """从 JSON 文件加载设置（如果存在）。"""
    try:
        if SETTINGS_PATH.exists():
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k in ("player_name", "difficulty", "volume", "theme", "fullscreen", "player_id"):
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


def ensure_player_identity() -> str:
    """确保存在稳定的 player_id（用于房间聊天标识）。"""
    pid = APP_STATE["settings"].get("player_id")
    if not pid:
        pid = str(uuid.uuid4())
        APP_STATE["settings"]["player_id"] = pid
        save_settings()
    return str(pid)


def get_network_client() -> NetworkClient:
    net = APP_STATE.get("net")
    if net is None:
        net = NetworkClient()
        APP_STATE["net"] = net
    return net


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
    screen_filter: Optional[str] = None,
) -> List[Button]:
    """Create and return Button instances from configuration.

    This function also registers original/hover colors and callbacks in
    module-level dictionaries for runtime use.
    """
    buttons: List[Button] = []
    for idx, cfg in enumerate(config_list):
        # 如果指定了 screen_filter，只创建属于该 screen 的按钮
        if screen_filter is not None and cfg.get("screen") != screen_filter:
            continue
        x, y, w, h = resolve_position_and_size(cfg, screen_size)

        # start off-screen to the right (for menu animation) or place directly for other screens
        start_x = screen_size[0] + 20 + idx * 8
        # compute target_x; respect explicit position from cfg by default.
        if cfg.get("align_to_logo") and logo_anchor is not None:
            logo_right_x = int(logo_anchor[0])
            gap = int(cfg.get("align_gap", 0))
            target_x = logo_right_x - w - gap
        else:
            target_x = x

        initial_x = start_x if screen_filter == "menu" else target_x

        orig = tuple(cfg.get("bg_color", (0, 0, 0)))
        hover = tuple(
            cfg.get(
                "hover_bg",
                (min(255, orig[0] + 40), min(255, orig[1] + 40), min(255, orig[2] + 40)),
            )
        )

        cb_name = cfg.get("callback")
        callback = None
        if cb_name and cb_name in callbacks_map:
            callback = callbacks_map[cb_name]

        btn = Button(
            x=initial_x,
            y=y,
            width=w,
            height=h,
            text=cfg.get("text", ""),
            bg_color=orig,
            fg_color=tuple(cfg.get("fg_color", (255, 255, 255))),
            hover_bg_color=hover,
            font_size=cfg.get("font_size", 24),
            font_name=cfg.get("font_name", None),
            on_click=callback,
        )
        # attach config id for callers to find specific buttons
        try:
            setattr(btn, "_cfg_id", cfg.get("id"))
        except Exception:
            pass

        BUTTON_ORIG_BG[id(btn)] = orig
        BUTTON_HOVER_BG[id(btn)] = hover

        if callback:
            BUTTON_CALLBACKS[id(btn)] = callback

        # register animation state for slide-in from right
        BUTTON_ANIMS[id(btn)] = {
            "start_x": start_x,
            "target_x": target_x,
            "y": y,
            "duration": BUTTON_SLIDE_DURATION,
            "delay": idx * BUTTON_STAGGER,
            "finished": False if screen_filter == "menu" else True,
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
    APP_STATE["ui"] = None


def on_quit() -> None:
    logger.info("Quit pressed")
    try:
        net = APP_STATE.get("net")
        if net:
            net.close()
    except Exception:
        pass
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
    # 发送按钮将在配置中创建并附加到 UI（位置依赖输入区域）

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

    def _on_submit(msg: str) -> None:
        safe = msg.replace("\n", " ")
        try:
            net = APP_STATE.get("net")
            if net and net.connected:
                net.send_chat(safe)
        except Exception:
            pass
        chat.add_message("你", safe)

    text_input.on_submit = _on_submit

    # 返回菜单按钮将在配置中创建并附加到 UI

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
        "hud": hud_state,
    }


def build_settings_ui(screen_size: tuple) -> Dict[str, Any]:
    """构建设置界面组件。"""
    sw, sh = screen_size
    # Responsive layout: use percentages so window/fullscreen changes keep UI readable
    left_x = int(sw * 0.08)
    control_x = int(sw * 0.22)
    row1_y = int(sh * 0.16)
    row2_y = int(sh * 0.36)

    input_w = max(220, min(520, int(sw * 0.36)))
    input_h = max(36, min(48, int(sh * 0.06)))

    slider_w = max(260, min(620, int(sw * 0.46)))
    slider_h = 25

    from src.client.ui.setting_components import make_slider_rect

    # 玩家名字输入框
    player_name_label = "玩家名字"
    player_name_input = TextInput(
        rect=pygame.Rect(control_x, row1_y, input_w, input_h),
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

    # 难度选择按钮
    # 难度设置已移除（改为使用默认/固定难度）

    # 音量滑块范围
    volume_slider_rect = make_slider_rect(control_x, row2_y, slider_w, slider_h)

    # 主题与全屏按钮由配置创建并在主循环中附加到 UI

    # 快捷键说明已移除（快捷键仍然存在于运行时，但不在设置界面展示）

    return {
        "player_name_input": player_name_input,
        # difficulty buttons removed
        "volume_slider_rect": volume_slider_rect,
        # theme/fullscreen buttons attached from config
        # shortcuts removed from UI dict
    }


def process_network_messages(ui: Optional[Dict[str, Any]]) -> None:
    """从网络事件队列消费消息并更新 UI。"""
    if not ui:
        return
    net = APP_STATE.get("net")
    if net is None:
        return

    self_id = APP_STATE.get("settings", {}).get("player_id")

    for msg in net.drain_events():
        data = msg.data or {}
        if msg.type == "chat":
            by_id = data.get("by") or data.get("by_id")
            name = data.get("by_name") or by_id or "玩家"
            if by_id and self_id and str(by_id) == str(self_id):
                # 已在本地显示，跳过重复
                continue
            label = "你" if by_id and self_id and str(by_id) == str(self_id) else name
            text = str(data.get("text") or "").replace("\n", " ")
            try:
                ui["chat"].add_message(label, text)
            except Exception:
                pass
        elif msg.type == "room_state":
            hud = ui.get("hud")
            if hud:
                try:
                    hud["round_time_left"] = data.get("time_left", hud.get("round_time_left", 60))
                except Exception:
                    pass


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
        
        # 初始化SDL文本输入支持（用于中文输入法）
        try:
            import os
            os.environ['SDL_IME_SHOW_UI'] = '1'
            # 重新初始化显示模块以应用环境变量
            pygame.display.quit()
            pygame.display.init()
        except Exception as e:
            logger.warning(f"初始化输入法支持失败: {e}")
        
        # 加载持久化设置并确保玩家标识
        load_settings()
        ensure_player_identity()

        # Create a window or fullscreen depending on saved settings
        flags = pygame.RESIZABLE
        if APP_STATE["settings"].get("fullscreen"):
            flags = pygame.FULLSCREEN
            screen = pygame.display.set_mode((0, 0), flags)
        else:
            screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), flags)
        pygame.display.set_caption(WINDOW_TITLE)

        logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
        APP_STATE["ui"] = None

        # 防抖延迟（毫秒），在连续调整窗口时等待短暂静默期再重建 UI
        RESIZE_DEBOUNCE_MS = 140

        def on_back():
            APP_STATE["screen"] = "menu"
            APP_STATE["ui"] = None
            nonlocal logo_orig, logo_base_size, logo_anchor, buttons
            logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
            buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor, screen_filter="menu")

        def on_light_theme():
            APP_STATE["settings"]["theme"] = "light"
            save_settings()

        def on_dark_theme():
            APP_STATE["settings"]["theme"] = "dark"
            save_settings()

        def on_fullscreen():
            nonlocal screen, logo_orig, logo_base_size, logo_anchor
            cur = bool(APP_STATE["settings"].get("fullscreen", False))
            new = not cur
            APP_STATE["settings"]["fullscreen"] = new
            save_settings()
            try:
                if new:
                    screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
                else:
                    screen = pygame.display.set_mode((1280, 720), pygame.RESIZABLE)
                logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, screen.get_size())
                APP_STATE["ui"] = None
            except Exception:
                pass

        def on_send():
            ui = APP_STATE["ui"]
            if ui and ui.get("input"):
                txt = ui["input"].text.strip()
                if txt:
                    cb = ui["input"].on_submit
                    if cb:
                        cb(txt)
                    ui["input"].text = ""

        CALLBACKS.update({
            "on_back": on_back,
            "on_light_theme": on_light_theme,
            "on_dark_theme": on_dark_theme,
            "on_fullscreen": on_fullscreen,
            "on_send": on_send,
        })

        clock = pygame.time.Clock()
        running = True

        buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor, screen_filter="menu")

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.VIDEORESIZE:
                    # 记录待处理的尺寸（不在每次事件中重建显示），等待防抖期结束后一次性调用 set_mode
                    APP_STATE["pending_resize_size"] = event.size
                    APP_STATE["pending_resize_until"] = pygame.time.get_ticks() + RESIZE_DEBOUNCE_MS
                else:
                    # 根据当前界面分发事件
                    if APP_STATE["screen"] == "menu":
                        for b in buttons:
                            b.handle_event(event)

                        # 进入 play/settings 时在渲染阶段统一构建 UI（含配置按钮）
                        if APP_STATE["screen"] in ("play", "settings"):
                            APP_STATE["ui"] = None
                    elif APP_STATE["screen"] == "play":
                        ui = APP_STATE["ui"]
                        if ui is None:
                            ui = build_play_ui(screen.get_size())
                            # create play-specific buttons from config and attach to ui
                            play_buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor, screen_filter="play")
                            for pb in play_buttons:
                                cid = getattr(pb, "_cfg_id", None)
                                if cid == "play_back":
                                    ui["back_btn"] = pb
                                elif cid == "play_send":
                                    ui["send_btn"] = pb
                            APP_STATE["ui"] = ui
                            # 确保网络连接并加入房间
                            player_id = ensure_player_identity()
                            net = get_network_client()
                            if not net.connected:
                                ok = net.connect(APP_STATE["settings"].get("player_name", "玩家"), player_id, room_id="default")
                                try:
                                    if ok:
                                        ui["chat"].add_message("系统", "已连接到服务器，已加入房间 default")
                                    else:
                                        ui["chat"].add_message("系统", "无法连接到服务器，聊天仅本地显示")
                                except Exception:
                                    pass

                        # 处理按钮事件
                        if ui.get("back_btn"):
                            ui["back_btn"].handle_event(event)
                        if ui.get("send_btn"):
                            ui["send_btn"].handle_event(event)

                        # 先处理鼠标事件到组件（工具栏、画布、输入框）
                        if event.type == pygame.MOUSEBUTTONDOWN or event.type == pygame.MOUSEMOTION:
                            ui["toolbar"].handle_event(event)
                            ui["canvas"].handle_event(event)
                            ui["input"].handle_event(event)
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
                            # attach settings buttons from config
                            settings_buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor, screen_filter="settings")
                            for sb in settings_buttons:
                                cid = getattr(sb, "_cfg_id", None)
                                if cid == "settings_back":
                                    ui["back_btn"] = sb
                                elif cid == "settings_light":
                                    ui["light_btn"] = sb
                                elif cid == "settings_dark":
                                    ui["dark_btn"] = sb
                                elif cid == "settings_fullscreen":
                                    ui["fullscreen_btn"] = sb
                            APP_STATE["ui"] = ui

                        # 处理设置界面事件
                        ui["player_name_input"].handle_event(event)

                        # 处理按钮事件
                        for btn_key in ["back_btn", "light_btn", "dark_btn", "fullscreen_btn"]:
                            if ui.get(btn_key):
                                ui[btn_key].handle_event(event)

                        # 音量滑块拖动
                        if event.type == pygame.MOUSEMOTION and pygame.mouse.get_pressed()[0]:
                            if ui["volume_slider_rect"].collidepoint(event.pos):
                                rel_x = event.pos[0] - ui["volume_slider_rect"].x
                                vol = max(0, min(100, int(rel_x / ui["volume_slider_rect"].width * 100)))
                                APP_STATE["settings"]["volume"] = vol
                                save_settings()

            if APP_STATE["screen"] == "play":
                process_network_messages(APP_STATE.get("ui"))

            # 如果存在待处理的 resize 且防抖期已过，则执行一次性的重建操作
            now_tick = pygame.time.get_ticks()
            pending_until = APP_STATE.get("pending_resize_until", 0)
            pending_size = APP_STATE.get("pending_resize_size")
            if pending_size and now_tick >= pending_until:
                # finalize resize handling once: set display mode once and rebuild UI
                try:
                    screen = pygame.display.set_mode(pending_size, pygame.RESIZABLE)
                except Exception:
                    pass
                try:
                    if APP_STATE["screen"] == "menu":
                        logo_orig, logo_base_size, logo_anchor = load_logo(LOGO_PATH, pending_size)
                        buttons = create_buttons_from_config(
                            BUTTONS_CONFIG, CALLBACKS, pending_size, logo_anchor, screen_filter="menu"
                        )
                    elif APP_STATE["screen"] in ("play", "settings"):
                        # 在渲染阶段重建 UI（play/settings 会在后续逻辑中重建）
                        APP_STATE["ui"] = None
                except Exception:
                    pass
                APP_STATE["pending_resize_size"] = None
                APP_STATE["pending_resize_until"] = 0

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
                    # create play-specific buttons from config and attach to ui
                    play_buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor, screen_filter="play")
                    for pb in play_buttons:
                        cid = getattr(pb, "_cfg_id", None)
                        if cid == "play_back":
                            ui["back_btn"] = pb
                        elif cid == "play_send":
                            ui["send_btn"] = pb
                    APP_STATE["ui"] = ui

                # 游戏背景色
                screen.fill((250, 250, 252))  # 淡灰白色

                # 渲染各组件
                update_and_draw_hud(screen, ui)
                ui["canvas"].draw(screen)
                ui["toolbar"].draw(screen)
                ui["chat"].draw(screen)
                ui["input"].draw(screen)
                if ui.get("send_btn"):
                    ui["send_btn"].draw(screen)
                if ui.get("back_btn"):
                    ui["back_btn"].draw(screen)
            elif APP_STATE["screen"] == "settings":
                ui = APP_STATE["ui"]
                if ui is None:
                    ui = build_settings_ui(screen.get_size())
                    # attach settings buttons from config
                    settings_buttons = create_buttons_from_config(BUTTONS_CONFIG, CALLBACKS, screen.get_size(), logo_anchor, screen_filter="settings")
                    for sb in settings_buttons:
                        cid = getattr(sb, "_cfg_id", None)
                        if cid == "settings_back":
                            ui["back_btn"] = sb
                        elif cid == "settings_light":
                            ui["light_btn"] = sb
                        elif cid == "settings_dark":
                            ui["dark_btn"] = sb
                        elif cid == "settings_fullscreen":
                            ui["fullscreen_btn"] = sb
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

                # 将返回按钮放置在面板的右上角，避免遮挡面板内部内容
                if ui.get("back_btn"):
                    try:
                        bb = ui["back_btn"]
                        margin = 20
                        new_x = panel_rect.right - bb.rect.width - margin
                        new_y = panel_rect.y + margin
                        bb.set_position(new_x, new_y)
                    except Exception:
                        pass

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
                pn_rect = ui["player_name_input"].rect
                label = font_label.render("玩家名字:", True, label_color)
                label_x = max(panel_rect.x + 20, pn_rect.x - label.get_width() - 16)
                label_y = pn_rect.y + (pn_rect.height - label.get_height()) // 2
                screen.blit(label, (label_x, label_y))
                ui["player_name_input"].draw(screen)

                # 难度设置已从界面移除

                # 音量标签与滑块
                slider_rect = ui["volume_slider_rect"]
                label = font_label.render("音量:", True, label_color)
                label_x = max(panel_rect.x + 20, slider_rect.x - label.get_width() - 16)
                label_y = slider_rect.y + (slider_rect.height - label.get_height()) // 2
                screen.blit(label, (label_x, label_y))

                # 音量滑块背景
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
                screen.blit(vol_label, (slider_rect.right + 16, slider_rect.y - 2))

                # 主题切换标签与按钮
                theme_y = None
                if ui.get("light_btn"):
                    theme_y = ui["light_btn"].rect.y
                elif ui.get("dark_btn"):
                    theme_y = ui["dark_btn"].rect.y
                theme_label = font_label.render("主题:", True, label_color)
                if theme_y is None:
                    screen.blit(theme_label, (panel_rect.x + 20, panel_rect.y + 220))
                else:
                    screen.blit(theme_label, (panel_rect.x + 20, theme_y + 6))
                if ui.get("light_btn"):
                    ui["light_btn"].draw(screen)
                if ui.get("dark_btn"):
                    ui["dark_btn"].draw(screen)
                # 全屏切换按钮
                if ui.get("fullscreen_btn"):
                    # 动态刷新文案，避免显示状态不一致
                    try:
                        is_fs = bool(APP_STATE["settings"].get("fullscreen", False))
                        ui["fullscreen_btn"].update_text(f"全屏: {'是' if is_fs else '否'}")
                    except Exception:
                        pass
                    ui["fullscreen_btn"].draw(screen)

                # 快捷键说明已从设置界面移除

                # 返回按钮
                if ui.get("back_btn"):
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
