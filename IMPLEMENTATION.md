# 🎨 Draw & Guess - 实现说明文档

## 📚 项目概述

本项目实现了一个完整的多人在线"你画我猜"游戏，包含服务器端、客户端和完整的游戏逻辑。

## 🏗️ 架构设计

### 系统架构

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  客户端 1    │◄───────►│   服务器     │◄───────►│  客户端 2    │
│  (Pygame)   │  Socket │  (Python)   │  Socket │  (Pygame)   │
└─────────────┘         └─────────────┘         └─────────────┘
                               ▲
                               │
                               ▼
                        ┌─────────────┐
                        │   词库文件   │
                        │ words.txt   │
                        └─────────────┘
```

### 技术栈

- **编程语言**: Python 3.8+
- **网络通信**: Socket (TCP)
- **图形界面**: Pygame 2.5+
- **数据格式**: JSON
- **测试框架**: pytest

## 📦 核心模块说明

### 1. 服务器端 (src/server/)

#### 1.1 数据模型 (models/)

**Player 类** (`player.py`)
- 表示游戏中的玩家
- 属性：
  - `id`: 玩家唯一标识
  - `name`: 玩家名称
  - `score`: 当前分数
  - `is_drawing`: 是否是当前画家
  - `room_id`: 所在房间ID
  - `conn`: 客户端连接对象
- 方法：
  - `add_score(points)`: 增加分数
  - `reset_score()`: 重置分数
  - `to_dict()`: 转换为字典格式

**Room 类** (`room.py`)
- 表示游戏房间
- 属性：
  - `id`: 房间唯一标识
  - `max_players`: 最大玩家数
  - `players`: 玩家字典
  - `current_word`: 当前词语
  - `current_drawer`: 当前画家ID
  - `round_number`: 回合数
  - `is_active`: 房间是否活跃
- 方法：
  - `add_player(player)`: 添加玩家
  - `remove_player(player_id)`: 移除玩家
  - `start_round(word)`: 开始新回合
  - `end_round()`: 结束回合
  - `check_guess(player_id, guess)`: 检查猜测

#### 1.2 网络层 (network/)

**GameServer 类** (`server.py`)
- 核心服务器实现
- 功能：
  - 监听客户端连接
  - 处理多个客户端并发连接
  - 消息路由和广播
  - 游戏状态管理
- 主要方法：
  - `start()`: 启动服务器
  - `stop()`: 停止服务器
  - `_accept_connections()`: 接受连接线程
  - `_handle_client()`: 处理单个客户端
  - `_process_message()`: 处理客户端消息
  - `_broadcast_to_room()`: 广播消息到房间

**支持的消息类型**:
```python
{
    "connect": "客户端连接",
    "draw": "绘图数据",
    "guess": "玩家猜测",
    "chat": "聊天消息",
    "start_game": "开始游戏",
}
```

### 2. 客户端 (src/client/)

#### 2.1 网络层 (game/network.py)

**NetworkClient 类**
- 客户端网络连接管理
- 功能：
  - 连接到服务器
  - 发送和接收消息
  - 消息处理器注册
- 主要方法：
  - `connect(player_name)`: 连接服务器
  - `disconnect()`: 断开连接
  - `send_message(message)`: 发送消息
  - `send_draw()`: 发送绘图数据
  - `send_guess()`: 发送猜测
  - `register_handler()`: 注册消息处理器

#### 2.2 UI组件 (ui/)

**Canvas 类** (`canvas.py`)
- 绘图画布组件
- 功能：
  - 鼠标绘图
  - 颜色和画笔大小设置
  - 绘图数据导出
  - 从网络数据绘制
- 主要方法：
  - `start_drawing(pos)`: 开始绘图
  - `draw_line(pos)`: 绘制线条
  - `stop_drawing()`: 停止绘图
  - `draw_from_network()`: 从网络数据绘制
  - `clear()`: 清空画布

**InputBox 类** (`input_box.py`)
- 文本输入框组件
- 功能：
  - 文本输入
  - 焦点管理
  - 光标显示
- 主要方法：
  - `handle_event(event)`: 处理事件
  - `draw(screen)`: 绘制到屏幕

**Button 类** (`button.py`)
- 按钮组件
- 功能：
  - 点击检测
  - 悬停效果
  - 自定义样式

#### 2.3 游戏客户端 (game_client.py)

**GameClient 类**
- 集成的游戏客户端
- 功能：
  - 完整的游戏流程
  - UI管理
  - 网络通信
  - 事件处理
- 游戏状态：
  - `connecting`: 连接中
  - `lobby`: 大厅（等待开始）
  - `playing`: 游戏中

### 3. 共享模块 (src/shared/)

#### 3.1 常量定义 (constants.py)

定义了所有游戏常量：
- 网络配置（主机、端口、缓冲区大小）
- 游戏配置（最大玩家数、回合时间）
- 窗口配置（宽度、高度、标题）
- 颜色定义（预设颜色）
- 消息类型

#### 3.2 通信协议 (protocols.py)

**Message 类**
- 消息基类
- 提供JSON序列化/反序列化
- 方法：
  - `to_json()`: 转换为JSON字符串
  - `from_json()`: 从JSON字符串创建

## 🔄 游戏流程

### 1. 启动阶段
```
服务器启动 → 创建默认房间 → 监听端口 → 等待连接
```

### 2. 连接阶段
```
客户端启动 → 输入名称 → 连接服务器 → 加入默认房间 → 进入大厅
```

### 3. 游戏准备
```
等待玩家(≥2) → 点击"开始游戏" → 随机选择画家和词语 → 开始回合
```

### 4. 游戏进行
```
┌─────────────────────────────────────┐
│  画家端                              │
│  - 看到词语                          │
│  - 在画布上绘制                       │
│  - 绘图数据实时发送到服务器           │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  服务器                              │
│  - 接收绘图数据                      │
│  - 广播给其他玩家                    │
│  - 接收玩家猜测                      │
│  - 判断正确性并计分                  │
└─────────────────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│  猜测者端                            │
│  - 看到实时绘图                      │
│  - 输入猜测                          │
│  - 查看分数和聊天                    │
└─────────────────────────────────────┘
```

### 5. 计分规则
```python
基础分数 = 100
实际得分 = max(10, 基础分数 - 猜对顺序 * 10)

