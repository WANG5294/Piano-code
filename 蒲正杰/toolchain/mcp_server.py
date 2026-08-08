"""
ESP32 AI 原生开发工具链 - MCP 服务器

功能：
1. 固件烧录：通过 esptool 烧录 MicroPython 固件
2. 文件传输：上传文件到 ESP32
3. 程序执行：运行 ESP32 上的 MicroPython 程序
4. 微控制器复位：软复位或硬复位 ESP32
5. 串口监控：读取 ESP32 实时串口输出
6. 运行日志检索：获取最近串口日志
7. 错误报告：解析 MicroPython Traceback 错误

本文件为 MCP 接口层，具体工具实现位于 tools/ 包：
    tools/connection.py      连接管理
    tools/file_transfer.py   文件传输
    tools/executor.py        程序执行、复位、固件烧录
    tools/serial_monitor.py  串口监控、日志检索
    tools/error_handler.py   错误报告

运行方式：
    python mcp_server.py

注册到新版 Kimi Code CLI：
    新版 Kimi Code CLI 使用 ~/.kimi-code/mcp.json 或项目级 .kimi-code/mcp.json。
    本项目已在根目录创建 .kimi-code/mcp.json，启动 kimi 后输入 /mcp 即可验证。
    也可在 TUI 中使用 /mcp-config 交互式添加。

注意：旧版 kimi-cli 命令 "kimi mcp add" 在新版 kimi 中已不可用。
"""

import sys
import json

# 确保当前目录在路径中，以便导入 tools 包与 esp32_client
sys.path.insert(0, __import__("os").path.dirname(__file__))

from tools import connection, file_transfer, executor, serial_monitor, error_handler

# ------------------------------------------------------------------------------
# MCP 服务器初始化
# ------------------------------------------------------------------------------
try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    print("错误：缺少 mcp 包。请先安装：pip install mcp", file=sys.stderr)
    sys.exit(1)

mcp = FastMCP("esp32-toolchain")


# ------------------------------------------------------------------------------
# 工具 1：连接管理
# ------------------------------------------------------------------------------
@mcp.tool()
def connect_esp32(port: str) -> str:
    """
    连接 ESP32 开发板串口

    Args:
        port: 串口名称，例如 Windows 下的 "COM3"，Linux/Mac 下的 "/dev/ttyUSB0"
    """
    return connection.connect_esp32(port)


@mcp.tool()
def disconnect_esp32() -> str:
    """断开 ESP32 串口连接"""
    return connection.disconnect_esp32()


# ------------------------------------------------------------------------------
# 工具 2：文件传输
# ------------------------------------------------------------------------------
@mcp.tool()
def upload_file(local_path: str, remote_path: str = "") -> str:
    """
    将本地 MicroPython 文件上传到 ESP32

    Args:
        local_path: 本地文件路径
        remote_path: ESP32 上的目标路径，留空则默认为本地文件名
    """
    return file_transfer.upload_file(local_path, remote_path)


@mcp.tool()
def list_files(path: str = "/") -> str:
    """
    列出 ESP32 文件系统中的文件

    Args:
        path: 目标目录，默认为根目录 "/"
    """
    files = file_transfer.list_files(path)
    return json.dumps(files, ensure_ascii=False, indent=2)


@mcp.tool()
def remove_file(remote_path: str) -> str:
    """
    删除 ESP32 上的文件

    Args:
        remote_path: ESP32 上的文件路径
    """
    return file_transfer.remove_file(remote_path)


# ------------------------------------------------------------------------------
# 工具 3：程序执行
# ------------------------------------------------------------------------------
@mcp.tool()
def execute_program(remote_path: str, timeout: float = 5.0) -> str:
    """
    在 ESP32 上执行指定的 MicroPython 文件

    Args:
        remote_path: ESP32 上的 Python 文件路径
        timeout: 执行超时时间（秒）
    """
    return executor.execute_program(remote_path, timeout=timeout)


@mcp.tool()
def execute_repl(command: str, timeout: float = 5.0) -> str:
    """
    在 ESP32 REPL 中执行单条 Python 命令

    Args:
        command: 要执行的 Python 命令
        timeout: 执行超时时间（秒）
    """
    return executor.execute_repl(command, timeout=timeout)


# ------------------------------------------------------------------------------
# 工具 4：微控制器复位
# ------------------------------------------------------------------------------
@mcp.tool()
def reset_esp32(hard: bool = False) -> str:
    """
    复位 ESP32 开发板

    Args:
        hard: 是否使用硬复位（通过 DTR/RTS），默认软复位
    """
    return executor.reset_esp32(hard=hard)


@mcp.tool()
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
    return executor.flash_firmware(
        firmware_path=firmware_path,
        port=port,
        baudrate=baudrate,
        erase=erase,
    )


# ------------------------------------------------------------------------------
# 工具 5：串口监控
# ------------------------------------------------------------------------------
@mcp.tool()
def read_serial_output(clear: bool = True) -> str:
    """
    读取 ESP32 的串口输出

    Args:
        clear: 读取后是否清空缓冲区，默认 True
    """
    return serial_monitor.read_serial_output(clear=clear)


# ------------------------------------------------------------------------------
# 工具 6：运行日志检索
# ------------------------------------------------------------------------------
@mcp.tool()
def get_logs(lines: int = 100) -> str:
    """
    获取 ESP32 最近的串口日志

    Args:
        lines: 返回最近的日志行数
    """
    logs = serial_monitor.get_logs(lines=lines)
    return "\n".join(logs)


# ------------------------------------------------------------------------------
# 工具 7：错误报告
# ------------------------------------------------------------------------------
@mcp.tool()
def report_error() -> str:
    """
    检查并报告 ESP32 最近的 MicroPython 运行时错误
    返回结构化的错误信息 JSON
    """
    error = error_handler.report_error()
    return json.dumps(error, ensure_ascii=False, indent=2)


# ------------------------------------------------------------------------------
# 入口
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    # 使用 stdio 传输方式运行 MCP 服务器
    mcp.run(transport="stdio")
