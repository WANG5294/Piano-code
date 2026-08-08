# ESP32 AI 原生开发工具链

本项目是为"基于 ESP32 的 AI 辅助数字钢琴与 AI 原生开发工具链"作业实现的工具链部分。

工具链以 **MCP（Model Context Protocol）服务器**形式实现，支持新版 Kimi Code CLI（命令名为 `kimi`）直接操控 ESP32 硬件。

> **注意：旧版 CLI 命令名为 `kimi-cli`，是残留版本，已不再使用。请使用新版 `kimi`。**
>
> 新版 Kimi Code CLI 的 MCP 配置与旧版不同：旧版使用 `~/.kimi/mcp.json` 和 `kimi mcp add` 命令；新版使用 `~/.kimi-code/mcp.json` 或项目级 `.kimi-code/mcp.json`，并通过 TUI 命令 `/mcp-config` 交互式管理。

---

## 功能清单

| 能力 | 工具名 | 实现模块 | 说明 |
|------|--------|----------|------|
| 连接管理 | `connect_esp32` / `disconnect_esp32` | `tools/connection.py` | 连接/断开 ESP32 串口 |
| 文件传输 | `upload_file` / `list_files` / `remove_file` | `tools/file_transfer.py` | 上传、列出、删除 ESP32 文件 |
| 程序执行 | `execute_program` / `execute_repl` | `tools/executor.py` | 运行文件或单条 REPL 命令 |
| 微控制器复位 | `reset_esp32` | `tools/executor.py` | 软复位或硬复位 ESP32 |
| 固件烧录 | `flash_firmware` | `tools/executor.py` | 通过 esptool 烧录 MicroPython 固件 |
| 串口监控 | `read_serial_output` | `tools/serial_monitor.py` | 读取实时串口输出 |
| 运行日志检索 | `get_logs` | `tools/serial_monitor.py` | 获取最近串口日志 |
| 错误报告 | `report_error` | `tools/error_handler.py` | 解析 MicroPython Traceback |

---

## 安装依赖

```sh
cd toolchain

python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate

pip install -r requirements.txt
```

---

## 注册 MCP 到新版 Kimi Code CLI

确保你使用的是新版 Kimi Code CLI，命令名为 `kimi`。旧版 `kimi-cli` 是残留版本，请忽略。

### 配置文件位置

新版 Kimi Code CLI 从以下位置读取 MCP 配置：

- **用户级**：`~/.kimi-code/mcp.json`（或 `$KIMI_CODE_HOME/mcp.json`）
- **项目级**：工作目录下的 `.kimi-code/mcp.json`

项目级配置会覆盖用户级同名服务器。本项目已在根目录创建 `.kimi-code/mcp.json`。

### 方式一：使用 TUI 交互式配置（推荐）

在项目根目录启动 Kimi：

```sh
kimi
```

进入 TUI 后输入：

```
/mcp-config
```

按提示添加 stdio 类型的 MCP 服务器：

- **Name**: `esp32-mcp`
- **Command**: `C:/Users/pc/Desktop/课程作业/数科大作业26暑假/toolchain/venv/Scripts/python.exe`
- **Args**: `C:/Users/pc/Desktop/课程作业/数科大作业26暑假/toolchain/mcp_server.py`

保存后退出，配置会自动写入 `~/.kimi-code/mcp.json`。

### 方式二：手动编辑配置文件

编辑 `~/.kimi-code/mcp.json` 或项目级 `.kimi-code/mcp.json`，添加以下内容：

```json
{
  "mcpServers": {
    "esp32-mcp": {
      "command": "C:/Users/pc/Desktop/课程作业/数科大作业26暑假/toolchain/venv/Scripts/python.exe",
      "args": [
        "C:/Users/pc/Desktop/课程作业/数科大作业26暑假/toolchain/mcp_server.py"
      ],
      "cwd": "C:/Users/pc/Desktop/课程作业/数科大作业26暑假/toolchain",
      "enabled": true
    }
  }
}
```

> 请根据你的实际路径修改 `python.exe`、`mcp_server.py` 和 `cwd` 的路径。推荐指向虚拟环境中的 Python，以避免依赖问题。

### 验证注册

在 Kimi TUI 中输入：

```
/mcp
```

如果看到 `esp32-mcp` 状态为已连接，并列出以下工具，说明注册成功：

