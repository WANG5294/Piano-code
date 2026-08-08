"""
ESP32 AI 原生开发工具链 - 工具模块包

按作业要求（8.3 节推荐目录结构）将工具链的各项能力拆分为独立模块：

- connection.py      连接管理（串口连接/断开）
- file_transfer.py   文件传输（上传/列出/删除文件）
- executor.py        程序执行（REPL 执行、运行文件、复位、固件烧录）
- serial_monitor.py  串口监控与运行日志检索
- error_handler.py   错误报告（解析 MicroPython Traceback）

所有模块均基于底层 esp32_client.ESP32Client 串口客户端实现，
mcp_server.py 作为 MCP 接口层调用本包中的工具函数。
"""

import sys
from pathlib import Path

# 确保 toolchain/ 目录在 sys.path 中，以便导入 esp32_client
_TOOLCHAIN_DIR = str(Path(__file__).resolve().parent.parent)
if _TOOLCHAIN_DIR not in sys.path:
    sys.path.insert(0, _TOOLCHAIN_DIR)
