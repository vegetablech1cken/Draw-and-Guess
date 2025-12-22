"""
示例：如何使用游戏 API

演示如何创建自定义客户端和使用服务器 API。
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

# 示例1: 使用服务器 API
def example_server():
    """演示如何使用服务器 API"""
    from src.server.network import GameServer
    from src.server.models import Player, Room

    # 创建游戏服务器
    server = GameServer("127.0.0.1", 5555)

    # 启动服务器
    if server.start():
        print("服务器启动成功！")
        print("等待客户端连接...")

        # 服务器会自动处理连接和消息
        # 你可以通过 server.players 和 server.rooms 访问当前状态

        try:
            import time

            while True:
                time.sleep(1)
                # 可以在这里添加自定义逻辑
                # 例如：显示在线玩家数
                if len(server.players) > 0:
                    print(f"当前在线玩家数: {len(server.players)}")
        except KeyboardInterrupt:
            print("\n停止服务器...")
            server.stop()


# 示例2: 使用客户端 API
def example_client():
    """演示如何使用客户端 API"""
    from src.client.game import NetworkClient

    # 创建网络客户端
    client = NetworkClient("127.0.0.1", 5555)

    # 定义消息处理器
    def on_connected(data):
        print(f"连接成功！玩家列表: {data.get('players', [])}")

    def on_chat(data):
        print(f"聊天消息: {data.get('player_name')}: {data.get('message')}")

    def on_game_started(data):
        if data.get("is_drawer"):
            print(f"你是画家！词语是：{data.get('word')}")
        else:
            print(f"{data.get('drawer_name')} 正在画画！")

    # 注册消息处理器
    client.register_handler("connected", on_connected)
    client.register_handler("chat", on_chat)
    client.register_handler("game_started", on_game_started)

    # 连接到服务器
    if client.connect("示例玩家"):
        print("已连接到服务器")

        # 发送聊天消息
        client.send_chat("你好，大家好！")

        # 开始游戏（如果是第一个玩家）
        import time

        time.sleep(2)
        client.start_game()

        # 保持连接
        try:
            while client.connected:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n断开连接...")
            client.disconnect()


# 示例3: 使用数据模型
def example_models():
    """演示如何使用数据模型"""
    from src.server.models import Player, Room

    # 创建玩家
    player1 = Player("player1", "小明")
    player2 = Player("player2", "小红")

    print(f"玩家1: {player1}")
    print(f"玩家2: {player2}")

    # 创建房间
    room = Room("room1", max_players=4)
    print(f"房间: {room}")

    # 添加玩家到房间
    room.add_player(player1)
    room.add_player(player2)
    print(f"房间玩家数: {len(room.players)}")

    # 开始游戏回合
    room.start_round("苹果")
    print(f"当前词语: {room.current_word}")
    print(f"当前画家: {room.current_drawer}")

    # 玩家猜测
    is_correct = room.check_guess("player2", "苹果")
    print(f"玩家2猜测是否正确: {is_correct}")
    print(f"玩家2分数: {player2.score}")

    # 结束回合
    room.end_round()
    print("回合结束")


# 示例4: 使用 UI 组件
def example_ui():
    """演示如何使用 UI 组件（需要 pygame）"""
    import pygame
    from src.client.ui import Canvas, InputBox, Button

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("UI 组件示例")
    clock = pygame.time.Clock()

    # 创建组件
    canvas = Canvas(50, 50, 500, 400)
    canvas.enable(True)

    input_box = InputBox(50, 470, 400, 40, placeholder="输入文字...")
    button = Button(470, 470, 100, 40, "提交")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            # 处理输入框事件
            text = input_box.handle_event(event)
            if text:
                print(f"输入的文字: {text}")

            # 处理按钮点击
            if event.type == pygame.MOUSEBUTTONDOWN:
                if button.is_clicked(event.pos, event.button):
                    print("按钮被点击！")

                if canvas.is_point_inside(event.pos):
                    canvas.start_drawing(event.pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                canvas.stop_drawing()

            elif event.type == pygame.MOUSEMOTION:
                if canvas.drawing:
                    canvas.draw_line(event.pos)

        # 绘制
        screen.fill((255, 255, 255))
        canvas.draw(screen)
        input_box.draw(screen)
        button.draw(screen)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    print("你画我猜游戏 - API 示例")
    print("=" * 50)
    print("\n可用的示例:")
    print("1. example_server() - 启动服务器")
    print("2. example_client() - 连接客户端")
    print("3. example_models() - 使用数据模型")
    print("4. example_ui() - 使用 UI 组件")
    print("\n运行方式:")
    print("python examples.py")
    print("然后在 Python 交互式环境中调用函数")
    print("\n或者直接运行某个示例:")
    print("python -c 'from examples import example_models; example_models()'")

    # 默认运行模型示例（不需要 GUI）
    print("\n" + "=" * 50)
    print("运行数据模型示例:")
    print("=" * 50)
    example_models()
