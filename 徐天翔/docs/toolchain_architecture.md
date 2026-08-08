# MCPiano 工具链架构设计

## 1. 总体架构

```
┌─────────────────────────────────────────────────────────┐
│                    VS Code + KimiCode                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   对话界面   │  │  LLM 引擎   │  │  工具调度器  │    │
│  │  (Chat UI)  │  │ (Kimi API)  │  │(Tool Router)│   │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘    │
│         │                │                │           │
│         └────────────────┴────────────────┘           │
│                        │                               │
│              ┌─────────┴─────────┐                     │
│              ▼                   ▼                     │
│  ┌──────────────────┐  ┌──────────────────┐          │
│  │   内置工具        │  │   MCP 服务器      │          │
│  │ (文件读写/终端)   │  │ (自定义硬件工具)  │          │
│  └──────────────────┘  └──────────────────┘          │
└─────────────────────────────────────────────────────────┘
                              │
                              │ stdio (JSON-RPC 2.0)
                              ▼
              ┌───────────────────────────────┐
              │      MCPiano MCP Server        │
              │  (Python 3.10+ 独立进程)       │
              │                                │
              │  ┌──────────┐ ┌──────────┐   │
              │  │esp32_    │ │esp32_    │   │
              │  │ upload   │ │ execute  │   │
              │  └──────────┘ └──────────┘   │
              │  ┌──────────┐ ┌──────────┐   │
              │  │esp32_    │ │esp32_    │   │
              │  │ serial   │ │ error    │   │
              │  └──────────┘ └──────────┘   │
              │  ┌──────────┐ ┌──────────┐   │
              │  │esp32_    │ │esp32_    │   │
              │  │ reset    │ │ logs     │   │
              │  └──────────┘ └──────────┘   │
              └──────────┬────────────────────┘
                         │ pyserial
                         ▼
              ┌───────────────────────────────┐
              │     ESP32-D0WD-V3 开发板       │
              │     (MicroPython REPL)         │
              └───────────────────────────────┘
```

## 2. 工具定义

| # | 工具名 | 功能 | 输入参数 | 返回值 | 错误处理 |
|:--|:------|:-----|:---------|:-------|:---------|
| 1 | `esp32_upload` | 文件传输 | `local_path`, `remote_path` | `{"success", "message"}` | 串口超时、文件不存在 |
| 2 | `esp32_execute` | 程序执行 | `entry_file`, `action` | `{"success"}` | 文件未找到、执行超时 |
| 3 | `esp32_reset` | 微控制器复位 | `mode` ("soft"/"hard") | `{"success"}` | 串口未连接 |
| 4 | `esp32_serial` | 串口监控 | `action`, `duration` | `{"lines"}` | 串口占用、波特率错误 |
| 5 | `esp32_logs` | 日志检索 | `lines`, `filter` | `{"logs"}` | 缓冲区为空 |
| 6 | `esp32_error` | 错误报告 | `auto_parse` | `{"error"}` | 无错误可解析 |

## 3. 通信协议

**选择：MicroPython raw REPL 协议**

理由：
- 比 ampy 更底层，控制更精确。
- 不需要额外安装 ampy 工具。
- 直接通过 pyserial 发送 Ctrl+A (`0x01`) 进入 raw REPL，Ctrl+D (`0x04`) 执行代码。
- 文件传输通过 exec 写入文件系统。

## 4. 串口监听策略

**选择：asyncio + 独立线程**

理由：
- 串口监听需要持续后台运行，不能阻塞主线程。
- asyncio 适合处理多个并发 I/O 操作。
- 环形缓冲区（`deque(maxlen=1000)`）保存最近输出，防止内存溢出。

## 5. 错误解析策略

**Traceback 正则匹配**：

```python
pattern = (
    r'Traceback \(most recent call last\):\n'
    r'.*\n  File "(.+)", line (\d+).*?\n'
    r'    .+?\n(\w+Error): (.+)'
)
```

提取：文件名、行号、异常类型、异常消息。

## 6. 与 KimiCode 集成

在 KimiCode 的 `mcp.json` 中添加：

```json
{
  "mcpServers": {
    "mcpiano-esp32": {
      "command": "/home/chuzhen/MCPpiano/.venv/bin/python",
      "args": ["/home/chuzhen/MCPpiano/toolchain/mcp_server.py"],
      "env": {"PYTHONPATH": "/home/chuzhen/MCPpiano/toolchain"}
    }
  }
}
```
