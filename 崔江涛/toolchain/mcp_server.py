"""
mcp_server.py — ESP32 AI Piano 工具链 MCP 服务器
==================================================

基于 MCP (Model Context Protocol) Python SDK 实现的工具服务器。
通过 stdio 传输与 Claude Code 通信，将串口监控等硬件工具暴露为
AI 可调用的 Tool。

V2 架构变更：
  服务器启动时立即建立串口连接并启动后台采集线程，无需等待
  第一次工具调用。所有 ESP32 输出被持续缓存，AI 随时查询
  "最近发生了什么"。

=== 如何被 Claude Code 连接（供理解，配置需自行操作） ===

Claude Code 通过 MCP 协议与本文件通信：

  1. 启动方式：Claude Code 读取配置文件中的 command 字段，
     以子进程方式启动本文件：
       python path/to/toolchain/mcp_server.py

  2. 通信协议：JSON-RPC over stdio
     - stdout → 服务器发送 JSON-RPC 响应给 Claude Code
     - stderr → 服务器日志（不会干扰协议通信）
     - stdin  → Claude Code 发送 JSON-RPC 请求给服务器

  3. 发现工具：Claude Code 连接后首先发送 tools/list 请求，
     本服务器返回已注册的工具列表（含 name/description/inputSchema）。
     Claude 根据这些信息在对话中自动判断何时调用哪个工具。

  4. 调用工具：用户说"帮我看看 ESP32 在输出什么"时，Claude 根据
     serial_monitor 工具的 description 判断匹配，发送 tools/call
     请求。本服务器从后台缓冲区直接查询缓存数据，毫秒级返回。

  5. Claude Code 配置示例（放在 ~/.claude/claude-code.json 或项目
     .mcp.json 中）：
       {
         "mcpServers": {
           "esp32-piano": {
             "command": "python",
             "args": ["toolchain/mcp_server.py"],
             "cwd": "C:/Users/notch/Desktop/ESP32-AI-Piano"
           }
         }
       }

=== 当前状态 ===

  已注册工具：serial_monitor, file_transfer, reset_device,
              fetch_logs, execute_program, report_error（6个）
"""

import sys
import os
import json
import logging
import asyncio

# 确保 toolchain 目录在 sys.path 中，使工具模块可导入
_TOOLCHAIN_DIR = os.path.dirname(os.path.abspath(__file__))
if _TOOLCHAIN_DIR not in sys.path:
    sys.path.insert(0, _TOOLCHAIN_DIR)

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# ─── 日志配置 ───────────────────────────────────────────────
# MCP 协议使用 stdout 传输 JSON-RPC，因此日志必须输出到 stderr，
# 否则会破坏协议消息格式导致连接失败。

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    stream=sys.stderr,
)
logger = logging.getLogger('mcp_server')


# ─── 服务器实例 ─────────────────────────────────────────────

app = Server("esp32-piano-toolchain")
logger.info("MCP Server 'esp32-piano-toolchain' 已创建（V2: 后台持续采集模式）")


# ─── 后台采集预启动 ─────────────────────────────────────────
# 在服务器启动时立即建立串口连接并开启后台采集线程。
# 这样从启动第一刻起 ESP32 的所有输出都被缓存，不会因为
# "AI 还没调用工具"而漏掉数据。

def _init_serial_collection() -> bool:
    """
    在 MCP Server 启动时初始化串口连接和后台采集。

    这是 V2 架构的核心：后台采集线程从服务器启动即开始运行，
    独立于任何工具调用。AI 连接后随时可以查询历史缓存。
    """
    from serial_connection import SerialConnection
    conn = SerialConnection()

    if not conn.connect():
        logger.warning("串口连接失败，后台采集未启动（稍后工具调用时会重试）")
        return False

    if not conn.start_background_collection():
        logger.warning("后台采集启动失败")
        return False

    logger.info("后台串口采集已启动 — ESP32 输出将持续被缓存")
    return True


