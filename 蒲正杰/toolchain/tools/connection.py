"""
连接管理工具：负责 ESP32 串口的连接与断开。

对应 6 项基本能力之外的基础能力，其他所有工具都依赖已建立的串口连接。
"""

from esp32_client import get_client


def connect_esp32(port: str) -> str:
    """
    连接 ESP32 开发板串口

    Args:
        port: 串口名称，例如 Windows 下的 "COM3"，Linux/Mac 下的 "/dev/ttyUSB0"
    """
    return get_client().connect(port)


def disconnect_esp32() -> str:
    """断开 ESP32 串口连接"""
    return get_client().disconnect()
