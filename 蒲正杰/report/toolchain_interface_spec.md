# ESP32 AI 原生开发工具链 — 工具接口定义文档

> 本文档是第二周任务"确定各工具的接口定义"的产出，与 `toolchain_architecture.md`（详细架构设计）配套。
> 文档定义 AI 可见的 12 个 MCP 工具的**输入参数、输出格式、错误语义**，以及底层数据协议格式。
> 所有示例均为 **2026-07-17 在真实硬件（COM5，ESP32-D0WD-V3，MicroPython v1.22.1）上的实测返回**，非虚构样例。

---

## 〇、工具总览

| # | 工具名 | 能力域 | 实现模块 | 返回值类型 |
|---|--------|--------|---------|-----------|
| 1 | `connect_esp32` | 连接管理 | `tools/connection.py` | 确认字符串 |
| 2 | `disconnect_esp32` | 连接管理 | `tools/connection.py` | 确认字符串 |
| 3 | `upload_file` | 文件传输 | `tools/file_transfer.py` | 确认字符串 |
| 4 | `list_files` | 文件传输 | `tools/file_transfer.py` | JSON 字符串 |
| 5 | `remove_file` | 文件传输 | `tools/file_transfer.py` | 确认字符串 |
| 6 | `execute_program` | 程序执行 | `tools/executor.py` | stdout 文本 |
| 7 | `execute_repl` | 程序执行 | `tools/executor.py` | REPL 输出文本 |
| 8 | `reset_esp32` | 复位 | `tools/executor.py` | 确认字符串 |
| 9 | `flash_firmware` | 固件烧录 | `tools/executor.py` | esptool 输出文本 |
| 10 | `read_serial_output` | 串口监控 | `tools/serial_monitor.py` | 串口输出文本 |
| 11 | `get_logs` | 日志检索 | `tools/serial_monitor.py` | 多行文本 |
| 12 | `report_error` | 错误报告 | `tools/error_handler.py` | **结构化错误 JSON（协议见第七章）** |

---

## 一、接口总体约定

### 1.1 调用通道

- AI 客户端（Kimi Code CLI）通过 **MCP 协议 / stdio（JSON-RPC 2.0）** 调用工具：请求为"工具名 + JSON 参数对象"，响应为 MCP 文本内容（`TextContent`）。
- 工具的参数 Schema 由 FastMCP 依据 Python 类型注解自动生成；工具描述取自函数 docstring。因此**类型注解与 docstring 即接口契约的一部分**，修改函数签名即修改接口。

### 1.2 返回值约定

| 返回类别 | 约定 | 适用工具 |
|---------|------|---------|
| 确认字符串 | 固定格式的中文短句，描述操作结果 | `connect_esp32`、`disconnect_esp32`、`upload_file`、`remove_file`、`reset_esp32` |
| 输出文本 | 设备侧产生的原始/净输出文本（程序 stdout、REPL 输出、串口日志、esptool 输出） | `execute_program`、`execute_repl`、`read_serial_output`、`get_logs`、`flash_firmware` |
| JSON 字符串 | `json.dumps(obj, ensure_ascii=False, indent=2)`，供 AI 精确解析字段 | `list_files`、`report_error` |

### 1.3 错误语义（两级错误通道）

1. **工具执行失败**（本地侧问题：串口未连接、本地文件不存在、esptool 退出码非零等）：底层抛出 Python 异常，FastMCP 捕获后以 MCP 工具调用错误返回，AI 可感知失败并重试或调整方案。**不会静默吞错**。
2. **设备侧运行错误**（ESP32 上程序抛出 Traceback）：不算工具失败，工具正常返回；AI 通过 `read_serial_output` / `get_logs` 观察输出，或调用 `report_error` 获取结构化错误（见第七章协议）。

### 1.4 通用参数约定

