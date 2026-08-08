# ESP32 AI Piano — 工具链

基于 MCP (Model Context Protocol) 的 ESP32 开发工具链，连接 AI 模型与物理硬件。

**状态**: 6/6 工具全部实现 ✅ | 架构: 后台持续采集 + 按需查询

## 快速开始

### 安装依赖

```bash
pip install pyserial mcp
```

### 启动 MCP Server

```bash
cd toolchain
python mcp_server.py
```

启动后自动连接 COM3 并启动后台采集线程，日志输出到 stderr。
MCP Server 注册了全部 6 个工具，Claude Code 连接后即可调用。

### 单独测试工具（不通过 AI）

每个工具都有独立测试入口，可直接运行：

```bash
cd toolchain

# 串口监控（交互式，按琴键后回车查看结果）
python -m tools.serial_monitor 15

# 文件上传
python tools/file_transfer.py <本地文件> <远程路径>

# 设备复位
python tools/reset_device.py soft

# 日志检索
python tools/fetch_logs.py 演奏        # 只看按键记录
python tools/fetch_logs.py 演奏 30 10  # 最近30秒，最多10条

# 程序执行
python tools/execute_program.py code "print('hello')"
python tools/execute_program.py module piano

# 错误检测
python tools/report_error.py 50
```

### 运行测试脚本

```bash
cd toolchain

# 所有测试脚本在 test/ 目录下
python test/test_pause_resume.py     # 暂停/恢复机制验证
python test/test_reset_device.py     # 软/硬复位验证
python test/test_fetch_logs.py       # 日志检索验证
python test/test_execute_program.py  # 程序执行验证
python test/test_report_error.py     # 错误检测验证
```

### 配置 Claude Code 连接

配置文件 `.mcp.json` 已放置在项目根目录，内容如下：

```json
{
  "mcpServers": {
    "esp32-piano": {
      "type": "stdio",
      "command": "python",
      "args": ["toolchain/mcp_server.py"],
      "cwd": "C:\\Users\\notch\\Desktop\\ESP32-AI-Piano"
    }
  }
}
```

Claude Code 启动时会自动加载项目根目录的 `.mcp.json`，无需手动配置。
配完后**重启 Claude Code**（或在对话中输入 `/mcp` 查看已连接服务器列表），即可使用全部 6 个 MCP 工具。

## 目录结构

```
toolchain/
├── ARCHITECTURE.md           # 架构设计文档（设计决策、接口定义）
├── README.md                 # 本文件（安装与使用说明）
├── live_monitor.py           # 实时监控演示脚本（tail -f 风格）
├── mcp_server.py             # MCP 服务器入口（6个工具全部注册）
├── serial_connection.py      # 串口连接管理单例 + 后台采集 + 缓冲区
├── test/                     # 测试脚本
│   ├── __init__.py
│   ├── test_pause_resume.py      # 暂停/恢复 + 软复位流程
│   ├── test_reset_device.py      # soft/hard 双模式复位
│   ├── test_fetch_logs.py        # 关键字+时间过滤
│   ├── test_execute_program.py   # code/module 执行+超时
│   └── test_report_error.py      # 异常解析+诊断
└── tools/                    # 工具实现（6项基本能力）
    ├── __init__.py
    ├── _raw_repl.py              # [内部] raw REPL 协议共享模块
    ├── serial_monitor.py         # 串口监控（后台缓存查询）
    ├── file_transfer.py          # 文件上传（raw REPL + base64 分块）
    ├── reset_device.py           # 微控制器复位（soft/hard 双模式）
    ├── execute_program.py        # 程序执行（code/module + 超时中断）
    ├── fetch_logs.py             # 日志检索（关键字+时间范围）
    └── report_error.py           # 错误报告（异常检测+诊断）
```

## 已注册的 MCP 工具

| 工具名 | 功能 | 输入参数 |
|--------|------|----------|
| `serial_monitor` | 查询后台缓存的串口输出 | `duration_sec` (float) |
| `file_transfer` | 上传文件到 ESP32 | `local_path` (str), `remote_path` (str), `timeout_sec` (float) |
| `reset_device` | 复位 ESP32（soft/hard） | `mode` (str: "soft"/"hard"), `wait_ready_sec` (float) |
| `fetch_logs` | 关键字+时间检索日志 | `keyword` (str), `since_sec` (float), `max_lines` (int) |
| `execute_program` | 执行代码或启动模块 | `module` (str), `code` (str), `timeout_sec` (float) |
| `report_error` | 检测异常生成诊断报告 | `context_lines` (int) |

## 已知限制

| 限制 | 说明 |
|------|------|
| **端口硬编码** | 串口参数（COM3/115200）目前硬编码 |
| **Windows 专属** | COM3 是 Windows 串口命名，Linux/macOS 为 `/dev/ttyUSB0` |
| **单串口** | 工具链运行时独占 COM3，不能同时使用 Thonny/mpremote |
| **无日志持久化** | 缓存仅在内存中（deque, 1000 行），不落盘 |

## 错误处理设计

本工具链遵循"永不崩溃"原则：所有底层异常都被捕获并转换为结构化错误信息返回给 AI。详见 [ARCHITECTURE.md](ARCHITECTURE.md) 第四节。
