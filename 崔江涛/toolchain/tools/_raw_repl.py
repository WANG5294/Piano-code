"""
_raw_repl.py — MicroPython raw REPL 协议共享模块
==================================================

供 file_transfer 和 execute_program 共用的底层 raw REPL 通信函数。
不直接对外暴露（模块名前缀 _ 表示私有实现细节）。

关键发现（MicroPython v1.18）：
  - 进入 raw REPL 后的第一个 Ctrl+D 触发软复位，需要先消耗掉
  - OK 是"代码已收到"的确认，\\x04 才是"执行完成"的标记
  - 成功响应: OK + output + \\x04(+...)
  - 错误响应: OK + \\x04 + error_text

参考：https://docs.micropython.org/en/latest/reference/repl.html
"""

import time
import logging

logger = logging.getLogger(__name__)

# raw REPL 控制字符
CTRL_A = b'\x01'  # 进入 raw REPL
CTRL_B = b'\x02'  # 退出 raw REPL
CTRL_C = b'\x03'  # 中断
CTRL_D = b'\x04'  # 执行（raw REPL 中表示代码结束）

# raw REPL 响应标记
RAW_REPL_PROMPT = b'raw REPL; CTRL-B to exit\r\n>'
RAW_REPL_OK = b'OK'


def _drain_response(conn, timeout: float = 2.0) -> None:
    """读取并丢弃 raw REPL 响应数据（用于消耗软复位输出等）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        b = conn.raw_read_bytes(256, timeout=0.2)
        if not b:
            break


def enter_raw_repl(conn, timeout: float = 10.0) -> bool:
    """
    进入 MicroPython raw REPL 模式。

    步骤：
      1. 发送两次 Ctrl+C 中断当前程序
      2. 发送 Ctrl+A 进入 raw REPL
      3. 等待 raw REPL 提示符
      4. 消耗首次 Ctrl+D（软复位），后续 Ctrl+D 才能执行代码
    """
    conn.raw_flush_input()
    # 第一次 Ctrl+C：触发 KeyboardInterrupt
    conn.raw_write(b'\r' + CTRL_C + CTRL_C)
    # 等待 ~200ms，此时 main.py 应处于 500ms sleep 中
    time.sleep(0.2)
    conn.raw_flush_input()

    # 第二次 Ctrl+C：在 sleep 期间中断，KeyboardInterrupt 不被
    # except Exception 捕获，传播到 except KeyboardInterrupt → break → REPL
    conn.raw_write(b'\r' + CTRL_C + CTRL_C)
    time.sleep(0.4)
    conn.raw_flush_input()

    conn.raw_write(b'\r' + CTRL_A)
    time.sleep(0.5)

    response = conn.raw_read_until(RAW_REPL_PROMPT, timeout=timeout)
    if RAW_REPL_PROMPT not in response:
        logger.warning("未收到 raw REPL 提示符，响应: %r", response[:100])
        return False

    # 消耗首次 Ctrl+D（触发软复位而非执行代码）
    conn.raw_write(CTRL_D)
    time.sleep(0.3)
    _drain_response(conn, timeout=2.0)

    logger.debug("已进入 raw REPL 模式（已消化首次软复位）")
    return True


def exit_raw_repl(conn) -> None:
    """退出 MicroPython raw REPL 模式，回到友好 REPL。"""
    try:
        conn.raw_write(b'\r' + CTRL_B)
        time.sleep(0.2)
        conn.raw_flush_input()
        logger.debug("已退出 raw REPL 模式")
    except Exception as e:
        logger.warning("退出 raw REPL 时异常（忽略）: %s", e)


def raw_repl_execute(conn, code: str, timeout: float = 10.0) -> tuple[bool, str]:
    """
    在 raw REPL 模式下执行 Python 代码并获取输出。

    MicroPython v1.18 响应格式：
      - 先发送 OK（代码已收到，开始执行）
      - 代码执行完成后发送 \\x04（执行完成标记）
      - 成功: ...OK...output...\\x04...
      - 错误: ...OK...\\x04...error_text...

    因此必须等待 \\x04 而非 OK 来判断执行是否完成。
    OK 可能在执行开始时就到达，\\x04 在执行完成后才到达。

    Returns:
        (success, output_text) 二元组。
        success=True 表示执行成功（输出中无 Traceback）
    """
    payload = code.encode('utf-8') + CTRL_D
    conn.raw_write(payload)

    deadline = time.monotonic() + timeout

    # 读取全部响应直到 \\x04 执行完成标记或超时
    all_data = b''
    while b'\x04' not in all_data and time.monotonic() < deadline:
        b = conn.raw_read_bytes(1, timeout=0.3)
        if b:
            all_data += b

    # 找到 \\x04 后，短暂继续读取 — 错误响应的 traceback 在 \\x04 之后
    if b'\x04' in all_data:
        dl_extra = time.monotonic() + 0.5
        while time.monotonic() < dl_extra:
            b = conn.raw_read_bytes(256, timeout=0.15)
            if b:
                all_data += b
            else:
                break

    # ── 超时：未收到任何 \\x04（执行未完成）──
    if b'\x04' not in all_data:
        logger.warning("raw REPL 执行超时（%.1fs 未收到 \\x04），发送 Ctrl+C...", timeout)
        conn.raw_write(b'\r' + CTRL_C + CTRL_C)
        time.sleep(0.3)
        remaining = b''
        dl2 = time.monotonic() + 3.0
        while time.monotonic() < dl2:
            b = conn.raw_read_bytes(1, timeout=0.3)
            if b:
                remaining += b
            else:
                break
        output = (all_data + remaining).decode('utf-8', errors='replace').strip()
        if not output:
            output = '(执行超时，已发送中断信号)'
        return False, output

    # ── 解析响应 ──
    end_idx = all_data.find(b'\x04')
    before_eof = all_data[:end_idx]      # \\x04 之前
    after_eof = all_data[end_idx + 1:]   # \\x04 之后（错误文本在此）

    # 查找 OK
    ok_idx = before_eof.find(RAW_REPL_OK)
    if ok_idx < 0:
        output_text = all_data.decode('utf-8', errors='replace').strip()
        return False, output_text

    after_ok = before_eof[ok_idx + 2:]  # OK 之后、\\x04 之前的内容

    # 错误响应: OK 后就是 \\x04，真正的错误文本在 \\x04 之后
    if not after_ok.strip() and after_eof.strip():
        output_text = after_eof.decode('utf-8', errors='replace').strip()
    else:
        # 成功响应: OK + 输出 + \\x04(+可能残留)
        output_text = after_ok.decode('utf-8', errors='replace').strip()

    success = 'Traceback' not in output_text

    if not success:
        logger.warning("raw REPL 执行异常: %s",
                       extract_error(output_text)[:200])

    return success, output_text


def extract_error(output: str) -> str:
    """从 raw REPL 输出中提取错误信息的最后一行。"""
    if not output or not output.strip():
        return '(无输出)'
    lines = output.strip().split('\n')
    return lines[-1].strip() if lines else output.strip()