| 参数 | 类型 | 含义 |
|------|------|------|
| `port` | `str` | 串口名。Windows：`"COM3"`/`"COM5"`；Linux/Mac：`"/dev/ttyUSB0"`、`"/dev/ttyACM0"` |
| `timeout` | `float`（秒） | 单次 REPL 执行的等待上限，默认 5.0。超时返回已收到的部分内容 |
| 路径 | `str` | 本地路径支持相对/绝对；ESP32 远端路径为 MicroPython 文件系统路径（根为 `/`，文件名不含目录时存于根目录） |
| 编码 | — | 全部文本按 UTF-8 处理；串口解码容错 `errors="replace"` |

### 1.5 会话模型

- 进程内全局单例 `ESP32Client`，所有工具共享**同一条串口连接**。
- 工具调用存在顺序依赖：`connect_esp32` 是会话起点，其余工具（除 `flash_firmware` 可自带 `port` 外）要求在已连接状态下调用，否则抛出"ESP32 未连接"异常。
- MCP 服务器由 AI 客户端按需拉起，生命周期与客户端会话一致；客户端退出时连接随之释放。

---

## 二、连接管理接口

### 2.1 `connect_esp32(port: str) -> str`

连接 ESP32 串口并启动后台监听线程。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `port` | `str` | 是 | — | 串口名，如 `"COM5"` |

- **成功返回**：`已连接到 ESP32：<port> @ 115200 baud`
- **失败**：串口被占用/不存在 → 抛出 `serial.SerialException`（MCP 错误）；未传 port → `ValueError`
- **副作用**：占用串口（独占）；启动后台监听线程开始缓存串口输出
- **实测示例**（2026-07-17, COM5）：

```
已连接到 ESP32：COM5 @ 115200 baud
```

### 2.2 `disconnect_esp32() -> str`

停止监听线程并关闭串口，释放独占。

- **返回**：`已断开与 ESP32 的连接`

---

## 三、文件传输接口（输入输出格式）

### 3.1 `upload_file(local_path: str, remote_path: str = "") -> str`

将本地文件上传到 ESP32 文件系统。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `local_path` | `str` | 是 | — | 本地文件路径（UTF-8 文本） |
| `remote_path` | `str` | 否 | `""` | ESP32 目标路径；留空取本地文件名 |

- **输入格式约束**：文件须为 UTF-8 文本（MicroPython 源码）；内容经转义后通过 raw REPL 单条语句写入，**适合 KB 级小文件**。
- **成功返回格式**：`文件上传成功：<local_path> -> <remote>`
- **失败**：本地文件不存在 → `FileNotFoundError: 本地文件不存在：<local_path>`
- **实测示例**：

```
文件上传成功：_itc_demo.py -> _itc_demo.py
```

- **底层写入协议**（raw REPL 执行的单条语句）：

```python
with open("<remote>", "w") as f: f.write("<escaped_content>")
```

转义规则（按序执行）：

| 原字符 | 转义后 | 目的 |
|--------|--------|------|
| `\` | `\\` | 防止反斜杠被解释 |
| `"` | `\"` | 防止字符串提前闭合 |
| 换行 `\n` | 字面 `\n` 两字符 | 单条语句内表示多行内容 |

ESP32 端 `f.write()` 还原后与原文件**逐字节一致**。

### 3.2 `list_files(path: str = "/") -> str`

列出 ESP32 文件系统内容。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `path` | `str` | 否 | `"/"` | 目标目录 |

- **底层执行**：`import os; print(os.listdir('<path>'))`
- **返回格式**：JSON 字符串数组，元素为 REPL 输出的各行。**如实说明当前实际格式**：首元素是 `os.listdir` 结果的 Python repr（一个字符串化的列表），末元素可能带 REPL 提示符残留 `">"`。
- **实测示例**（MCP 层返回值）：

```json
[
  "['boot.py', 'button_test.py', 'button_test_9.py', 'button_test_focused.py', 'buttons.py', 'buzzer.py', 'diagnose_buttons.py', 'hardware_config.py', 'leds.py', 'main.py', 'piano.py', 'pin_monitor.py']",
  ">"
]
```