# ─── 工具注册：list_tools ───────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    返回当前所有可用工具的元数据。

    Claude Code 连接后会自动调用此方法获取工具列表。
    每个工具的 description 和 inputSchema 会被 Claude 用于
    判断"用户这句话是否该调用这个工具"。

    添加新工具时，只需在此函数中追加 Tool 对象即可。
    """
    tools = [
        Tool(
            name="serial_monitor",
            description=(
                "查询 ESP32 串口输出的最近历史记录（V2: 后台缓存查询）。"
                "ESP32 的所有 print() 输出从 MCP Server 启动起就被持续"
                "采集并缓存，此工具从缓存中查询最近 N 秒的数据，立即返回。"
                "适用于以下场景："
                "(1) 查看 ESP32 当前运行状态（如数字钢琴按键记录）；"
                "(2) 诊断固件问题（捕获异常信息和 Traceback）；"
                "(3) 验证固件修改是否生效（上传代码后观察输出变化）；"
                "(4) 回顾「刚才发生了什么」（不需要提前掐时机监控）。"
                "串口配置：COM3, 115200bps。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "duration_sec": {
                        "type": "number",
                        "description": (
                            "查询最近多少秒内的缓存数据，默认 10 秒。"
                            "取值范围 1~300 秒。数值越大返回的数据越多。"
                            "注意：这是查询后台已缓存的历史数据窗口，"
                            "不会实时等待。调用立即返回（毫秒级）。"
                        ),
                        "default": 10.0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="file_transfer",
            description=(
                "将本地 Python 文件上传到 ESP32 文件系统，或从 ESP32 下载文件到本地。"
                "基于 MicroPython raw REPL 协议 + base64 分块传输，确保二进制安全。"
                "支持 upload 和 download 两个方向。"
                "传输前自动暂停后台采集，传输后自动恢复。"
                "注意：传输过程会中断 ESP32 上正在运行的程序；"
                "完成后需配合 reset_device（软复位）恢复程序运行。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "description": (
                            "传输方向：'upload'（上传本地文件到 ESP32，默认）"
                            "或 'download'（从 ESP32 下载文件到本地）。"
                        ),
                        "enum": ["upload", "download"],
                        "default": "upload",
                    },
                    "local_path": {
                        "type": "string",
                        "description": (
                            "本地文件路径。upload 时为要上传的文件（必填）；"
                            "download 时为保存目标路径（默认使用 remote_path 的文件名）。"
                        ),
                    },
                    "remote_path": {
                        "type": "string",
                        "description": (
                            "ESP32 上的文件路径，如 'main.py' 或 'piano.py'。"
                        ),
                    },
                    "timeout_sec": {
                        "type": "number",
                        "description": (
                            "传输总超时时间（秒），默认 30。"
                            "大文件可能需要更长时间。"
                        ),
                        "default": 30.0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="reset_device",
            description=(
                "复位 ESP32 设备，支持软复位（Ctrl+D）和硬复位（DTR）两种模式。"
                "复位后等待设备就绪，捕获并返回启动信息（boot_msg）。"
                "适用于以下场景："
                "(1) 文件上传后恢复程序运行（配合 file_transfer 使用）；"
                "(2) 固件修改后重启以加载新代码；"
                "(3) 设备异常时尝试恢复。"
                "hard 模式在 DTR 不支持时会自动回退到 soft 模式。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "description": (
                            "复位模式：'soft'（默认，Ctrl+D 软复位，通过 REPL 指令触发 MicroPython 重启）"
                            "或 'hard'（DTR 引脚硬件复位，模拟物理按 RST 按钮）。"
                            "hard 模式失败时自动回退到 soft。"
                        ),
                        "enum": ["soft", "hard"],
                        "default": "soft",
                    },
                    "wait_ready_sec": {
                        "type": "number",
                        "description": (
                            "复位后等待设备就绪的超时时间（秒），默认 5.0。"
                            "在此期间捕获启动信息并检测 ESP32 是否已成功运行 main.py。"
                            "时间过短可能来不及捕获完整的启动横幅。"
                        ),
                        "default": 5.0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="fetch_logs",
            description=(
                "从后台采集缓冲区中检索日志，支持关键字和时间范围过滤。"
                "与 serial_monitor 的区别：serial_monitor 返回原始数据，"
                "fetch_logs 增加了关键字搜索和时间窗口过滤，适合定向查找"
                "特定事件（如查找所有'演奏'记录、排查特定错误信息等）。"
                "过滤不区分大小写。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "keyword": {
                        "type": "string",
                        "description": (
                            "搜索关键字，只返回包含此关键字的行（不区分大小写）。"
                            "留空则不过滤关键字，返回时间范围内的所有行。"
                        ),
                    },
                    "since_sec": {
                        "type": "number",
                        "description": (
                            "只检索最近 N 秒内的日志。留空则检索全部缓存。"
                            "例如 since_sec=30 只返回最近半分钟内的数据。"
                        ),
                    },
                    "max_lines": {
                        "type": "integer",
                        "description": (
                            "最多返回多少行匹配结果。超过此数量时保留最新的行。"
                            "默认 100。"
                        ),
                        "default": 100,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="execute_program",
            description=(
                "在 ESP32 上执行 Python 代码或启动指定模块。"
                "支持两种模式："
                "(1) code 模式：直接发送 Python 代码片段执行并等待返回输出；"
                "(2) module 模式：导入指定模块（如 'piano'），执行后自动"
                "软复位让 main.py 运行，模块在 ESP32 后台持续运行。"
                "执行超时时会自动发送 Ctrl+C 中断，不会让设备卡死。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "module": {
                        "type": "string",
                        "description": (
                            "要导入执行的模块名，如 'piano'。"
                            "会生成 'import {module}' 在 ESP32 执行，"
                            "完成后自动软复位重启 main.py。"
                        ),
                    },
                    "code": {
                        "type": "string",
                        "description": (
                            "直接在 ESP32 上执行的 Python 代码字符串。"
                            "适用于临时测试、调试命令等。"
                            "如果同时提供 code 和 module，code 优先。"
                        ),
                    },
                    "timeout_sec": {
                        "type": "number",
                        "description": (
                            "等待执行完成的超时时间（秒），默认 30。"
                            "超时后发送 Ctrl+C 中断并返回已捕获的输出。"
                        ),
                        "default": 30.0,
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="report_error",
            description=(
                "检查 ESP32 最近的串口输出，识别 MicroPython 异常信息"
                "并生成结构化诊断报告。支持识别 ValueError、TypeError、"
                "ImportError、OSError、SyntaxError、NameError 等常见异常类型。"
                "适用于：固件调试后检查是否有运行时错误、"
                "验证修复是否消除了之前的异常。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "context_lines": {
                        "type": "integer",
                        "description": (
                            "检查最近 N 行日志，默认 50。"
                            "数值越大扫描范围越广，但可能包含历史旧错误。"
                        ),
                        "default": 50,
                    },
                },
                "required": [],
            },
        ),
    ]

    logger.info("list_tools() 被调用，返回 %d 个工具", len(tools))
    return tools


# ─── 工具调用：call_tool ─────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    处理来自 Claude Code 的工具调用请求。

    Args:
        name: 工具名（与 list_tools 返回的 Tool.name 对应）
        arguments: 工具参数字典（由 Claude 根据 inputSchema 构造）

    Returns:
        TextContent 列表，内容为格式化的工具执行结果。
        注意：即使工具执行失败，也应返回结构化错误文本而非抛异常，
        这样 Claude 可以理解错误原因并给用户友好提示。
    """
    logger.info("call_tool(name=%s, args=%s)", name, arguments)

    try:
        if name == "serial_monitor":
            return await _handle_serial_monitor(arguments)

        elif name == "file_transfer":
            return await _handle_file_transfer(arguments)

        elif name == "reset_device":
            return await _handle_reset_device(arguments)

        elif name == "fetch_logs":
            return await _handle_fetch_logs(arguments)

        elif name == "execute_program":
            return await _handle_execute_program(arguments)

        elif name == "report_error":
            return await _handle_report_error(arguments)

        else:
            return [TextContent(
                type="text",
                text=f"未知工具: {name}。"
                     f"当前可用工具: serial_monitor, file_transfer, reset_device, "
                     f"fetch_logs, execute_program, report_error",
            )]

    except Exception as e:
        logger.error("call_tool(%s) 未预期异常: %s", name, e, exc_info=True)
        return [TextContent(
            type="text",
            text=json.dumps({
                "status": "error",
                "error_message": f"MCP Server 内部错误: {str(e)}",
            }, ensure_ascii=False, indent=2),
        )]


