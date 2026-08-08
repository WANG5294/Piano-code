"""
ESP32 串口通信客户端
提供与 ESP32 开发板交互的基础能力：
- 串口连接管理
- REPL 命令执行
- 文件上传/下载（基于 MicroPython raw REPL）
- 串口输出监听
"""

import serial
import subprocess
import sys
import time
import re
import threading
from pathlib import Path
from typing import Optional, List, Dict, Any


class ESP32Client:
    """ESP32 串口客户端"""

    def __init__(self, port: Optional[str] = None, baudrate: int = 115200, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._monitor_thread: Optional[threading.Thread] = None
        self._monitor_running = False
        self._output_buffer: List[str] = []
        self._buffer_lock = threading.Lock()

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------
    def connect(self, port: Optional[str] = None) -> str:
        """连接 ESP32 串口"""
        if port:
            self.port = port
        if not self.port:
            raise ValueError("未指定串口端口，请提供 port 参数（如 'COM3' 或 '/dev/ttyUSB0'）")

        if self._serial and self._serial.is_open:
            self._serial.close()

        self._serial = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=self.timeout
        )
        time.sleep(0.2)  # 等待串口稳定
        self._serial.reset_input_buffer()
        self._serial.reset_output_buffer()

        # 启动串口监听线程
        self._start_monitor()

        return f"已连接到 ESP32：{self.port} @ {self.baudrate} baud"

    def disconnect(self) -> str:
        """断开串口连接"""
        self._stop_monitor()
        if self._serial and self._serial.is_open:
            self._serial.close()
            self._serial = None
        return "已断开与 ESP32 的连接"

    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._serial is not None and self._serial.is_open

    def _ensure_connected(self):
        if not self.is_connected():
            raise RuntimeError("ESP32 未连接，请先调用 connect()")

    # ------------------------------------------------------------------
    # REPL 命令执行
    # ------------------------------------------------------------------
    def exec_raw(self, command: str, timeout: float = 5.0) -> str:
        """
        进入 MicroPython raw REPL 并执行命令
        返回执行结果字符串
        """
        self._ensure_connected()

        with self._lock:
            ser = self._serial
            ser.write(b"\x03")  # Ctrl-C: 中断当前程序
            time.sleep(0.1)
            ser.write(b"\x01")  # Ctrl-A: 进入 raw REPL
            time.sleep(0.1)
            ser.read_all()  # 清空提示信息

            # 发送命令
            cmd_bytes = command.encode("utf-8")
            ser.write(cmd_bytes)
            ser.write(b"\x04")  # Ctrl-D: 执行

            # 读取结果
            deadline = time.time() + timeout
            response = b""
            while time.time() < deadline:
                chunk = ser.read_all()
                if chunk:
                    response += chunk
                    if b"\x04\x04>" in response or response.endswith(b">"):
                        break
                time.sleep(0.05)

            # 退出 raw REPL
            ser.write(b"\x02")  # Ctrl-B: 退出 raw REPL
            time.sleep(0.1)

        # 解析结果
        text = response.decode("utf-8", errors="replace")
        # 去掉前后提示符
        text = re.sub(r"^\s*raw REPL; CTRL-B to exit\r?\n", "", text)
        text = re.sub(r"\x04", "", text)
        text = text.strip()
        return text

    def exec_normal(self, command: str, timeout: float = 5.0) -> str:
        """
        在普通 REPL 模式下执行单条命令
        适合快速验证
        """
        self._ensure_connected()

        with self._lock:
            ser = self._serial
            ser.write(b"\x03\x03")  # 两次 Ctrl-C 确保中断
            time.sleep(0.1)
            ser.read_all()

            ser.write(command.encode("utf-8") + b"\r\n")
            time.sleep(0.1)

            deadline = time.time() + timeout
            response = b""
            while time.time() < deadline:
                chunk = ser.read_all()
                if chunk:
                    response += chunk
                    if b">>>" in response:
                        break
                time.sleep(0.05)

        text = response.decode("utf-8", errors="replace")
        return text.strip()

    # ------------------------------------------------------------------
    # 文件传输（简化版：基于 exec_raw 写入文件）
    # ------------------------------------------------------------------
    def upload_file(self, local_path: str, remote_path: str = "") -> str:
        """上传本地 MicroPython 文件到 ESP32"""
        self._ensure_connected()

        local = Path(local_path)
        if not local.exists():
            raise FileNotFoundError(f"本地文件不存在：{local_path}")

        remote = remote_path or local.name
        content = local.read_text(encoding="utf-8")

        # 将文件内容写入 ESP32 文件系统
        # 使用 Python 的 exec_raw 执行写入命令
        escaped = content.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n")
        cmd = f'with open("{remote}", "w") as f: f.write("{escaped}")'

        result = self.exec_raw(cmd)
        return f"文件上传成功：{local_path} -> {remote}"

    def list_files(self, path: str = "/") -> List[str]:
        """列出 ESP32 文件系统中的文件"""
        self._ensure_connected()
        result = self.exec_raw(f"import os; print(os.listdir('{path}'))")
        return result.splitlines()

    def remove_file(self, remote_path: str) -> str:
        """删除 ESP32 上的文件"""
        self._ensure_connected()
        self.exec_raw(f"import os; os.remove('{remote_path}')")
        return f"已删除文件：{remote_path}"

    # ------------------------------------------------------------------
    # 程序控制
    # ------------------------------------------------------------------
    def run_file(self, remote_path: str, timeout: float = 5.0) -> str:
        """运行 ESP32 上的指定 Python 文件"""
        self._ensure_connected()
        result = self.exec_raw(f"exec(open('{remote_path}').read())", timeout=timeout)
        return result

    def reset(self) -> str:
        """软复位 ESP32"""
        self._ensure_connected()
        with self._lock:
            self._serial.write(b"\x04")  # Ctrl-D: 软复位
            time.sleep(0.5)
        return "ESP32 已复位"

    def hard_reset(self) -> str:
        """通过 DTR/RTS 硬复位 ESP32（CP2102N 支持）"""
        self._ensure_connected()
        with self._lock:
            self._serial.dtr = False
            self._serial.rts = True
            time.sleep(0.1)
            self._serial.rts = False
            time.sleep(0.5)
        return "ESP32 已硬复位"

    # ------------------------------------------------------------------
    # 固件烧录
    # ------------------------------------------------------------------
    def flash_firmware(
        self,
        firmware_path: str,
        port: Optional[str] = None,
        baudrate: int = 460800,
        erase: bool = True,
        flash_offset: str = "0x1000",
    ) -> str:
        """
        通过 esptool 烧录 MicroPython 固件到 ESP32

        Args:
            firmware_path: 本地 MicroPython 固件 (.bin) 路径
            port: 串口名称，默认使用当前连接或构造时指定的端口
            baudrate: 烧录波特率，默认 460800
            erase: 烧录前是否先擦除整个 Flash，默认 True
            flash_offset: 固件写入偏移地址，ESP32 通常为 0x1000
        """
        port = port or self.port
        if not port:
            raise ValueError("未指定串口端口，请提供 port 参数（如 'COM5' 或 '/dev/ttyUSB0'）")

        fw = Path(firmware_path)
        if not fw.exists():
            raise FileNotFoundError(f"固件文件不存在：{firmware_path}")

        # 烧录前需要释放串口，避免与 esptool 冲突
        was_connected = self.is_connected()
        if was_connected:
            self.disconnect()

        base_cmd = [
            sys.executable, "-m", "esptool",
            "--chip", "esp32",
            "--port", port,
            "--baud", str(baudrate),
        ]

        outputs = []

        def _run(args: List[str]) -> str:
            result = subprocess.run(
                base_cmd + args,
                capture_output=True,
                text=True,
            )
            text = (result.stdout or "") + (result.stderr or "")
            if result.returncode != 0:
                raise RuntimeError(f"esptool 执行失败（exit {result.returncode}）：\n{text}")
            return text

        try:
            if erase:
                outputs.append("[*] 擦除 Flash...")
                outputs.append(_run(["erase_flash"]))

            outputs.append("[*] 烧录固件...")
            outputs.append(_run(["write_flash", "-z", flash_offset, str(fw.resolve())]))
            outputs.append(f"[+] 固件烧录完成：{fw.resolve()}")
            return "\n".join(outputs)
        finally:
            # 如果之前保持连接，尝试重新连接（esptool 操作后板子会复位）
            if was_connected:
                try:
                    self.connect(port)
                except Exception as e:
                    outputs.append(f"[!] 自动重连失败：{e}")

    # ------------------------------------------------------------------
    # 串口监控
    # ------------------------------------------------------------------
    def _start_monitor(self):
        """启动后台串口监听线程"""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return
        self._monitor_running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _stop_monitor(self):
        """停止后台串口监听线程"""
        self._monitor_running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None

    def _monitor_loop(self):
        """后台持续读取串口输出"""
        while self._monitor_running:
            if self._serial and self._serial.is_open:
                try:
                    data = self._serial.read_all()
                    if data:
                        text = data.decode("utf-8", errors="replace")
                        with self._buffer_lock:
                            self._output_buffer.append(text)
                            # 限制缓冲区大小
                            if len(self._output_buffer) > 1000:
                                self._output_buffer = self._output_buffer[-1000:]
                except Exception:
                    pass
            time.sleep(0.05)

    def read_serial_output(self, clear: bool = True) -> str:
        """读取并返回缓存的串口输出"""
        with self._buffer_lock:
            output = "".join(self._output_buffer)
            if clear:
                self._output_buffer.clear()
            return output

    def get_logs(self, lines: int = 100) -> List[str]:
        """获取最近的串口日志"""
        with self._buffer_lock:
            all_text = "".join(self._output_buffer)
            lines_list = all_text.splitlines()
            return lines_list[-lines:] if lines_list else []

    # ------------------------------------------------------------------
    # 错误解析
    # ------------------------------------------------------------------
    def parse_error(self, output: str) -> Optional[Dict[str, Any]]:
        """解析 MicroPython Traceback，提取错误信息"""
        if "Traceback" not in output:
            return None

        error_info = {
            "has_error": True,
            "traceback": [],
            "file": None,
            "line": None,
            "error_type": None,
            "message": None,
            "raw": output
        }

        # 提取 Traceback 行
        tb_pattern = re.compile(r'File "([^"]+)", line (\d+), in (.+)')
        for match in tb_pattern.finditer(output):
            error_info["traceback"].append({
                "file": match.group(1),
                "line": int(match.group(2)),
                "function": match.group(3)
            })
            error_info["file"] = match.group(1)
            error_info["line"] = int(match.group(2))

        # 提取错误类型和消息
        err_pattern = re.compile(r'(\w+Error):\s*(.+)$', re.MULTILINE)
        match = err_pattern.search(output)
        if match:
            error_info["error_type"] = match.group(1)
            error_info["message"] = match.group(2).strip()

        return error_info


# 全局单例，供 MCP 服务器使用
_esp32_client: Optional[ESP32Client] = None


def get_client() -> ESP32Client:
    """获取全局 ESP32Client 实例"""
    global _esp32_client
    if _esp32_client is None:
        _esp32_client = ESP32Client()
    return _esp32_client