> AI 使用方式：对首元素按 Python 字面量解析即可得到文件名列表。该"原始行"格式是已知瑕疵，见第十章。

### 3.3 `remove_file(remote_path: str) -> str`

删除 ESP32 上的文件（底层执行 `import os; os.remove('<remote_path>')`）。

- **成功返回**：`已删除文件：<remote_path>`
- **实测示例**：`已删除文件：_itc_demo.py`

---

## 四、程序执行与复位接口

### 4.1 `execute_program(remote_path: str, timeout: float = 5.0) -> str`

在 ESP32 上执行指定文件（底层执行 `exec(open('<remote_path>').read())`）。

- **返回**：程序 stdout 文本（经 raw REPL 净化的输出）。
- **如实说明实际行为**：后台监听线程与执行读取存在竞争，程序的 print 输出可能被监听线程先行捕获进入串口缓冲，导致本工具返回空或部分内容；**完整输出以 `read_serial_output` / `get_logs` 为准**（见第十章瑕疵 3）。实测中 `_itc_demo.py` 的返回为 `""`，而其输出出现在随后的串口缓冲里。
- **失败**：远端文件不存在 → 设备侧 Traceback（经输出通道观察，见 1.3 错误语义）。

### 4.2 `execute_repl(command: str, timeout: float = 5.0) -> str`

在 raw REPL 中执行单条 Python 命令。

- **返回**：REPL 输出文本。**当前实际格式**：剥除了横幅与 `\x04` 控制字符，但保留帧首 `OK` 标记与帧尾 `>` 提示符（已知瑕疵，见第十章）。
- **实测示例**（`import os; print(os.uname())`）：

```
OK(sysname='esp32', nodename='esp32', release='1.22.1', version='v1.22.1 on 2024-01-05', machine='Generic ESP32 module with ESP32')
>
```

### 4.3 `reset_esp32(hard: bool = False) -> str`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `hard` | `bool` | 否 | `False` | `False`=软复位（REPL 发送 Ctrl-D）；`True`=硬复位（DTR/RTS 拉低 EN，CP2102N 支持） |

- **返回**：`ESP32 已复位` / `ESP32 已硬复位`
- **副作用**：板子重启，若根目录存在 `main.py` 则自动重新运行（本项目数字钢琴即以此方式恢复运行）。
- **实测示例**（软复位后串口输出）：

```
MPY: soft reboot
数字钢琴已启动
7 个音符键: do re mi fa sol la si
八度键：低八度/高八度
```

---

## 五、固件烧录接口

### 5.1 `flash_firmware(firmware_path: str, port: str = "", baudrate: int = 460800, erase: bool = True) -> str`

通过 esptool 子进程烧录 MicroPython 固件（与 ROM bootloader 通信，**不要求板载已有固件**）。

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `firmware_path` | `str` | 是 | — | 本地 `.bin` 固件路径 |
| `port` | `str` | 否 | `""` | 串口名；留空用当前已连接端口 |
| `baudrate` | `int` | 否 | `460800` | 烧录波特率（与 REPL 的 115200 无关） |
| `erase` | `bool` | 否 | `True` | 烧录前是否整片擦除 |

- **执行序列**：释放串口 → `erase_flash`（可选）→ `write_flash -z 0x1000 <bin>` → 自动重连（详见架构文档 6.3 节时序图）。
- **返回**：esptool 各阶段输出拼接的多行文本（含 `[*]` 进度标记与 `[+]` 完成标记）。
- **失败**：固件文件不存在 → `FileNotFoundError`；esptool 非零退出 → `RuntimeError`（内含完整 esptool 输出，供 AI 诊断）。
- **实测说明**：该工具为破坏性操作（擦写 Flash），本次验证未在板子上执行；其命令模板与 esptool 原生命令一致，已在架构文档中定义。

---

## 六、串口监控与日志接口（数据格式）

### 6.1 数据格式约定

