# ESP32 AI 辅助数字钢琴与 AI 原生开发工具链

[![MicroPython](https://img.shields.io/badge/MicroPython-1.22.1-blue.svg)](https://micropython.org/)
[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Kimi Code CLI](https://img.shields.io/badge/Kimi%20Code%20CLI-0.23+-green.svg)](https://www.kimi.com/code)

本项目是 2026 年暑假大作业：**基于 ESP32 的 AI 辅助数字钢琴与 AI 原生开发工具链**。

项目包含两个相互关联的任务：

1. **数字钢琴**：使用 ESP32-D0WD-V3 开发板实现按键输入 → 音符发声 → LED 反馈的完整数字钢琴。
2. **AI 原生开发工具链**：以 MCP（Model Context Protocol）服务器形式实现，让 Kimi Code CLI 等 AI 编程助手能够直接操控 ESP32，完成代码上传、程序执行、串口监控、错误报告等闭环操作。

---

## 目录结构

```
ESP32-AI-Piano/
├── README.md                    # 本文件
├── LICENSE                      # MIT 许可证
├── .gitignore                   # Git 忽略配置
├── .kimi-code/                  # Kimi Code CLI 项目级 MCP 配置
│   └── mcp.json.template        # MCP 配置模板
├── firmware/                    # 数字钢琴 MicroPython 固件
│   ├── main.py                  # 程序入口
│   ├── piano.py                 # 钢琴核心逻辑
│   ├── buttons.py               # 按键驱动
│   ├── leds.py                  # LED 驱动
│   ├── buzzer.py                # 蜂鸣器 PWM 驱动
│   └── hardware_config.py       # GPIO 与外设配置
├── toolchain/                   # AI 原生开发工具链
│   ├── mcp_server.py            # MCP 服务器入口（接口层）
│   ├── tools/                   # 工具模块包（按能力划分）
│   │   ├── connection.py        # 连接管理
│   │   ├── file_transfer.py     # 文件传输
│   │   ├── executor.py          # 程序执行、复位、固件烧录
│   │   ├── serial_monitor.py    # 串口监控、日志检索
│   │   └── error_handler.py     # 错误报告
│   ├── esp32_client.py          # ESP32 串口通信客户端（底层通信层）
│   ├── test/
│   │   └── test_client.py       # 串口客户端独立测试
│   ├── requirements.txt         # Python 依赖
│   └── README.md                # 工具链使用说明
├── hardware/                    # 硬件工程文档
│   ├── schematic.pdf            # 原理图
│   ├── pcb.pdf                  # PCB 版图
│   ├── bom_analysis.md          # 工程物料清单分析
│   ├── hardware_mapping.txt     # GPIO 映射表（以本表为准）
│   └── 最新25级实验班暑假大作业要求.pdf
├── docs/                        # 补充技术文档
│   └── reference/               # PDF 文本化备份
├── tests/                       # 外设测试程序
│   ├── button_test.py
│   ├── button_test_9.py
│   ├── button_test_focused.py
│   └── pin_monitor.py
├── images/                      # 图片资源
└── report/                      # 最终报告源文件
    ├── toolchain_architecture.md  # 工具链详细架构设计文档
    ├── toolchain_interface_spec.md# 工具链接口定义文档
    └── toolchain_report.md
```

---

## 硬件平台

- **微控制器**：ESP32-D0WD-V3
- **USB 转串口**：CP2102N
- **蜂鸣器**：MLT-5020（GPIO25，PWM 驱动）
- **LED**：LED2 绿色（GPIO32）、LED3 红色（GPIO33），低电平点亮
- **按键**：
  - BOOT 键 → GPIO0
  - 数字钢琴 9 键（do/re/mi/fa/sol/la/si/低八度/高八度）→ GPIO5/12/14/18/19/21/22/35/34
  - 原板载 KEY1/KEY2 已废弃，不再使用
- **扩展外设**：MPU6050（GPIO16/GPIO17，I2C）

> **注意**：所有 GPIO 编号以 `hardware/hardware_mapping.txt` 为最终依据。

---

## 快速开始

### 1. 安装工具链依赖

```sh
cd toolchain

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Linux/Mac

pip install -r requirements.txt
```

### 2. 配置 Kimi Code CLI 的 MCP

新版 Kimi Code CLI 使用项目级 `.kimi-code/mcp.json` 或用户级 `~/.kimi-code/mcp.json`。

复制模板并修改路径：

```sh
cp .kimi-code/mcp.json.template .kimi-code/mcp.json
```

把 `<your-venv-python-or-python>` 和路径替换为你本机的实际路径，例如：

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

启动 Kimi 后在 TUI 中输入 `/mcp` 验证是否加载了 `esp32-mcp` 和全部工具。

详细说明见 [`toolchain/README.md`](toolchain/README.md)。

### 3. 烧录 MicroPython 固件（首次使用）

如果你的 ESP32 还没有 MicroPython，需要先下载并烧录固件：

1. 从 [MicroPython ESP32 下载页](https://micropython.org/download/ESP32_GENERIC/) 下载对应型号的 `.bin` 固件；
2. 使用 esptool 烧录（先擦除再写入）：

```sh
cd toolchain
venv\Scripts\activate
python -m esptool --chip esp32 --port COM5 erase_flash
python -m esptool --chip esp32 --port COM5 --baud 460800 write_flash -z 0x1000 path/to/ESP32_GENERIC-xxxxxxxx.bin
```

> 烧录完成后，ESP32 会自动复位并进入 MicroPython REPL。

### 4. 上传数字钢琴固件

在 Kimi TUI 中说：

> "连接 ESP32 到 COM5，把 firmware 下的所有 MicroPython 文件上传到 ESP32，然后运行 main.py。"

### 5. 运行数字钢琴

上传完成后，ESP32 上电会自动运行 `main.py`。按下 do/re/mi/fa/sol/la/si 音符键即可演奏。

---

## AI 闭环演示

在 Kimi TUI 中，可以直接用自然语言完成完整闭环：

> "连接 ESP32 到 COM5，上传 firmware/main.py 到 ESP32，运行它，并监控串口输出。如果报错了，读取错误信息并修复。"

Kimi 会自动调用：

1. `connect_esp32("COM5")`
2. `upload_file(...)`
3. `execute_program("main.py")`
4. `read_serial_output()`
5. 若出错，自动调用 `report_error()` 并修复代码

---

## 开发工具

| 工具 | 用途 |
|------|------|
| [Kimi Code CLI](https://www.kimi.com/code) | AI 编程助手，通过 MCP 操控 ESP32 |
| [MicroPython](https://micropython.org/) | ESP32 固件开发语言 |
| [Pymakr](https://marketplace.visualstudio.com/items?itemName=pycom.Pymakr) | VS Code 插件，用于手动上传和 REPL 调试 |
| [pyserial](https://pyserial.readthedocs.io/) | Python 串口通信库 |
| [esptool](https://docs.espressif.com/projects/esptool/) | ESP32 固件烧录工具 |

---

## 许可证

MIT License
