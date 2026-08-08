# KimiCode 工具扩展机制详解 —— MCP 服务器实现指南

> **目标**：让 KimiCode 能够直接操控 ESP32 硬件（文件上传、程序执行、串口监控、错误捕获）  
> **技术路线**：MCP (Model Context Protocol) 服务器  
> **适用 Agent**：KimiCode (VS Code 扩展)  
> **项目**：MCPiano

---

## 1. KimiCode 的扩展架构总览

```
┌─────────────────────────────────────────────────────────────┐
│                    VS Code 窗口                              │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   KimiCode 扩展                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐ │   │
│  │  │   对话界面   │  │  LLM 引擎   │  │ 工具调度器  │ │   │
│  │  │  (Chat UI)  │  │ (Kimi API)  │  │(Tool Router)│ │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘ │   │
│  │         │                │                │        │   │
│  │         └────────────────┴────────────────┘        │   │
│  │                        │                          │   │
│  │              ┌─────────┴─────────┐                │   │
│  │              ▼                   ▼                │   │
│  │  ┌──────────────────┐  ┌──────────────────┐      │   │
│  │  │   内置工具        │  │   MCP 服务器      │      │   │
│  │  │ (文件读写/终端)   │  │ (自定义硬件工具)  │      │   │
│  │  └──────────────────┘  └──────────────────┘      │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                              │
                              │ stdio / SSE
                              ▼
              ┌───────────────────────────────┐
              │      MCPiano MCP Server        │
              │  (Python 3.10+ 独立进程)       │
              │                                │
              │  ┌──────────┐ ┌──────────┐    │
              │  │esp32_    │ │esp32_    │    │
              │  │ upload   │ │ execute  │    │
              │  └──────────┘ └──────────┘    │
              │  ┌──────────┐ ┌──────────┐    │
              │  │esp32_    │ │esp32_    │    │
              │  │ serial   │ │ error    │    │
              │  └──────────┘ └──────────┘    │
              │  ┌──────────┐ ┌──────────┐    │
              │  │esp32_    │ │esp32_    │    │
              │  │ reset    │ │ logs     │    │
              │  └──────────┘ └──────────┘    │
              └──────────┬────────────────────┘
                         │ pyserial
                         ▼
              ┌───────────────────────────────┐
              │     ESP32-D0WD-V3 开发板       │
              │     (MicroPython REPL)         │
              └───────────────────────────────┘
```

**核心机制**：KimiCode 通过 **MCP (Model Context Protocol)** 与外部工具进程通信。MCP 服务器是一个独立的 Python 进程，通过标准输入输出 (stdio) 与 KimiCode 交换 JSON-RPC 消息。

---

## 2. MCP 协议核心概念

### 2.1 什么是 MCP

MCP (Model Context Protocol) 是 Anthropic 推出的开放协议，允许 AI 客户端（如 Claude Code、KimiCode）通过标准化接口调用外部工具。

**关键特性**：
- **标准化**：统一的工具注册、调用、错误处理格式
- **语言无关**：服务器可用 Python/Node.js/Rust 等实现
- **即插即用**：配置即可使用，无需修改客户端代码
- **安全隔离**：工具在独立进程中运行，不影响编辑器主进程

### 2.2 MCP 通信模型

```
┌─────────────┐         JSON-RPC 2.0          ┌─────────────┐
│  KimiCode   │  ◄────────────────────────►  │ MCP Server  │
│  (Client)   │   stdin/stdout 或 SSE        │  (Python)   │
└─────────────┘                              └─────────────┘

消息类型：
  1. initialize      — 初始化握手
  2. tools/list      — 客户端获取工具列表
  3. tools/call      — 客户端调用工具
  4. notifications   — 服务端推送（如串口数据）
```

### 2.3 MCP vs 其他方案