- **采集**：连接建立后，后台守护线程每 50ms 读取一次串口，UTF-8 解码（`errors="replace"`）后按"数据块"追加到缓冲区。
- **缓冲格式**：`list[str]`，每个元素是一次 `read_all()` 得到的文本块（不定长、可跨行）；上限 **1000 块**，超出丢弃最旧块。
- **消费语义**：两个读取工具对缓冲区的处理不同（见下表），`report_error` 内部以 `clear=False` 读取，诊断后保留现场。

### 6.2 `read_serial_output(clear: bool = True) -> str`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `clear` | `bool` | 否 | `True` | 读取后是否清空缓冲区（防止 AI 重复读到旧输出） |

- **返回**：缓冲区全部文本块拼接（无附加格式）。无输出时返回空串 `""`。
- **实测示例**：连接后钢琴程序静默运行期间返回 `""`；复位后返回启动横幅（见 4.3 节示例）。

### 6.3 `get_logs(lines: int = 100) -> str`

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `lines` | `int` | 否 | `100` | 返回最近的行数 |

- **返回**：缓冲区全文按行切分后取末 `lines` 行，以 `\n` 拼接。**不清空缓冲区**（与 6.2 的关键区别），可反复调用回溯历史。
- **实测示例**（`get_logs(20)` 末几行，截取）：

```
...
MPY: soft reboot
数字钢琴已启动
7 个音符键: do re mi fa sol la si
八度键：低八度/高八度
```

---

## 七、错误报告接口（协议）

### 7.1 `report_error() -> str` —— 结构化错误 JSON 协议

检查最近串口输出中的 MicroPython Traceback，返回 JSON 字符串（`ensure_ascii=False, indent=2`）。

**协议字段定义：**

| 字段 | 类型 | 含义 |
|------|------|------|
| `has_error` | `bool` | 是否检测到 Traceback。**恒存在**，是 AI 的首要判断字段 |
| `traceback` | `array<object>` | 调用栈帧数组（仅 `has_error=true` 时存在），按源码出现顺序排列 |
| `traceback[].file` | `str` | 帧所在文件名 |
| `traceback[].line` | `int` | 帧所在行号 |
| `traceback[].function` | `str` | 帧所在函数（模块级为 `<module>`） |
| `file` | `str \| null` | 栈底帧文件（错误实际抛出位置） |
| `line` | `int \| null` | 栈底帧行号 |
| `error_type` | `str \| null` | 异常类型名。当前仅匹配 `*Error`（如 `KeyError`）；`KeyboardInterrupt` 等为 `null`（已知限制） |
| `message` | `str \| null` | 异常消息文本 |
| `raw` | `str` | 原始串口输出全文，供 AI 在结构化字段不足时自行分析 |

**无错误情形（实测）：**

```json
{
  "has_error": false,
  "message": "未检测到 Traceback 错误"
}
```

**有错误情形（实测）**——本次验证中 Ctrl-C 中断了正在运行的钢琴程序，设备产生 `KeyboardInterrupt` Traceback，`report_error` 实际返回（节选）：

```json
{
  "has_error": true,
  "traceback": [
    { "file": "main.py", "line": 17, "function": "<module>" },
    { "file": "main.py", "line": 13, "function": "main" },
    { "file": "piano.py", "line": 97, "function": "run" }
  ],
  "file": "piano.py",
  "line": 97,
  "error_type": null,
  "message": null,
  "raw": "Traceback (most recent call last):\r\n  File \"main.py\", line 17, in <module>\r\n ..."
}

```

> 该实例同时暴露了已知限制：`KeyboardInterrupt` 不匹配 `(\w+Error)` 正则，故 `error_type`/`message` 为 `null`，但 `traceback` 与 `raw` 仍完整可用——AI 定位问题不受影响。改进方向见第十章。

### 7.2 `parse_error(output: str) -> dict | None`（纯函数）

`tools/error_handler.py` 同时暴露纯函数接口：输入任意串口文本，返回上述结构（无 Traceback 时返回 `None`）。可脱离硬件单独测试，是错误报告协议的可测试性保证。

---

