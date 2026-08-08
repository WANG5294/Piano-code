"""
execute_program.py — 程序执行工具
===================================

通过 raw REPL 协议在 ESP32 上执行 Python 代码或启动指定模块。
复用 _raw_repl.py 中的共享 raw REPL 函数，不重复实现底层协议。

=== code vs module ===

- code: 直接发送一段 Python 代码到 ESP32 执行，等待返回输出
- module: 导入并启动指定模块（如 "piano"），模块代码运行在 ESP32
          后台；执行完成后自动触发软复位确保 main.py 重新运行

=== 超时处理 ===

如果执行超时（如代码中包含无限循环），会发送 Ctrl+C 中断执行，
捕获已有的输出后返回。设备不会因此卡死。
"""

import time
import logging

logger = logging.getLogger(__name__)


def execute(module: str | None = None,
            code: str | None = None,
            timeout_sec: float = 30.0) -> dict:
    """
    在 ESP32 上执行指定模块或代码片段。

    module 和 code 至少提供一个。如果都提供，code 优先。

    Args:
        module: 要导入并启动的模块名（如 "piano"）。
                会生成代码: "import {module}" 在 raw REPL 中执行，
                完成后自动软复位让 main.py 重新运行（启动模块主循环）。
        code: 直接在 ESP32 上执行的 Python 代码字符串。
        timeout_sec: 等待执行完成的超时（秒），默认 30.0

    Returns:
        dict:
            {
                "status": "ok" | "error",
                "stdout": str,       # 正常 print 输出
                "stderr": str,       # 错误信息（Traceback 等）
                "exit_code": int,    # 0=成功，1=执行错误，2=超时
            }
    """
    from serial_connection import SerialConnection
    from tools._raw_repl import (
        enter_raw_repl, exit_raw_repl, raw_repl_execute,
    )

    result = {
        'status': 'error',
        'stdout': '',
        'stderr': '',
        'exit_code': 1,
    }

    # ── 参数校验 ──
    if not code and not module:
        result['stderr'] = '参数缺失: module 和 code 至少需要提供一个'
        return result

    # ── 构造要执行的代码 ──
    if code:
        exec_code = code
        exec_desc = f'code ({len(code)} chars)'
    else:
        # 模块导入：只做 import，不调用 run()（避免无限循环）
        exec_code = f"import {module}\r\n"
        exec_code += f"print('MODULE_IMPORT_OK: {module}')\r\n"
        exec_desc = f'module={module}'

    logger.info("execute_program: %s, timeout=%.1f 秒", exec_desc, timeout_sec)

    try:
        conn = SerialConnection()

        if not conn.is_connected():
            if not conn.connect():
                result['stderr'] = '无法连接串口 COM3'
                return result

        # ── 暂停后台采集，独占串口用于 raw REPL ──
        conn.pause_background_collection()
        try:
            # ── 进入 raw REPL ──
            if not enter_raw_repl(conn, timeout=10.0):
                result['stderr'] = '无法进入 raw REPL 模式'
                return result

            try:
                # ── 执行代码 ──
                success, output = raw_repl_execute(
                    conn, exec_code, timeout=timeout_sec)

                # ── 解析输出：分离 stdout 和 stderr ──
                stdout, stderr = _split_output(output)

                if success:
                    result['status'] = 'ok'
                    result['exit_code'] = 0
                    result['stdout'] = stdout
                    result['stderr'] = stderr
                else:
                    # 判断是超时（KeyboardInterrupt）还是执行错误（Traceback）
                    if 'KeyboardInterrupt' in output or '超时' in output:
                        result['status'] = 'error'
                        result['exit_code'] = 2  # 2 = 超时中断
                        result['stderr'] = (
                            f'执行超时（{timeout_sec}秒），已发送中断信号\n'
                            f'{output}'
                        )
                    else:
                        result['status'] = 'error'
                        result['exit_code'] = 1  # 1 = 代码执行错误
                        result['stdout'] = stdout
                        result['stderr'] = stderr

            finally:
                # ── 退出 raw REPL（无论成功失败）──
                exit_raw_repl(conn)

        finally:
            # ── 恢复后台采集 ──
            conn.resume_background_collection()

        # ── 模块执行后的特殊处理 ──
        # 模块导入成功后，需要软复位让 main.py 重新运行
        # （因为 raw REPL 中断了当前运行的程序）
        if module and result['exit_code'] == 0:
            logger.info("模块导入成功，触发软复位让 main.py 运行...")
            boot_msg = conn.soft_reset(capture_timeout=4.0)
            if boot_msg:
                result['stdout'] += '\n--- 软复位后启动信息 ---\n' + boot_msg
                result['stdout'] += '\n(模块已加载，钢琴程序正在后台运行)'

        return result

    except Exception as e:
        logger.error("execute_program 未预期异常: %s", e, exc_info=True)
        result['status'] = 'error'
        result['stderr'] = f'执行过程发生异常: {str(e)}'
        result['exit_code'] = 1
        return result


def _split_output(output: str) -> tuple[str, str]:
    """
    将 raw REPL 输出分离为 stdout 和 stderr。

    简单策略：
      - 如果输出包含 "Traceback (most recent call last)"，
        则 Traceback 行及之后的内容归为 stderr，之前的内容归 stdout
      - 否则全部归为 stdout
    """
    if not output:
        return '', ''

    traceback_marker = 'Traceback (most recent call last)'
    idx = output.find(traceback_marker)

    if idx >= 0:
        stdout = output[:idx].strip()
        stderr = output[idx:].strip()
    else:
        stdout = output.strip()
        stderr = ''

    return stdout, stderr


# ─── 独立测试入口 ───────────────────────────────────────────

if __name__ == '__main__':
    """
    独立测试 execute_program 工具。

    用法：
        cd toolchain
        python tools/execute_program.py code "print('hello')"
        python tools/execute_program.py module piano
    """
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(name)s: %(message)s',
    )

    # 自动确保连接
    from serial_connection import SerialConnection
    conn = SerialConnection()
    if not conn.is_connected():
        conn.connect()

    mode = sys.argv[1] if len(sys.argv) > 1 else 'code'
    arg = sys.argv[2] if len(sys.argv) > 2 else "print('EXEC_TEST_OK')"
    timeout = float(sys.argv[3]) if len(sys.argv) > 3 else 10.0

    print("=" * 50)
    print(f"  ESP32 程序执行 (mode={mode})")
    print("=" * 50)

    if mode == 'module':
        result = execute(module=arg, timeout_sec=timeout)
    else:
        result = execute(code=arg, timeout_sec=timeout)

    print(f"\n状态:     {result['status']}")
    print(f"exit_code: {result['exit_code']}")
    print(f"\n--- stdout ---")
    print(result['stdout'] or '(空)')
    if result['stderr']:
        print(f"\n--- stderr ---")
        print(result['stderr'])
