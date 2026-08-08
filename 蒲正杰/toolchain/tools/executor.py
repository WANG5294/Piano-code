"""
程序执行工具：在 ESP32 上执行程序、复位设备、烧录固件。

对应 6 项基本能力之"程序执行"与"复位"，
并包含进阶能力"固件烧录"（通过 esptool 部署 MicroPython 固件）。
"""

from esp32_client import get_client


def execute_program(remote_path: str, timeout: float = 5.0) -> str:
    """
    在 ESP32 上执行指定的 MicroPython 文件

    Args:
        remote_path: ESP32 上的 Python 文件路径
        timeout: 执行超时时间（秒）
    """
    return get_client().run_file(remote_path, timeout=timeout)


def execute_repl(command: str, timeout: float = 5.0) -> str:
    """
    在 ESP32 REPL 中执行单条 Python 命令

    Args:
        command: 要执行的 Python 命令
        timeout: 执行超时时间（秒）
    """
    return get_client().exec_raw(command, timeout=timeout)


def reset_esp32(hard: bool = False) -> str:
    """
    复位 ESP32 开发板

    Args:
        hard: 是否使用硬复位（通过 DTR/RTS），默认软复位
    """
    client = get_client()
    if hard:
        return client.hard_reset()
    return client.reset()


def flash_firmware(firmware_path: str, port: str = "", baudrate: int = 460800, erase: bool = True) -> str:
    """
    通过 esptool 烧录 MicroPython 固件到 ESP32

    注意：烧录前需要先从 https://micropython.org/download/ESP32_GENERIC/
    下载对应 ESP32 型号的 .bin 固件文件。

    Args:
        firmware_path: 本地 MicroPython 固件 (.bin) 文件路径
        port: 串口名称，例如 "COM5" 或 "/dev/ttyUSB0"，留空则使用当前已连接端口
        baudrate: 烧录波特率，默认 460800
        erase: 烧录前是否先擦除 Flash，默认 True（建议首次烧录时开启）
    """
    return get_client().flash_firmware(
        firmware_path=firmware_path,
        port=port or None,
        baudrate=baudrate,
        erase=erase,
    )