| 方案 | 代表 | 难度 | 推荐度 | 说明 |
|------|------|------|--------|------|
| **MCP 服务器** | Claude Code / KimiCode | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 标准化协议，即插即用 |
| Codex 插件 | OpenAI Codex CLI | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 需适配 OpenAI 生态 |
| Zcode 扩展 | Zed 编辑器 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 需 Rust 开发 |
| OpenCode 扩展 | OpenCode IDE | ⭐⭐⭐ | ⭐⭐⭐ | 社区驱动 |
| 自定义 CLI | 任意 | ⭐⭐ | ⭐⭐ | AI 通过 Shell 调用，不稳定 |

**KimiCode 最佳选择：MCP 服务器**（官方支持、文档完善、Python SDK 成熟）

---

## 3. MCP 服务器实现步骤（MCPiano 专用）

### 3.1 环境准备

```bash
# 在 VM 中操作
cd ~/MCPpiano
source .venv/bin/activate

# 安装 MCP Python SDK
pip install mcp pyserial

# 验证安装
python -c "import mcp; print(mcp.__version__)"
```

### 3.2 项目结构

```
MCPpiano/
├── toolchain/                    # MCP 工具链目录
│   ├── mcp_server.py             # MCP 服务器主入口
│   ├── __init__.py
│   ├── tools/                    # 工具模块
│   │   ├── __init__.py
│   │   ├── file_transfer.py     # esp32_upload / esp32_download
│   │   ├── serial_monitor.py    # esp32_serial / esp32_logs
│   │   ├── executor.py          # esp32_execute / esp32_reset
│   │   └── error_handler.py     # esp32_error
│   └── README.md                # 安装配置说明
```

### 3.3 MCP 服务器骨架代码

```python
# toolchain/mcp_server.py
"""
MCPiano MCP Server
为 KimiCode 提供 ESP32 硬件交互能力
"""

import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools.file_transfer import esp32_upload, esp32_download
from tools.serial_monitor import esp32_serial, esp32_logs
from tools.executor import esp32_execute, esp32_reset
from tools.error_handler import esp32_error

# ─── 服务器初始化 ──────────────────────────
app = Server("mcpiano-esp32")

# ─── 工具注册 ──────────────────────────────
@app.list_tools()
async def list_tools() -> list[Tool]:
    """
    向 KimiCode 注册所有可用工具
    LLM 根据 name 和 description 选择调用哪个工具
    """
    return [
        # ── 文件传输 ──────────────────────
        Tool(
            name="esp32_upload",
            description="将本地 MicroPython 文件推送到 ESP32 开发板。"
                        "上传成功后文件会保存在 ESP32 的文件系统中，"
                        "可以通过 import 导入执行。",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {
                        "type": "string",
                        "description": "本地文件的绝对路径，如 /home/user/project/main.py"
                    },
                    "remote_path": {
                        "type": "string",
                        "description": "ESP32 上的目标路径，如 main.py 或 lib/utils.py"
                    }
                },
                "required": ["local_path", "remote_path"]
            }
        ),
        
        # ── 程序执行 ──────────────────────
        Tool(
            name="esp32_execute",
            description="远程触发 ESP32 上用户程序的运行或停止。"
                        "start: 执行指定入口文件; stop: 发送 Ctrl+C 中断当前运行程序",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_file": {
                        "type": "string",
                        "description": "要执行的入口文件路径，如 main.py"
                    },
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop"],
                        "description": "start 启动程序 | stop 中断程序"
                    }
                },
                "required": ["entry_file", "action"]
            }
        ),
        
        # ── 串口监控 ──────────────────────
        Tool(
            name="esp32_serial",
            description="实时捕获并读取 ESP32 的串口输出。"
                        "可用于监控程序运行状态、查看打印日志、调试输出。",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["start", "stop", "read"],
                        "description": "start 开始监控 | stop 停止监控 | read 读取最近输出"
                    },
                    "duration": {
                        "type": "integer",
                        "description": "读取持续时间（秒），仅 action=read 时有效",
                        "default": 5
                    }
                },
                "required": ["action"]
            }
        ),
        
        # ── 错误报告 ──────────────────────
        Tool(
            name="esp32_error",
            description="自动检测并解析 MicroPython 运行时异常。"
                        "从串口输出中提取 Traceback 信息，返回结构化的错误详情。",
            inputSchema={
                "type": "object",
                "properties": {
                    "auto_parse": {
                        "type": "boolean",
                        "description": "是否自动从最近串口输出中解析错误",
                        "default": True
                    }
                }
            }
        ),
        
        # ── 微控制器复位 ──────────────────
        Tool(
            name="esp32_reset",
            description="通过软件命令重启 ESP32 开发板。"
                        "soft: 调用 machine.reset() 软复位; hard: 通过 DTR/RTS 信号硬复位",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["soft", "hard"],
                        "description": "soft 软复位 | hard 硬复位",
                        "default": "soft"
                    }
                }
            }
        ),
        
        # ── 日志检索 ──────────────────────
        Tool(
            name="esp32_logs",
            description="检索 ESP32 的历史运行日志。"
                        "从串口监控的环形缓冲区中提取最近 N 行输出。",
            inputSchema={
                "type": "object",
                "properties": {
                    "lines": {
                        "type": "integer",
                        "description": "要检索的最近行数",
                        "default": 50
                    },
                    "filter": {
                        "type": "string",
                        "description": "关键词过滤，如 'Error' 或 'Traceback'",
                        "default": ""
                    }
                }
            }
        ),
    ]


# ─── 工具调用路由 ──────────────────────────
@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """
    KimiCode 调用工具时的入口函数
    根据 name 分发到对应的处理函数
    """
    try:
        if name == "esp32_upload":
            result = await esp32_upload(arguments["local_path"], arguments["remote_path"])
        
        elif name == "esp32_download":
            result = await esp32_download(arguments["remote_path"], arguments["local_path"])
        
        elif name == "esp32_execute":
            result = await esp32_execute(arguments["entry_file"], arguments["action"])
        
        elif name == "esp32_serial":
            result = await esp32_serial(arguments["action"], arguments.get("duration", 5))
        
        elif name == "esp32_error":
            result = await esp32_error(arguments.get("auto_parse", True))
        
        elif name == "esp32_reset":
            result = await esp32_reset(arguments.get("mode", "soft"))
        
        elif name == "esp32_logs":
            result = await esp32_logs(arguments.get("lines", 50), arguments.get("filter", ""))
        
        else:
            raise ValueError(f"未知工具: {name}")
        
        return [TextContent(type="text", text=str(result))]
    
    except Exception as e:
        return [TextContent(type="text", text=f"错误: {type(e).__name__}: {str(e)}")]


# ─── 服务器启动 ────────────────────────────
async def main():
    async with stdio_server(server=app) as (read_stream, write_stream):
        await app.run(read_stream, write_stream)

if __name__ == "__main__":
    asyncio.run(main())
```

