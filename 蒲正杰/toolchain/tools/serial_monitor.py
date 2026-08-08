"""
串口监控工具：读取 ESP32 实时串口输出并检索运行日志。

对应 6 项基本能力之"串口监控"与"日志检索"。
"""

from typing import List

from esp32_client import get_client


def read_serial_output(clear: bool = True) -> str:
    """
    读取 ESP32 的串口输出

    Args:
        clear: 读取后是否清空缓冲区，默认 True
    """
    return get_client().read_serial_output(clear=clear)


def get_logs(lines: int = 100) -> List[str]:
    """
    获取 ESP32 最近的串口日志

    Args:
        lines: 返回最近的日志行数
    """
    return get_client().get_logs(lines=lines)
