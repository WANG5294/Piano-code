"""
错误处理工具：解析 MicroPython Traceback，生成结构化错误报告。

对应 6 项基本能力之"错误报告"。
"""

from typing import Any, Dict, Optional

from esp32_client import get_client


def parse_error(output: str) -> Optional[Dict[str, Any]]:
    """
    解析串口输出中的 MicroPython Traceback

    Args:
        output: 串口输出文本

    Returns:
        结构化错误信息字典；未检测到错误时返回 None
    """
    return get_client().parse_error(output)


def report_error() -> Dict[str, Any]:
    """
    检查并报告 ESP32 最近的 MicroPython 运行时错误

    Returns:
        结构化错误信息字典（含 has_error 字段）
    """
    client = get_client()
    output = client.read_serial_output(clear=False)
    error = client.parse_error(output)

    if error is None:
        return {
            "has_error": False,
            "message": "未检测到 Traceback 错误",
        }
    return error