### 3.4 工具模块实现示例

```python
# toolchain/tools/serial_monitor.py
"""
串口监控模块
持续监听 ESP32 串口输出，维护环形缓冲区
"""

import serial
import asyncio
from collections import deque

# 全局串口连接（单例）
_serial_conn = None
# 环形缓冲区：保存最近 1000 行输出
_log_buffer = deque(maxlen=1000)
# 监控任务
_monitor_task = None

# 串口配置（根据你的实际情况修改）
SERIAL_PORT = "/dev/ttyACM0"  # Linux; Windows 用 COM3
BAUD_RATE = 115200


async def _ensure_connection():
    """确保串口连接已建立"""
    global _serial_conn
    if _serial_conn is None or not _serial_conn.is_open:
        _serial_conn = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    return _serial_conn


async def _monitor_loop():
    """后台监控循环：持续读取串口并写入缓冲区"""
    global _log_buffer
    conn = await _ensure_connection()
    
    while True:
        try:
            if conn.in_waiting > 0:
                line = conn.readline().decode('utf-8', errors='replace').rstrip()
                if line:
                    _log_buffer.append(line)
            else:
                await asyncio.sleep(0.05)  # 50ms 轮询间隔
        except Exception as e:
            _log_buffer.append(f"[串口错误] {e}")
            await asyncio.sleep(1)


async def esp32_serial(action: str, duration: int = 5) -> dict:
    """
    串口监控工具
    action: start | stop | read
    """
    global _monitor_task
    
    if action == "start":
        if _monitor_task is None or _monitor_task.done():
            _monitor_task = asyncio.create_task(_monitor_loop())
        return {"status": "started", "message": "串口监控已启动"}
    
    elif action == "stop":
        if _monitor_task and not _monitor_task.done():
            _monitor_task.cancel()
            try:
                await _monitor_task
            except asyncio.CancelledError:
                pass
        return {"status": "stopped", "message": "串口监控已停止"}
    
    elif action == "read":
        # 读取最近 N 秒的输出
        lines = list(_log_buffer)[-duration*20:]  # 估算每秒 20 行
        return {"status": "ok", "lines": lines, "count": len(lines)}
    
    else:
        raise ValueError(f"无效 action: {action}")


async def esp32_logs(lines: int = 50, filter_str: str = "") -> dict:
    """检索历史日志"""
    result = list(_log_buffer)[-lines:]
    
    if filter_str:
        result = [line for line in result if filter_str in line]
    
    return {"lines": result, "count": len(result)}
```

