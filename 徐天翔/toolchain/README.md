# MCPiano AI 原生开发工具链

基于 **MCP（Model Context Protocol）** 的 ESP32 MicroPython 开发工具链，让 AI 编程助手（如 KimiCode）能直接与 ESP32 硬件交互：文件传输、程序执行、复位、串口监控、日志检索、错误解析。

## 目录结构

```
toolchain/
├── mcp_server.py              # MCP 服务器主入口（stdio 传输）
└── tools/
    ├── raw_repl.py            # MicroPython raw REPL 协议层
    ├── file_transfer.py       # 文件上传/下载（base64 分块）
    ├── serial_monitor.py      # 串口监控 + 环形日志缓冲
    ├── executor.py            # 程序执行 + 复位
    └── error_handler.py       # MicroPython Traceback 解析
```

## 环境要求

- Python 3.9+（工具链侧）
- `pyserial`（串口通信）
- `mcp`（MCP 协议库）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install pyserial mcp
```

## 运行（MCP stdio 服务器）

```bash
PYTHONPATH=. python3 toolchain/mcp_server.py
```

作为 MCP 客户端（KimiCode / Claude Code 等）的 stdio 服务器配置，需同时设置 `PYTHONPATH` 环境变量指向仓库根目录。

## 提供的工具

| 工具 | 功能 |
| --- | --- |
| `esp32_upload` | 上传本地文件到 ESP32 文件系统（base64 分块，二进制安全） |
| `esp32_execute` | 执行（`run`）或停止（`stop`）MicroPython 脚本 |
| `esp32_reset` | 软复位（`machine.reset()`）或硬复位（DTR/RTS） |
| `esp32_serial` | 启动/停止/读取串口监控，返回环形缓冲快照 |
| `esp32_logs` | 检索最近 N 行日志并按关键字过滤 |
| `esp32_error` | 解析串口输出中的 MicroPython Traceback 为结构化错误 |

> 注：`esp32_download` 后端已实现（`tools/file_transfer.py`），当前版本未注册进工具列表，计划在后续版本启用。

## 测试

```bash
# MCP stdio 握手冒烟测试（无需硬件）
python3 tests/test_server.py

# 真机闭环测试（需连接 ESP32）
python3 tests/test_toolchain_w3.py
python3 tests/test_toolchain_serial.py
```

## 与 AI 编程助手集成

以 KimiCode（VS Code）为例，在 MCP 服务器配置中添加：

```json
{
  "mcpServers": {
    "mcpiano-esp32": {
      "command": "<venv>/bin/python",
      "args": ["<repo>/toolchain/mcp_server.py"],
      "env": { "PYTHONPATH": "<repo>" }
    }
  }
}
```

加载后 AI 即可通过上述 6 个工具直接操作 ESP32。详细架构设计见 `docs/toolchain_architecture.md` 与 `docs/toolchain_proposal.md`。