例如：
- 第1个猜对: 100 分
- 第2个猜对: 90 分
- 第3个猜对: 80 分
- ...
- 第10+个: 10 分 (保底分)
```

## 📡 网络协议

### 消息格式

所有消息都使用JSON格式：
```json
{
    "type": "消息类型",
    "data": {
        "字段1": "值1",
        "字段2": "值2"
    }
}
```

### 消息类型详解

#### 1. 连接消息 (connect)
```json
// 客户端 → 服务器
{
    "type": "connect",
    "data": {
        "name": "玩家名称"
    }
}

// 服务器 → 客户端
{
    "type": "connected",
    "data": {
        "player_id": "玩家ID",
        "room_id": "房间ID",
        "players": [玩家列表]
    }
}
```

#### 2. 绘图消息 (draw)
```json
{
    "type": "draw",
    "data": {
        "x": 终点X坐标,
        "y": 终点Y坐标,
        "prev_x": 起点X坐标,
        "prev_y": 起点Y坐标,
        "color": [R, G, B],
        "size": 画笔大小
    }
}
```

#### 3. 猜测消息 (guess)
```json
// 客户端 → 服务器
{
    "type": "guess",
    "data": {
        "guess": "猜测内容"
    }
}

// 服务器 → 客户端
{
    "type": "guess_result",
    "data": {
        "correct": true/false,
        "score": 当前分数
    }
}
```

#### 4. 游戏开始 (game_started)
```json
// 给画家
{
    "type": "game_started",
    "data": {
        "word": "要画的词语",
        "is_drawer": true,
        "round": 回合数
    }
}

// 给猜测者
{
    "type": "game_started",
    "data": {
        "is_drawer": false,
        "round": 回合数,
        "drawer_name": "画家名称"
    }
}
```

#### 5. 玩家事件
```json
// 玩家加入
{
    "type": "player_joined",
    "data": {
        "player": {玩家信息}
    }
}

// 玩家离开
{
    "type": "player_left",
    "data": {
        "player_id": "玩家ID",
        "player_name": "玩家名称"
    }
}