```python
# toolchain/tools/file_transfer.py
"""
文件传输模块
通过 MicroPython raw REPL 协议上传/下载文件
"""

import serial
import time

SERIAL_PORT = "/dev/ttyACM0"
BAUD_RATE = 115200


def _enter_raw_repl(ser: serial.Serial):
    """进入 MicroPython raw REPL 模式"""
    ser.write(b'\x03')  # Ctrl+C: 中断当前程序
    time.sleep(0.1)
    ser.write(b'\x01')  # Ctrl+A: 进入 raw REPL
    time.sleep(0.1)
    # 等待提示符
    ser.read_until(b'raw REPL; CTRL-B to exit\r\n>')


def _exit_raw_repl(ser: serial.Serial):
    """退出 raw REPL 模式"""
    ser.write(b'\x02')  # Ctrl+B: 退出 raw REPL
    time.sleep(0.1)


async def esp32_upload(local_path: str, remote_path: str) -> dict:
    """
    上传本地文件到 ESP32
    使用 MicroPython raw REPL 协议
    """
    try:
        # 读取本地文件
        with open(local_path, 'rb') as f:
            content = f.read()
        
        # 打开串口
        ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=5)
        _enter_raw_repl(ser)
        
        # 使用 raw REPL 的文件写入命令
        # 方案: 通过 exec 执行 Python 代码创建文件
        cmd = f"""
f = open('{remote_path}', 'wb')
f.write(bytes({list(content)}))
f.close()
print('OK')
"""
        ser.write(cmd.encode())
        ser.write(b'\x04')  # Ctrl+D: 执行
        
        # 等待结果
        response = ser.read_until(b'OK\r\n').decode()
        _exit_raw_repl(ser)
        ser.close()
        
        if 'OK' in response or 'Traceback' not in response:
            return {
                "success": True,
                "message": f"成功上传 {local_path} -> {remote_path}",
                "bytes": len(content)
            }
        else:
            return {"success": False, "message": f"上传失败: {response}"}
    
    except Exception as e:
        return {"success": False, "message": f"错误: {type(e).__name__}: {str(e)}"}


async def esp32_download(remote_path: str, local_path: str) -> dict:
    """从 ESP32 下载文件（扩展功能）"""
    # 类似实现，通过 raw REPL 读取文件内容
    return {"success": True, "message": "下载功能待实现"}
```

---

## 4. KimiCode 配置

### 4.1 配置 MCP 服务器

在 VS Code 中打开 KimiCode 设置，添加 MCP 服务器配置：

```json
// .vscode/mcp.json 或 KimiCode 全局设置
{
  "mcpServers": {
    "mcpiano-esp32": {
      "command": "/home/chuzhen/MCPpiano/.venv/bin/python",
      "args": ["/home/chuzhen/MCPpiano/toolchain/mcp_server.py"],
      "env": {
        "PYTHONPATH": "/home/chuzhen/MCPpiano/toolchain"
      }
    }
  }
}
```

### 4.2 配置说明