## 八、底层协议格式（raw REPL）

工具链与设备间的全部交互（除烧录）承载于 MicroPython **raw REPL** 之上，控制字符约定：

| 字节 | 名称 | 作用 |
|------|------|------|
| `\x03` | Ctrl-C | 中断当前运行的程序 |
| `\x01` | Ctrl-A | 进入 raw REPL |
| `\x04` | Ctrl-D | raw REPL 中：执行已输入的代码；正常 REPL 中：软复位 |
| `\x02` | Ctrl-B | 退出 raw REPL，回到正常 REPL |

一次命令执行的帧结构：

```
请求：  [Ctrl-C][Ctrl-A] <command bytes> [Ctrl-D]
响应：  "raw REPL; CTRL-B to exit" 横幅 → "OK" → stdout → \x04 → stderr → \x04 → ">"
收尾：  [Ctrl-B]
```

客户端净化规则：剥离横幅行、删除全部 `\x04` 控制字符后返回（当前未剥离 `OK` 与 `>`，见第十章）。

---

## 九、接口验证记录（真实硬件）

- **日期/环境**：2026-07-17；Windows，COM5（USB-SERIAL）；ESP32-D0WD-V3，MicroPython v1.22.1；工具链 `toolchain/venv` Python。
- **验证方式**：绕开 MCP，直接驱动 `tools/` 各模块（分层测试策略，见架构文档第十章）。
- **结果**：

| 工具 | 实测 | 结果 |
|------|------|------|
| `connect_esp32` / `disconnect_esp32` | COM5 连接/断开 | ✅ |
| `upload_file` → `execute_program` → `remove_file` | `_itc_demo.py` 端到端文件传输与执行 | ✅ |
| `list_files` | 列出 12 个板载文件 | ✅（返回格式见 3.2 瑕疵说明） |
| `execute_repl` | `os.uname()` 返回 v1.22.1 系统信息 | ✅ |
| `read_serial_output` / `get_logs` | 捕获复位横幅与钢琴启动日志 | ✅ |
| `reset_esp32`（软） | 复位后钢琴程序自动重启 | ✅ |
| `report_error` | 正确捕获真实 Traceback 并结构化 | ✅ |
| `reset_esp32`（硬） | 未实测（软复位已满足流程） | ➖ |
| `flash_firmware` | 未实测（破坏性操作，按需验证） | ➖ |

- **板子状态**：验证结束后已通过软复位恢复，数字钢琴程序正常运行。

---

## 十、已知格式瑕疵与改进方向

以下为实测中暴露的真实行为，已如实记录于上文对应接口条目，作为第三周"工具独立测试与健壮性优化"的输入：

| # | 瑕疵 | 影响 | 改进方向 |
|---|------|------|---------|
| 1 | `execute_repl` 返回含帧首 `OK` 与帧尾 `>` 残留 | 输出不"净"，AI 需容忍 | 按 raw REPL 帧结构严格解析 stdout 段 |
| 2 | `list_files` 返回原始 REPL 行（repr 字符串 + 提示符），非净 JSON 数组 | AI 需二次解析首元素 | 在 REPL 端 `import json; print(json.dumps(os.listdir(p)))`，客户端直接解析 |
| 3 | 监听线程与执行读取竞争：`execute_program` 可能返回空，输出落入串口缓冲 | 输出分散在两个通道 | 执行期间暂停监听线程，或统一从缓冲按时间窗取证 |
| 4 | `error_type` 仅匹配 `*Error`，`KeyboardInterrupt` 等为 `null` | 结构化字段不完整（`raw` 仍可用） | 放宽异常名匹配，兜底取 Traceback 末行 |
| 5 | Traceback 帧 `function` 字段可能带 `\r`（CRLF 未清洗） | 字段含杂字符 | 解析前统一 `\r\n` → `\n` |

---

*本文档与 `report/toolchain_architecture.md` 配套使用：架构文档回答"系统如何分层、数据如何流动"，本文档回答"每个工具的输入输出是什么"。*
