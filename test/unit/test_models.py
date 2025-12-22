"""
测试数据模型
"""

import pytest
from src.server.models import Player, Room


def test_player_creation():
    """测试玩家创建"""
    player = Player("p1", "TestPlayer")
    assert player.id == "p1"
    assert player.name == "TestPlayer"
    assert player.score == 0
    assert player.is_drawing is False


def test_player_score():
    """测试玩家分数"""
    player = Player("p1", "TestPlayer")
    player.add_score(10)
    assert player.score == 10
    player.add_score(20)
    assert player.score == 30
    player.reset_score()
    assert player.score == 0


def test_player_to_dict():
    """测试玩家转字典"""
    player = Player("p1", "TestPlayer")
    player.add_score(50)
    player_dict = player.to_dict()

    assert player_dict["id"] == "p1"
    assert player_dict["name"] == "TestPlayer"
    assert player_dict["score"] == 50
    assert player_dict["is_drawing"] is False


def test_room_creation():
    """测试房间创建"""
    room = Room("room1", max_players=4)
    assert room.id == "room1"
    assert room.max_players == 4
    assert len(room.players) == 0
    assert room.is_active is False


def test_room_add_player():
    """测试添加玩家到房间"""
    room = Room("room1", max_players=2)
    player1 = Player("p1", "Player1")
    player2 = Player("p2", "Player2")
    player3 = Player("p3", "Player3")

    # 添加第一个玩家
    assert room.add_player(player1) is True
    assert len(room.players) == 1
    assert player1.room_id == "room1"

    # 添加第二个玩家
    assert room.add_player(player2) is True
    assert len(room.players) == 2

    # 尝试添加第三个玩家（应该失败，超过最大人数）
    assert room.add_player(player3) is False
    assert len(room.players) == 2


def test_room_remove_player():
    """测试从房间移除玩家"""
    room = Room("room1")
    player = Player("p1", "Player1")

    room.add_player(player)
    assert len(room.players) == 1

    room.remove_player("p1")
    assert len(room.players) == 0
    assert player.room_id is None


def test_room_start_round():
    """测试开始回合"""
    room = Room("room1")
    player1 = Player("p1", "Player1")
    player2 = Player("p2", "Player2")

    room.add_player(player1)
    room.add_player(player2)

    room.start_round("测试词语")

    assert room.is_active is True
    assert room.current_word == "测试词语"
    assert room.current_drawer is not None
    assert room.round_number == 1


def test_room_check_guess():
    """测试猜测检查"""
    room = Room("room1")
    player1 = Player("p1", "Player1")
    player2 = Player("p2", "Player2")

    room.add_player(player1)
    room.add_player(player2)
    room.start_round("苹果")

    # 假设 player1 是画家
    if room.current_drawer == "p1":
        # 画家自己不能猜
        assert room.check_guess("p1", "苹果") is False

        # 其他玩家猜对
        assert room.check_guess("p2", "苹果") is True
        assert player2.score > 0

        # 已经猜对的玩家再猜，不计分
        old_score = player2.score
        assert room.check_guess("p2", "苹果") is False
        assert player2.score == old_score
    else:
        # 如果 player2 是画家
        assert room.check_guess("p1", "苹果") is True
        assert player1.score > 0


def test_room_end_round():
    """测试结束回合"""
    room = Room("room1")
    player = Player("p1", "Player1")

    room.add_player(player)
    room.start_round("测试词语")

    assert room.is_active is True

    room.end_round()

    assert room.is_active is False
    assert room.current_word is None
    assert len(room.guessed_players) == 0


def test_room_to_dict():
    """测试房间转字典"""
    room = Room("room1", max_players=4)
    player = Player("p1", "Player1")
    room.add_player(player)

    room_dict = room.to_dict()

    assert room_dict["id"] == "room1"
    assert room_dict["max_players"] == 4
    assert room_dict["player_count"] == 1
    assert len(room_dict["players"]) == 1
    assert room_dict["is_active"] is False
