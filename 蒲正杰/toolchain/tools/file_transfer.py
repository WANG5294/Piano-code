"""
文件传输工具：在本地与 ESP32 文件系统之间传输文件。

对应 6 项基本能力之"文件传输"。
"""

from typing import List

from esp32_client import get_client


def upload_file(local_path: str, remote_path: str = "") -> str:
    """
    将本地 MicroPython 文件上传到 ESP32

    Args:
        local_path: 本地文件路径
        remote_path: ESP32 上的目标路径，留空则默认为本地文件名
    """
    return get_client().upload_file(local_path, remote_path)


def list_files(path: str = "/") -> List[str]:
    """
    列出 ESP32 文件系统中的文件

    Args:
        path: 目标目录，默认为根目录 "/"
    """
    return get_client().list_files(path)


def remove_file(remote_path: str) -> str:
    """
    删除 ESP32 上的文件

    Args:
        remote_path: ESP32 上的文件路径
    """
    return get_client().remove_file(remote_path)