| 字段 | 说明 | 示例 |
|------|------|------|
| `command` | MCP 服务器启动命令 | Python 解释器路径 |
| `args` | 传递给命令的参数 | mcp_server.py 路径 |
| `env` | 环境变量 | PYTHONPATH 确保 imports 正常 |

**关键**：KimiCode 通过 **stdio** 与 MCP 服务器通信，所以服务器必须能够：
1. 从 `stdin` 读取 JSON-RPC 请求
2. 向 `stdout` 写入 JSON-RPC 响应
3. 不使用 `print()` 调试（会污染 stdout）

---

## 5. 测试验证

### 5.1 手动测试 MCP 服务器

```bash
cd ~/MCPpiano
source .venv/bin/activate

# 启动服务器（手动测试）
python toolchain/mcp_server.py

# 在另一个终端发送 JSON-RPC 请求测试
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' | python toolchain/mcp_server.py
```

### 5.2 在 KimiCode 中验证

1. 打开 KimiCode 侧边栏
2. 检查工具列表中是否出现 `esp32_upload`、`esp32_execute` 等工具
3. 发送测试指令："请使用 esp32_upload 上传 test.py 到 ESP32"

### 5.3 闭环验证流程

```
1. KimiCode 对话: "帮我写一个钢琴程序"
   → LLM 生成代码

2. KimiCode 自动调用: esp32_upload
   → 上传 main.py 到 ESP32

3. KimiCode 自动调用: esp32_execute(start)
   → 启动程序

4. KimiCode 自动调用: esp32_serial(read)
   → 读取串口输出

5. 发现错误 → KimiCode 自动调用: esp32_error
   → 解析 Traceback

6. LLM 修复代码 → 回到步骤 2
   → 循环直至验证通过
```

---

## 6. 进阶扩展工具

| 工具名 | 功能 | 优先级 | 实现思路 |
|--------|------|--------|----------|
| `esp32_filesystem` | ls/rm/cat 远程文件 | ⭐⭐⭐⭐ | raw REPL 执行 os.listdir() / os.remove() |
| `esp32_gpio_query` | 查询 GPIO 状态 | ⭐⭐⭐⭐ | raw REPL 执行 machine.Pin().value() |
| `esp32_hwinfo` | 采集硬件信息 | ⭐⭐⭐ | os.uname(), esp.flash_size() |
| `esp32_regression` | 自动化回归测试 | ⭐⭐⭐⭐⭐ | 上传→执行→断言串口输出 |
| `esp32_flash` | 自动烧录固件 | ⭐⭐⭐ | 调用 esptool.py |
| `esp32_profile` | 内存/CPU 分析 | ⭐⭐ | micropython.mem_info() |

---

## 7. 常见问题

### Q1: KimiCode 不显示 MCP 工具？
- 检查 `mcp.json` 配置路径是否正确
- 确认 `python toolchain/mcp_server.py` 能独立运行不报错
- 查看 VS Code 输出面板 → KimiCode 日志

### Q2: 串口被占用？
- 确保没有其他程序（如 miniterm、picocom）占用 `/dev/ttyACM0`
- 使用 `lsof /dev/ttyACM0` 查找占用进程

### Q3: raw REPL 上传大文件失败？
- 大文件分块传输（每块 256 字节）
- 使用 `ampy` 或 `mpremote` 作为底层传输层

### Q4: 工具调用超时？
- MCP 默认超时 30 秒，烧录/大文件上传可能更长
- 在工具实现中使用异步 I/O，避免阻塞

---

## 8. 参考资源

| 资源 | 链接 |
|------|------|
| MCP 官方规范 | https://modelcontextprotocol.io |
| MCP Python SDK | `pip install mcp` |
| MicroPython REPL 文档 | https://docs.micropython.org/en/latest/reference/repl.html |
| pyserial 文档 | https://pyserial.readthedocs.io/ |
| mini-claude-code | https://github.com/ShareAI-Lab/mini-claude-code |

---

> **文档版本**：v1.0  
> **最后更新**：2026-07-10  
> **配套文件**：`./mini_claude_code_notes.md`（原理理解）、`./toolchain_architecture.md`（架构设计）