async def _handle_serial_monitor(arguments: dict) -> list[TextContent]:
    """
    处理 serial_monitor 工具调用（V2：查询后台缓存）。

    从 arguments 中提取 duration_sec 参数，调用 tools/serial_monitor.py
    的 monitor() 函数从后台缓冲区查询历史数据。

    V2 变更：monitor() 现在是纯查询操作，不再需要 asyncio.to_thread
    （不涉及 sleep 等待）。但保留 to_thread 以兼容内部可能存在的
    I/O 操作。
    """
    from tools.serial_monitor import monitor
    from serial_connection import SerialConnection

    duration_sec = float(arguments.get("duration_sec", 10.0))
    duration_sec = max(1.0, min(300.0, duration_sec))

    logger.info("查询串口缓存: 最近 %.1f 秒", duration_sec)

    result = await asyncio.to_thread(monitor, duration_sec=duration_sec)

    # 格式化为文本返回
    output_parts = [
        f"=== ESP32 串口缓存查询结果 ===",
        f"状态: {result['status']}",
        f"命中行数: {result['line_count']}",
        f"累计断连: {result['disconnects']} 次",
        f"查询窗口: {result['duration_sec']} 秒",
    ]

    if result.get('error_message'):
        output_parts.append(f"错误信息: {result['error_message']}")

    if result['lines']:
        output_parts.append(f"\n--- 最近 {result['duration_sec']} 秒内的输出 "
                           f"({result['line_count']} 行) ---")
        for i, line in enumerate(result['lines'], 1):
            output_parts.append(f"  {i:4d}: {line}")
    else:
        output_parts.append(f"\n(最近 {result['duration_sec']} 秒内无输出)")

    output_parts.append(f"\n--- 系统状态 ---")
    conn = SerialConnection()
    port_info = conn.get_port_info()
    output_parts.append(f"串口状态: {'已连接' if port_info['is_connected'] else '未连接'}")
    output_parts.append(f"后台采集: {'运行中' if port_info['collection_active'] else '已停止'}")
    output_parts.append(f"缓冲区: {port_info['buffer_size']} 行")

    formatted_text = "\n".join(output_parts)
    return [TextContent(type="text", text=formatted_text)]


