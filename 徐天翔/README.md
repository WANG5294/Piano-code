# MCPiano — AI 原生嵌入式数字钢琴 & 开发工具链

> 📹 **Week 1 视频演示**: [Bilibili - 硬件准备与工具链认识](https://b23.tv/FU8THly)
> 📹 **Week 2 视频演示**: [Bilibili - MCPiano: KimiCode + MCP 工具链开发 ESP32 数字钢琴](https://www.bilibili.com/video/BV1kCKv6HELY/)
> 📹 **Week 3 视频演示**: [Bilibili - Yuanshen 智能体架构与 A2A 协议](https://www.bilibili.com/video/BV1Ab3j6mEwA/)
> 📹 **Week 4 视频演示**: [Bilibili - AI 闭环与真实钢琴演示](https://www.bilibili.com/video/BV1Qo3X6PEoA/)
> 📹 **Week 5 视频演示**: [Bilibili - 最终演示视频 🎬](【W5链接】)
>
> 🔧 **AI-Native 工具链**: 本项目通过 MCP (Model Context Protocol) 实现 AI 自动操控 ESP32 硬件
>
> **硬件变更说明**：SSD1306 OLED 显示屏因硬件故障（I2C 无响应）已从项目中移除。当前显示方案：无。如需状态指示，使用 GPIO32/33 LED。

---

## 项目概述

本项目包含 **两个相互关联的工程任务**：

### 任务一：数字钢琴

利用 ESP32 开发板实现一台功能完整的 9 键数字钢琴：

- **按键输入**：10 个面包板按键
  - GPIO23/22/21/19/18/14/12 → do/re/mi/fa/sol/la/si（7 音阶）
  - GPIO34 → 八度+
  - GPIO35 → 八度-
  - GPIO5 → 录制/播放（短按=开始/停止录制，长按=播放）
- **音符生成**：通过 MAX98357A I2S 功放模块 + 喇叭，W4 起使用 21 个真实钢琴 WAV 采样（A3~G5）流式回放
- **视觉反馈**：7 个音调键 + 2 个八度键的 LED 由按键回路硬件直驱（3.3V → LED → 330Ω → 按键 → GND），按下即亮、释放即灭，实现零延迟硬件级声光同步
- **系统稳定性**：上电自动进入工作状态，持续稳定响应

### 任务二：AI 原生开发工具链

设计并实现一套工具链，使 AI 编程助手能直接与 ESP32 开发板交互：

| 序号 | 能力         | 描述                                 |
| ---- | ------------ | ------------------------------------ |
| 1    | 文件传输     | AI 将 MicroPython 源文件推送到 ESP32 |
| 2    | 程序执行     | AI 远程触发用户程序的运行和停止      |
| 3    | 微控制器复位 | AI 通过软件命令重启 ESP32            |
| 4    | 串口监控     | AI 实时捕获并读取 ESP32 的串口输出   |
| 5    | 运行日志检索 | AI 收集程序执行日志                  |
| 6    | 错误报告     | AI 自动检测 MicroPython 运行时异常   |

以数字钢琴为验证基准，演示 AI 通过工具链驱动嵌入式开发的 **完整闭环**（AI 发现问题 → 修改代码 → 自动部署 → 验证通过）。

---

## 项目结构

```
MCPpiano/
├── README.md                          # 项目总览
├── LICENSE                            # MIT 许可证
├── .gitignore                         # 排除规则
├── .mcp.json                          # MCP 服务器配置
│
├── samples/                           # 🎵 21个真实钢琴 WAV 采样（A3~G5）
│
├── piano/                             # 🎹 数字钢琴固件（MicroPython）
│   ├── main.py                        # 入口程序
│   ├── piano.py                       # 钢琴逻辑 + 声音控制
│   ├── buttons.py                     # 9键+2八度键扫描
│   └── i2s_audio.py                   # MAX98357A I2S 采样回放驱动
│
├── toolchain/                         # 🔧 AI-Native MCP 工具链（Python）
│   ├── README.md                      # 安装与使用说明
│   ├── mcp_server.py                  # MCP 服务器主入口
│   └── tools/                         # 工具模块
│       ├── raw_repl.py                # MicroPython raw REPL 协议
│       ├── file_transfer.py           # esp32_upload / esp32_download
│       ├── serial_monitor.py          # esp32_serial / esp32_logs
│       ├── executor.py                # esp32_execute / esp32_reset
│       └── error_handler.py           # esp32_error
│
├── tests/                             # ✅ 测试脚本
│   ├── test_button.py                 # 基础按键测试
│   ├── test_buttons_9key.py           # 9键+八度键测试
│   ├── test_buzzer.py                 # ⚠️ 已废弃（PWM蜂鸣器）
│   ├── test_led.py                    # LED 测试
│   ├── test_max98357a.py              # I2S功放测试
│   ├── test_piano_v1.py               # 钢琴v1集成测试
│   ├── diag_octave_pins.py            # 八度键 GPIO 诊断脚本
│   ├── test_toolchain_serial.py       # 串口工具测试
│   ├── test_toolchain_w3.py           # 工具链闭环测试
│   └── test_server.py                 # MCP stdio 握手冒烟测试
│
├── hardware/                          # 🔩 硬件工程文档
│   ├── bom_analysis.md                # GPIO映射、BOM分析
│   ├── MCPiano_硬件资源分析.xlsx      # 可视化GPIO/BOM数据表
│   ├── pcb.pdf                        # PCB版图
│   └── schematic.pdf                  # 原理图
│
├── docs/                              # 📚 技术文档
│   ├── 最新25级实验班暑假大作业要求.pdf
│   ├── mini_claude_code_notes.md      # Mini Claude Code源码分析
│   ├── toolchain_proposal.md          # MCP服务器实现指南
│   └── toolchain_architecture.md      # 工具链架构文档
│
├── images/                            # 演示截图/视频封面
├── report/                            # 最终技术报告（W5）
│
└── 本地文件/                           # 🗂️ 本地私有资料（gitignored）
    ├── kimi.md                        # Agent AutoContext
    ├── mine.md                        # 架构图与评分矩阵
    └── *.pdf                          # 原始文档
```

---

## 开发环境

| 组件       | 要求                           |
| ---------- | ------------------------------ |
| 开发语言   | MicroPython + Python（工具链） |
| 目标硬件   | ESP32-D0WD-V3 开发板           |
| 代码编辑器 | 不限（推荐 VS Code）           |
| 烧录工具   | esptool.py + MicroPython 固件  |
| 串口工具   | 调试输出和 REPL 交互           |
| 版本控制   | Git + GitHub（公共仓库）       |

---

## 硬件配置

| 组件 | GPIO | 说明 |
|------|------|------|
| KEY do | 23 | 琴键 do |
| KEY re | 22 | 琴键 re |
| KEY mi | 21 | 琴键 mi |
| KEY fa | 19 | 琴键 fa |
| KEY sol | 18 | 琴键 sol |
| KEY la | 14 | 琴键 la |
| KEY si | 12 | 琴键 si |
| KEY 八度+ | 34 | 八度升 |
| KEY 八度- | 35 | 八度降 |
| KEY 录制/播放 | 5 | 短按开始/停止录制，长按播放 |
| LED（直驱） | - | 3.3V → LED → 330Ω → 按键 → GND，GPIO 不做输出 |
| I2S BCLK | 16 | 功放位时钟 |
| I2S LRC | 17 | 功放字时钟 |
| I2S DIN | 25 | 功放数据输入 |
| 串口 | /dev/ttyACM0 | 115200 baud |

## MCP 工具链

| 工具 | 功能 | 状态 |
|------|------|------|
| `esp32_upload` | 上传文件到 ESP32 | ✅ |
| `esp32_download` | 从 ESP32 下载文件 | ✅ |
| `esp32_execute` | 执行/停止程序 | ✅ |
| `esp32_reset` | 软/硬复位 | ✅ |
| `esp32_serial` | 串口监控 | ✅ |
| `esp32_logs` | 日志检索 | ✅ |
| `esp32_error` | 错误解析 | ✅ |

---

## 快速开始

### 环境准备

```bash
# 克隆仓库
git clone https://github.com/ChuOZhen/MCPiano.git
cd MCPiano

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install esptool pyserial mpremote mcp
```

### 烧录固件

```bash
esptool --chip esp32 --port /dev/ttyACM0 erase_flash
esptool --chip esp32 --port /dev/ttyACM0 --baud 460800 write_flash -z 0x1000 ESP32_GENERIC-20240602-v1.23.0.bin
```

### 运行测试

```bash
# 按键测试
mpremote connect /dev/ttyACM0 run tests/test_buttons_9key.py

# 功放测试
mpremote connect /dev/ttyACM0 run tests/test_max98357a.py

# 钢琴系统综合测试
mpremote connect /dev/ttyACM0 cp piano/i2s_audio.py :i2s_audio.py
mpremote connect /dev/ttyACM0 cp piano/buttons.py :buttons.py
mpremote connect /dev/ttyACM0 cp piano/piano.py :piano.py
mpremote connect /dev/ttyACM0 cp piano/main.py :main.py
mpremote connect /dev/ttyACM0 run tests/test_piano_v1.py

# 工具链测试
python tests/test_toolchain_w3.py
```

### 启动 MCP 服务器

```bash
python toolchain/mcp_server.py
```

### KimiCode 配置

在 VS Code KimiCode 设置中添加：
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

---

## 硬件连接

### MAX98357A I2S 功放接线

| 信号    |    ESP32 GPIO    | MAX98357A 引脚 | 说明                                                                   |
| :------ | :---------------: | :------------- | :--------------------------------------------------------------------- |
| BCLK    | **GPIO16** | BCLK           | I2S 位时钟                                                             |
| LRCK    | **GPIO17** | LRCK           | I2S 帧时钟（WS）                                                       |
| DIN     | **GPIO25** | DIN            | I2S 数据输入                                                           |
| 5V      |      5V 排针      | VIN            | 功放供电（必须 5V，不能接 3.3V）                                       |
| GND     |     GND 排针     | GND            | 与 ESP32 共地                                                          |
| GAIN    | **5V 排针** | GAIN           | **本模块接 VIN = 正常增益；接 GND 会变成高增益，导致小音量削顶** |
| SD_MODE |      5V 排针      | SD_MODE        | **必须接 VIN，不能悬空；接 GND 会关闭功放**                      |

> ⚠️ **注意模块差异**：市面上 MAX98357A 模块的 GAIN 逻辑不统一。本项目的模块**GND=高增益、VIN=正常增益**，因此 GAIN 接 VIN。如果你的模块相反，表现为音量数字越大声音越小，请把 GAIN 改接 GND。
>
> ⚠️ **SD_MODE 悬空会导致功放状态不稳定**，表现为大音量反而变小、间歇失声或底噪异常。

### 其他外设

| 外设    | GPIO | 方向 | 电平特性                |
| :------ | :--: | :--: | :---------------------- |
| KEY 八度+ |  34  | 输入 | INPUT-ONLY，需外接上拉，按下 = 低电平 |
| KEY 八度- |  35  | 输入 | INPUT-ONLY，需外接上拉，按下 = 低电平 |
| KEY 录制/播放 |  5  | 输入 | 内部上拉可用，按下 = 低电平 |
| LED |  -  | 直驱 | 3.3V → LED → 330Ω → 按键 → GND |

> ⚠️ GPIO6–11 被 SPI Flash 占用，不可用。

### 硬件接线图

W5 实拍硬件接线照片（点击查看原图）：

| 图片 | 内容 |
| --- | --- |
| [📷 查看接线大图](images/wiring/1.jpg) | 面包板按键 + LED 硬件直驱接线（10 键）与 MAX98357A 功放接线 |

---

## 音频升级说明

Week 2 将音频输出从 **PWM 蜂鸣器** 升级为 **MAX98357A I2S 功放 + 喇叭**。

| 对比项   | PWM 蜂鸣器     | MAX98357A I2S 功放       |
| :------- | :------------- | :----------------------- |
| 信号类型 | 方波           | 16-bit PCM 正弦波        |
| 音质     | 谐波丰富、刺耳 | 平滑、音准干净           |
| 驱动方式 | GPIO25 PWM     | I2S 总线（GPIO16/17/25） |
| 外设     | 压电蜂鸣器     | 小喇叭                   |
| 扩展性   | 仅单音         | 支持复杂波形、多采样率   |

**为什么升级？**

- 方波含有大量高次谐波，听感尖锐；正弦波基频纯净，更适合音乐演示。
- I2S 是数字音频标准接口，为后续旋律、采样播放预留空间。
- MAX98357A 内置 D 类功放，可直接驱动喇叭，无需额外驱动电路。

---

## AI 编程助手选型

| 选项                    | 说明                    | 工具链实现建议         |
| ----------------------- | ----------------------- | ---------------------- |
| Claude Code             | 功能成熟，支持 MCP 扩展 | 实现 MCP 服务器        |
| Codex                   | OpenAI 生态             | 编写 Codex 兼容插件    |
| Zcode                   | 开源环境                | 编写 Zcode 扩展        |
| OpenCode + DeepSeek API | 开源 + 低成本           | 编写 OpenCode 工具扩展 |

---

## 开发进度

### Week 1 (7/6–7/12): 硬件入门 ✅
- [x] 原理图分析 → `hardware/bom_analysis.md`
- [x] MicroPython 固件烧录
- [x] 外设测试：按键、LED、蜂鸣器
- [x] 工具链方案选型：MCP 服务器
- [x] 交付：Bilibili W1 视频 → https://b23.tv/FU8THly

### Week 2 (7/13–7/19): 钢琴核心 + 工具链架构 ✅
- [x] 数字钢琴 v1 固件：9键 + I2S功放 + 八度切换
  - [x] `piano/buttons.py` — 按键扫描 + 软件去抖
  - [x] `piano/i2s_audio.py` — MAX98357A I2S 驱动
  - [x] `piano/piano.py` — 钢琴逻辑 + LED 反馈
  - [x] `piano/main.py` — 入口程序
- [x] MCP 工具链完整实现（6个工具）
  - [x] `esp32_upload` — 文件上传
  - [x] `esp32_download` — 文件下载
  - [x] `esp32_execute` — 程序执行/停止
  - [x] `esp32_reset` — 软/硬复位
  - [x] `esp32_serial` — 串口监控
  - [x] `esp32_logs` — 日志检索
  - [x] `esp32_error` — 错误解析
- [x] 工具链闭环测试：`tests/test_toolchain_w3.py` ✅ 通过
- [x] KimiCode MCP 集成验证：`mcpiano-esp32 · 6 tools connected`
- [x] 交付：Bilibili W2 视频 → https://www.bilibili.com/video/BV1kCKv6HELY/

### Week 3 (7/20–7/26): LED 声光同步 + 录音回放扩展 ✅
- [x] 7 音调键 + 2 八度键 LED 改为硬件直驱：3.3V → LED → 330Ω → 按键 → GND
- [x] GPIO 只做输入检测，不驱动 LED，消除软件输出延迟
- [x] 声光严格同步：按下瞬间灯亮+发声，释放瞬间灯灭+静音
- [x] 删除 `piano/leds.py`，简化 `piano/piano.py`
- [x] I2S 预初始化 + 5ms 主循环保持
- [x] 多键支持：同时按住多键，喇叭播放最后按下音
- [x] 新增 GPIO5 录制/播放键：短按开始/停止录制，长按播放
- [x] `piano/piano.py` 实现录制/回放状态机，记录音符事件并按时间重放
- [x] 交付：Bilibili W3 视频 → https://www.bilibili.com/video/BV1Ab3j6mEwA/

### Week 4 (7/27–8/2): AI 闭环验证 + 真实钢琴声音 ✅

- [x] AI 闭环演示：KimiCode 自动生成 → 上传 → 执行 → 监控 → 纠错 → 验证
- [x] Bug 场景设计与自修复验证
- [x] **真实钢琴采样回放**：
  - 21 个 WAV 采样（A3~G5，7音 × 3八度）
  - 流式播放，512B 分块，低内存占用，0.75s 截断避免拖尾
  - `piano/i2s_audio.py`：跳过 WAV 头，直接驱动 I2S
  - 音符映射：do=C, re=D, mi=E, fa=F, sol=G, la=A, si=B
- [x] 三八度完整覆盖：低八度(C3) / 中音(C4) / 高八度(C5)
- [x] 八度 toggle + GPIO32/33 LED 指示：绿灯=高八度，红灯=低八度
- [x] 录制/回放移植到采样版：GPIO5 短按录制/长按播放，录音回放真实钢琴音色
- [x] 真实钢琴声音 + 录制/回放 + 八度切换 + LED 声光指示全功能整合
- [x] **小组项目：Yuanshen 闭环自动化 Agent**（[github.com/WANG5294/Yuanshen](https://github.com/WANG5294/Yuanshen)）
  - 面向 ESP32 MicroPython 开发的闭环自动化 Agent v1.2.3，自然语言 → 需求规范化 → 接线确认 → 代码编写 → 固件烧录 → 实机测试 → 结果汇报
  - 核心规模 ~4369 行 Python（入口 + 11 模块包 + MCP 服务器 + A2A 服务）
  - 关键技术：token 级流式生成器（`llm_create_stream()`）、工具调用零浪费、thinking 块回传
  - 现代化终端 UI（Rich）：ASCII 启动页/确认页/进度条/轮次卡片/报告模板
  - 生态能力：A2A 协议远程任务下发、多模型切换（DeepSeek + Kimi）、经验自动沉淀为 Skill
  - 已发布 npm 包 `yuanshen-esp32-agent`，GitHub main 同步（cbd9bc7）
- [x] 交付：Bilibili W4 视频（AI 闭环 + 真实钢琴演示） → https://www.bilibili.com/video/BV1Qo3X6PEoA/

### Week 5 (8/3–8/9): 完善与交付 ✅
- [x] 扩展功能：八度切换（低/中/高三档）+ 旋律录制/回放（GPIO5 短按录制、长按播放）+ LED 声光直驱
- [x] 技术报告 15-20 页 → `report/技术报告.pdf`（正文 17 页，A4/宋体小四/1.5 倍行距）
- [x] GitHub 整理：LICENSE、toolchain/README、images/、tests 测试归位、报告入库
- [x] 交付：Bilibili W5 视频（链接发布后补充） + 技术报告 PDF（`report/技术报告.pdf`）

---

## 教学目标

1. **硬件文档解读能力** — 阅读原理图、PCB 版图、BOM
2. **嵌入式软件设计能力** — 模块化系统架构
3. **AI 协作开发能力** — 高效使用 AI 编程助手
4. **开发者工具与基础设施设计能力** — MCP / 插件扩展机制
5. **系统调试与问题解决能力** — 结构化调试方法
6. **技术沟通与工程文档能力**
7. **持续学习与批判性思维**

---

## 学术诚信

- 工程师负最终责任，每一行代码都必须被完全理解
- 硬件验证是唯一标准，AI 生成的代码必须在实际硬件上验证通过
- 如实记录 AI 贡献与不足
- 禁止抄袭、禁止伪造闭环验证演示

---

*项目进行中，逐步更新……*
