"""
ESP32 数字钢琴 - 主程序

上电后自动运行数字钢琴功能。
"""

from piano import Piano


def main():
    """主入口"""
    piano = Piano()
    piano.run()


if __name__ == "__main__":
    main()