async def _handle_file_transfer(arguments: dict) -> list[TextContent]:
    """处理 file_transfer 工具调用（upload / download）。"""
    from tools.file_transfer import upload_file, download_file

    direction = arguments.get("direction", "upload")
    local_path = arguments.get("local_path", "")
    remote_path = arguments.get("remote_path", "")
    timeout_sec = float(arguments.get("timeout_sec", 30.0))
    timeout_sec = max(5.0, min(120.0, timeout_sec))

    if not remote_path:
        remote_path = local_path
    if not local_path and direction == "upload":
        return [TextContent(type="text",
                text="参数缺失: 上传时 local_path 为必填项")]

    if direction == "download":
        logger.info("文件下载: %s → %s", remote_path, local_path)
        result = await asyncio.to_thread(
            download_file, remote_path=remote_path,
            local_path=local_path, timeout_sec=timeout_sec
        )
        direction_text = "下载"
    else:
        logger.info("文件上传: %s → %s", local_path, remote_path)
        result = await asyncio.to_thread(
            upload_file, local_path=local_path,
            remote_path=remote_path, timeout_sec=timeout_sec
        )
        direction_text = "上传"

    output_parts = [
        f"=== ESP32 文件{direction_text}结果 ===",
        f"状态: {result['status']}",
        f"本地: {result.get('local_path', local_path)}",
        f"远程: {result.get('remote_path', remote_path)}",
        f"传输: {result['bytes_transferred']} 字节",
    ]
    if result.get('error_message'):
        output_parts.append(f"错误: {result['error_message']}")

    formatted_text = "\n".join(output_parts)
    return [TextContent(type="text", text=formatted_text)]


async def _handle_reset_device(arguments: dict) -> list[TextContent]:
    """
    处理 reset_device 工具调用。

    调用 tools/reset_device.py 的 reset() 函数，
    执行软复位或硬复位并返回启动信息。
    """
    from tools.reset_device import reset

    mode = str(arguments.get("mode", "soft"))
    wait_ready_sec = float(arguments.get("wait_ready_sec", 5.0))
    wait_ready_sec = max(1.0, min(30.0, wait_ready_sec))

    if mode not in ("soft", "hard"):
        mode = "soft"

    logger.info("复位设备: mode=%s, wait=%.1f 秒", mode, wait_ready_sec)

    result = await asyncio.to_thread(reset, mode=mode, wait_ready_sec=wait_ready_sec)

    output_parts = [
        f"=== ESP32 复位结果 ===",
        f"复位模式: {mode}",
        f"状态: {result['status']}",
        f"设备就绪: {'是' if result['ready'] else '否'}",
    ]

    if result.get('boot_msg'):
        output_parts.append(f"\n--- 启动信息 ---")
        output_parts.append(result['boot_msg'])
    else:
        output_parts.append(f"\n(无启动信息)")

    formatted_text = "\n".join(output_parts)
    return [TextContent(type="text", text=formatted_text)]