// 玩家猜对
{
    "type": "player_guessed",
    "data": {
        "player_id": "玩家ID",
        "player_name": "玩家名称"
    }
}
```

## 🧪 测试

### 运行测试

```bash
# 运行所有测试
pytest

# 运行特定测试
pytest test/unit/test_models.py

# 查看覆盖率
pytest --cov=src tests/
```

### 测试覆盖

当前测试覆盖情况：
- **Player 模型**: 95% 覆盖
- **Room 模型**: 95% 覆盖
- **总体覆盖**: 23%（核心模型接近100%）

## 🚀 部署说明

### 本地部署

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 启动服务器：
```bash
python src/server/main.py
```

3. 启动客户端：
```bash
python src/client/game_client.py
```

### 网络部署

1. 修改 `src/shared/constants.py` 中的 `DEFAULT_HOST`
2. 确保服务器端口（默认5555）对外开放
3. 客户端连接时使用服务器的公网IP

## 🔧 配置选项

在 `src/shared/constants.py` 中可配置：

```python
# 网络配置
DEFAULT_HOST = "127.0.0.1"  # 服务器地址
DEFAULT_PORT = 5555          # 服务器端口
BUFFER_SIZE = 4096           # 缓冲区大小

# 游戏配置
MAX_PLAYERS = 8              # 最大玩家数
MIN_PLAYERS = 2              # 最小玩家数
ROUND_TIME = 60              # 回合时间（秒）

# 窗口配置
WINDOW_WIDTH = 1280          # 窗口宽度
WINDOW_HEIGHT = 720          # 窗口高度
```

## 📈 性能优化

### 已实现的优化

1. **多线程处理**: 每个客户端独立线程
2. **线程安全**: 使用锁保护共享数据
3. **守护线程**: 自动清理资源
4. **连接池**: 复用Socket连接

### 可能的改进

1. **异步IO**: 使用 asyncio 提升并发性能
2. **数据压缩**: 压缩绘图数据减少网络流量
3. **增量更新**: 只发送变化的数据
4. **缓存机制**: 缓存常用数据

## 🔒 安全考虑

### 已实现

1. **输入验证**: 检查消息格式
2. **异常处理**: 捕获并记录异常
3. **连接管理**: 自动清理断开的连接

### 建议改进

1. **身份验证**: 添加登录系统
2. **数据加密**: 使用SSL/TLS
3. **速率限制**: 防止消息洪水攻击
4. **房间密码**: 支持私密房间

## 📝 代码规范

### 遵循的标准

1. **PEP 8**: Python代码规范
2. **类型提示**: 使用类型注解
3. **文档字符串**: 详细的函数说明
4. **错误处理**: 完整的异常捕获

### 命名约定

- **类名**: PascalCase (如 `GameServer`)
- **函数名**: snake_case (如 `start_round`)
- **常量**: UPPER_CASE (如 `MAX_PLAYERS`)
- **私有方法**: 前缀下划线 (如 `_handle_client`)

## 🎯 功能扩展建议

### 短期目标

1. ✅ 基础游戏流程
2. ✅ 实时绘图同步
3. ✅ 猜词和计分
4. ⬜ 添加计时器
5. ⬜ 回合结束自动开始下一轮
6. ⬜ 完善UI界面

### 中期目标

1. ⬜ 支持多个房间
2. ⬜ 房间密码功能
3. ⬜ 玩家排行榜
4. ⬜ 聊天表情系统
5. ⬜ 游戏回放功能

### 长期目标

1. ⬜ Web版本（使用WebSocket）
2. ⬜ 移动端适配
3. ⬜ AI智能提示
4. ⬜ 语音聊天
5. ⬜ 社交功能

## 🐛 已知问题

1. 画布在不同分辨率下可能显示不一致
2. 网络断开后没有自动重连
3. 没有实现回合超时机制
4. 聊天记录不保存

## 📚 参考资料

- [Python Socket 编程](https://docs.python.org/zh-cn/3/howto/sockets.html)
- [Pygame 文档](https://www.pygame.org/docs/)
- [JSON 格式](https://www.json.org/json-zh.html)
- [多线程编程](https://docs.python.org/zh-cn/3/library/threading.html)

## 👥 贡献者

感谢所有贡献者的努力！

## 📄 许可证

本项目采用 MIT 许可证。

---

**文档版本**: 1.0
**最后更新**: 2025-12-22