- `connect_esp32`
- `disconnect_esp32`
- `upload_file`
- `list_files`
- `remove_file`
- `execute_program`
- `execute_repl`
- `reset_esp32`
- `flash_firmware`
- `read_serial_output`
- `get_logs`
- `report_error`

---

## 固件烧录

如果 ESP32 上还没有 MicroPython，需要先烧录固件：

1. 从 [MicroPython 下载页](https://micropython.org/download/ESP32_GENERIC/) 下载对应型号的 `.bin` 固件；
2. 使用 esptool 烧录（先擦除再写入）：

```sh
cd toolchain
venv\Scripts\activate
python -m esptool --chip esp32 --port COM5 erase_flash
python -m esptool --chip esp32 --port COM5 --baud 460800 write_flash -z 0x1000 path/to/ESP32_GENERIC-xxxxxxxx.bin
```

3. 或在 Kimi TUI 中直接说：

> "连接 ESP32 到 COM5，然后把 path/to/ESP32_GENERIC-xxxxxxxx.bin 烧录到 ESP32。"

Kimi 会自动调用 `flash_firmware(...)`。

> **注意**：烧录固件时工具链会自动断开当前串口连接，烧录完成后再尝试重连。

---

## 使用示例

在 Kimi Code CLI 中，你可以直接说：

> "连接 ESP32 到 COM5，先确认已烧录 MicroPython 固件，然后把 firmware 下的所有文件上传到 ESP32，运行 main.py，并监控串口输出。"

Kimi 会自动调用：

1. `connect_esp32("COM5")`
2. `upload_file("firmware/hardware_config.py", "hardware_config.py")`
3. `upload_file("firmware/buzzer.py", "buzzer.py")`
4. `upload_file("firmware/buttons.py", "buttons.py")`
5. `upload_file("firmware/leds.py", "leds.py")`
6. `upload_file("firmware/piano.py", "piano.py")`
7. `upload_file("firmware/main.py", "main.py")`
8. `execute_program("main.py")`
9. `read_serial_output()`

---

## 文件结构

```
ESP32-AI-Piano/
├── .kimi-code/
│   └── mcp.json.template    # 项目级 MCP 配置模板
├── firmware/                # 数字钢琴 MicroPython 源代码
│   ├── main.py
│   ├── buzzer.py
│   ├── buttons.py
│   ├── leds.py
│   ├── piano.py
│   └── hardware_config.py
└── toolchain/               # AI 原生开发工具链源代码
    ├── mcp_server.py        # MCP 服务器入口（接口层）
    ├── tools/               # 工具模块包（按能力划分）
    │   ├── __init__.py
    │   ├── connection.py    # 连接管理
    │   ├── file_transfer.py # 文件传输
    │   ├── executor.py      # 程序执行、复位、固件烧录
    │   ├── serial_monitor.py# 串口监控、日志检索
    │   └── error_handler.py # 错误报告
    ├── esp32_client.py      # ESP32 串口通信客户端（底层通信层）
    ├── requirements.txt
    ├── test/
    │   └── test_client.py   # 串口客户端独立测试（需真实硬件）
    └── README.md
```

---

## 注意事项

1. **区分新旧 CLI**：旧版命令是 `kimi-cli`，新版是 `kimi`。本项目只针对新版 `kimi` 配置 MCP。
2. **MCP 配置位置**：新版使用 `~/.kimi-code/mcp.json` 或 `.kimi-code/mcp.json`，不是旧版的 `~/.kimi/mcp.json`。
3. **串口权限**：Linux/Mac 用户可能需要将当前用户加入 `dialout` 组。
4. **端口名称**：Windows 下通常是 `COM3`、`COM4`、`COM5` 等；Linux 下通常是 `/dev/ttyUSB0` 或 `/dev/ttyACM0`。
5. **文件传输大小**：当前实现通过 raw REPL 写入文件，适合小文件。大文件可考虑改用 ampy 协议。
6. **串口占用**：MCP 服务器启动后会持续占用串口，其他串口工具（如 PuTTY）无法同时连接。
7. **必须先连接**：MCP 服务器不会自动连接 ESP32，请在对话中先让 Kimi 执行 `connect_esp32("COM5")`。
8. **固件烧录占口**：`flash_firmware` 需要独占串口，执行前会自动断开当前连接，执行后尝试恢复连接。