async def _handle_fetch_logs(arguments: dict) -> list[TextContent]:
    """
    处理 fetch_logs 工具调用。

    调用 tools/fetch_logs.py 的 fetch() 函数，
    从后台缓冲区中按关键字和时间范围检索日志。
    """
    from tools.fetch_logs import fetch

    keyword = arguments.get("keyword") or None
    since_sec = arguments.get("since_sec")
    max_lines = int(arguments.get("max_lines", 100))

    if since_sec is not None:
        since_sec = float(since_sec)
    max_lines = max(1, min(500, max_lines))

    logger.info("检索日志: keyword=%r, since_sec=%s, max_lines=%d",
                keyword, since_sec, max_lines)

    result = await asyncio.to_thread(
        fetch, keyword=keyword, since_sec=since_sec, max_lines=max_lines
    )

    output_parts = [
        f"=== ESP32 日志检索结果 ===",
        f"状态: {result['status']}",
        f"缓冲区总数: {result['total_cached']} 行",
        f"匹配行数: {result['match_count']} 行",
        f"消息: {result['message']}",
    ]

    if result['matches']:
        output_parts.append(f"\n--- 匹配内容 ({result['match_count']} 行) ---")
        for i, entry in enumerate(result['matches'], 1):
            ts = entry.get('timestamp', 0)
            if isinstance(ts, (int, float)):
                import time as _time
                ts = _time.strftime('%H:%M:%S', _time.localtime(ts))
            output_parts.append(f"  {i:4d}: [{ts}] {entry['line']}")
    else:
        output_parts.append(f"\n(无匹配结果)")

    formatted_text = "\n".join(output_parts)
    return [TextContent(type="text", text=formatted_text)]


async def _handle_execute_program(arguments: dict) -> list[TextContent]:
    """处理 execute_program 工具调用。"""
    from tools.execute_program import execute

    module = arguments.get("module") or None
    code = arguments.get("code") or None
    timeout_sec = float(arguments.get("timeout_sec", 30.0))
    timeout_sec = max(1.0, min(120.0, timeout_sec))

    logger.info("执行程序: module=%r, code=%r, timeout=%.1f",
                module,
                code[:80] + '...' if code and len(code) > 80 else code,
                timeout_sec)

    result = await asyncio.to_thread(
        execute, module=module, code=code, timeout_sec=timeout_sec
    )

    output_parts = [
        f"=== ESP32 程序执行结果 ===",
        f"状态: {result['status']}",
        f"exit_code: {result['exit_code']}",
    ]

    if result.get('stdout'):
        output_parts.append(f"\n--- stdout ---")
        output_parts.append(result['stdout'])
    else:
        output_parts.append(f"\n--- stdout ---\n(空)")

    if result.get('stderr'):
        output_parts.append(f"\n--- stderr ---")
        output_parts.append(result['stderr'])

    formatted_text = "\n".join(output_parts)
    return [TextContent(type="text", text=formatted_text)]


async def _handle_report_error(arguments: dict) -> list[TextContent]:
    """处理 report_error 工具调用。"""
    from tools.report_error import report

    context_lines = int(arguments.get("context_lines", 50))
    context_lines = max(1, min(500, context_lines))

    logger.info("错误检测: context_lines=%d", context_lines)

    result = await asyncio.to_thread(report, context_lines=context_lines)

    output_parts = [
        f"=== ESP32 错误诊断报告 ===",
        f"状态: {result['status']}",
        f"发现异常: {'是' if result['has_errors'] else '否'}",
        f"消息: {result['message']}",
    ]

    if result['errors']:
        output_parts.append(f"\n--- 异常详情 ({len(result['errors'])} 个) ---")
        for i, e in enumerate(result['errors'], 1):
            output_parts.append(f"  {i}. [{e['type']}] {e['message']}")
            output_parts.append(f"     原文: {e['line'][:120]}")

    formatted_text = "\n".join(output_parts)
    return [TextContent(type="text", text=formatted_text)]


# ─── 启动入口 ────────────────────────────────────────────────

async def main():
    """
    启动 MCP Server 并开始监听 stdio 上的 JSON-RPC 请求。

    V2 启动流程：
      1. 建立串口连接（COM3, 115200）  ← 新增
      2. 启动后台采集线程              ← 新增
      3. 开始监听 MCP 请求
    """
    logger.info("MCP Server 启动中...")
    logger.info("通信方式: stdio (stdin/stdout)")

    # V2: 预先建立串口连接并启动后台采集
    _init_serial_collection()

    async with stdio_server() as (read_stream, write_stream):
        logger.info("MCP Server 就绪，等待 Claude Code 连接...")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("MCP Server 已停止（KeyboardInterrupt）")
    except Exception as e:
        logger.error("MCP Server 异常退出: %s", e, exc_info=True)
        sys.exit(1)
