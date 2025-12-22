"""
服务器主程序入口

启动游戏服务器，监听客户端连接。
"""

import logging
import sys
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.shared.constants import DEFAULT_HOST, DEFAULT_PORT  # noqa: E402

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("server.log"), logging.StreamHandler()],
)

logger = logging.getLogger(__name__)


def main():
    """启动服务器主函数"""
    logger.info("=" * 50)
    logger.info("Draw & Guess 游戏服务器启动中...")
    logger.info(f"监听地址: {DEFAULT_HOST}:{DEFAULT_PORT}")
    logger.info("=" * 50)

    try:
        # 导入并创建服务器
        from src.server.network import GameServer

        server = GameServer(DEFAULT_HOST, DEFAULT_PORT)

        # 启动服务器
        if server.start():
            logger.info("服务器运行中，按 Ctrl+C 停止")

            # 保持服务器运行
            import time

            while True:
                time.sleep(1)
        else:
            logger.error("服务器启动失败")

    except KeyboardInterrupt:
        logger.info("\n服务器正在关闭...")
        if "server" in locals():
            server.stop()
    except Exception as e:
        logger.error(f"服务器错误: {e}", exc_info=True)
    finally:
        logger.info("服务器已停止")


if __name__ == "__main__":
    main()
