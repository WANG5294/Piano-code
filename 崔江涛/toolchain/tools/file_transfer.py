"""
file_transfer.py — 文件传输工具（基于 MicroPython raw REPL 协议）
=================================================================

通过串口 raw REPL 协议将本地 Python 文件上传到 ESP32 文件系统。
使用 base64 编码传输文件内容，确保二进制安全。

=== raw REPL 协议说明 ===

MicroPython 的 raw REPL 模式（Ctrl+A 进入）是一种面向机器的协议，
用于电脑和 ESP32 之间进行程序化交互（区别于人类交互的"友好 REPL"）。

协议流程：
  1. 中断当前程序：发送 Ctrl+C（\x03）两次
  2. 进入 raw REPL：发送 Ctrl+A（\x01）
     等待响应 "raw REPL; CTRL-B to exit\r\n>"
  3. 发送代码 + Ctrl+D（\x04）执行
  4. 读取响应：OK + 2字节长度 + 输出 + \x04 结束标记
  5. 退出 raw REPL：发送 Ctrl+B（\x02）

=== 为什么需要暂停后台采集 ===

raw REPL 协议要求电脑和 ESP32 严格按顺序交换控制字符。
如果后台采集线程同时在读取串口数据，会"吃掉"部分协议响应，
导致发送方（电脑）永远等不到预期的回复。因此在上传前必须
调用 SerialConnection.pause_background_collection()，
上传完成后（用 try/finally 确保）调用 resume_background_collection()。

参考：https://docs.micropython.org/en/latest/reference/repl.html
"""

import os
import base64
import time
import logging

from tools._raw_repl import (
    CTRL_A, CTRL_B, CTRL_C, CTRL_D,
    RAW_REPL_PROMPT, RAW_REPL_OK,
    enter_raw_repl, exit_raw_repl, raw_repl_execute, extract_error,
)

logger = logging.getLogger(__name__)

# 文件上传分块大小（原始字节，base64 编码后约大 33%）
# 8KB 分块对应的 base64 约 11KB，加上 Python 语句开销约 200 字节，
# 总传输量约 11.5KB/chunk，远低于 ESP32 可用 RAM（~200KB），安全。
_CHUNK_SIZE = 8 * 1024  # 8KB


# ─── 公开 API ─────────────────────────────────────────────

def upload_file(local_path: str, remote_path: str,
                port: str = 'COM3', timeout_sec: float = 30.0) -> dict:
    """
    将本地文件上传到 ESP32。

    使用 raw REPL + base64 分块传输，确保二进制安全。
    传输前暂停后台采集线程，传输后恢复。

    .. attention::

        **此函数会中断 ESP32 上当前正在运行的程序。**

        因为文件传输需要进入 MicroPython raw REPL 模式（Ctrl+A），
        进入该模式会中断当前正在执行的任何 Python 程序（如 main.py
        中的钢琴主循环）。传输完成后退出 raw REPL（Ctrl+B）回到
        正常 REPL，但已中断的程序**不会自动恢复运行**。

        如需在传输后重新运行程序，有以下选项：
        1. 调用 ``SerialConnection.soft_reset()`` 触发软复位 — ESP32
           将自动执行 main.py（这是最简单的方式）
        2. 手动按 ESP32 的 RST 按钮触发热复位
        3. 等待后续 reset_device 工具完成（将提供更完善的复位+就绪检测）

        本函数只负责文件传输，不负责程序恢复。

    Args:
        local_path: 本地文件路径
        remote_path: ESP32 上的目标路径（如 "main.py" 或 "/flash/piano.py"）
        port: 串口号，默认 COM3
        timeout_sec: 总超时时间（秒），默认 30

    Returns:
        dict:
            {
                "status": "ok" | "error",
                "local_path": str,
                "remote_path": str,
                "bytes_transferred": int,   # 实际传输的字节数
                "error_message": str | None
            }
    """
    from serial_connection import SerialConnection

    result = {
        'status': 'error',
        'local_path': local_path,
        'remote_path': remote_path,
        'bytes_transferred': 0,
        'error_message': None,
    }

    # ── 1. 检查本地文件 ──
    if not os.path.isfile(local_path):
        result['error_message'] = f'本地文件不存在: {local_path}'
        logger.error(result['error_message'])
        return result

    file_size = os.path.getsize(local_path)
    if file_size == 0:
        result['error_message'] = f'文件为空: {local_path}'
        logger.error(result['error_message'])
        return result

    logger.info("准备上传: %s → %s (%d 字节)", local_path, remote_path, file_size)

    # ── 2. 建立串口连接 ──
    conn = SerialConnection()

    if not conn.is_connected():
        logger.info("串口未连接，尝试连接 %s...", port)
        if not conn.connect(port=port):
            result['error_message'] = '无法连接串口 ' + port
            if conn.last_error:
                result['error_message'] += f' ({conn.last_error["message"]})'
            return result

    # ── 3. 暂停后台采集（关键！） ──
    # 使用 try/finally 确保无论成功失败都恢复后台采集
    conn.pause_background_collection()
    try:
        # ── 4. 进入 raw REPL ──
        if not enter_raw_repl(conn, timeout_sec):
            result['error_message'] = (
                '无法进入 raw REPL 模式。'
                '请确认：1) ESP32 已连接 2) 固件正在运行 3) 串口未被其他程序占用'
            )
            return result

        try:
            # ── 5. 分块上传 ──
            file_size = os.path.getsize(local_path)
            with open(local_path, 'rb') as f:
                chunk_idx = 0
                total_written = 0

                # 预先计算总块数（用于判断最后一块）
                total_chunks = (file_size + _CHUNK_SIZE - 1) // _CHUNK_SIZE

                while True:
                    raw_chunk = f.read(_CHUNK_SIZE)
                    if not raw_chunk:
                        break

                    is_last = (chunk_idx + 1 >= total_chunks)
                    b64_chunk = base64.b64encode(raw_chunk)
                    mode = 'wb' if chunk_idx == 0 else 'ab'

                    # 构造 MicroPython 代码：写入文件
                    # 最后一块同时打印验证信息（避免额外的 REPL 往返）
                    if is_last:
                        code = (
                            f"import ubinascii\r\n"
                            f"with open('{remote_path}', '{mode}') as f:\r\n"
                            f"    f.write(ubinascii.a2b_base64({b64_chunk!r}))\r\n"
                            f"import os\r\n"
                            f"try:\r\n"
                            f"    s=os.stat('{remote_path}')\r\n"
                            f"    print('VERIFY_OK:'+str(s[6]))\r\n"
                            f"except Exception as e:\r\n"
                            f"    print('VERIFY_FAIL:'+str(e))\r\n"
                        )
                    else:
                        code = (
                            f"import ubinascii\r\n"
                            f"with open('{remote_path}', '{mode}') as f:\r\n"
                            f"    f.write(ubinascii.a2b_base64({b64_chunk!r}))\r\n"
                        )

                    # 执行
                    success, output = raw_repl_execute(conn, code,
                                                        timeout=min(15, timeout_sec))
                    if not success:
                        result['error_message'] = (
                            f'第 {chunk_idx + 1} 个分块写入失败（{len(raw_chunk)} 字节）: '
                            f'{extract_error(output)}'
                        )
                        # 尝试清理：删除不完整的远程文件
                        raw_repl_execute(conn,
                                          f"import os\r\n"
                                          f"try:\r\n"
                                          f"    os.remove('{remote_path}')\r\n"
                                          f"except: pass\r\n",
                                          timeout=5)
                        return result

                    total_written += len(raw_chunk)
                    chunk_idx += 1
                    logger.info("分块 %d 写入成功（%d 字节，累计 %d/%d）",
                                chunk_idx, len(raw_chunk), total_written, file_size)

                    # 最后一块的输出中包含验证信息
                    if is_last and 'VERIFY_OK:' in output:
                        reported_size = int(output.split('VERIFY_OK:')[1].split()[0])
                        if reported_size == file_size:
                            result['status'] = 'ok'
                            result['bytes_transferred'] = file_size
                            logger.info("上传验证成功: %s (%d 字节)", remote_path, file_size)
                        else:
                            result['error_message'] = (
                                f'文件大小不匹配: 本地 {file_size} 字节, '
                                f'远程 {reported_size} 字节'
                            )
                    elif is_last:
                        # 最后一块写成功但没有 VERIFY_OK
                        result['status'] = 'ok'  # 写入本身成功了
                        result['bytes_transferred'] = file_size
                        logger.info("上传完成: %s (%d 字节，但验证信息未捕获)", remote_path, file_size)

        finally:
            # ── 7. 退出 raw REPL（无论成功失败都要执行）──
            exit_raw_repl(conn)

    finally:
        # ── 8. 恢复后台采集（关键！用 finally 确保恢复）──
        conn.resume_background_collection()

    return result


def download_file(remote_path: str, local_path: str,
                  timeout_sec: float = 30.0) -> dict:
    """
    从 ESP32 下载指定文件到本地。

    使用 raw REPL 模式在 ESP32 端执行 base64 编码 + 分块输出，
    电脑端解析拼接后写入本地文件。

    Args:
        remote_path: ESP32 上的文件路径（如 "piano.py"）
        local_path: 保存到本地的路径
        timeout_sec: 总超时时间（秒），默认 30

    Returns:
        dict:
            {
                "status": "ok" | "error",
                "remote_path": str,
                "local_path": str,
                "bytes_transferred": int,
                "error_message": str | None
            }
    """
    from serial_connection import SerialConnection

    result = {
        'status': 'error',
        'remote_path': remote_path,
        'local_path': local_path,
        'bytes_transferred': 0,
        'error_message': None,
    }

    logger.info("准备下载: %s → %s", remote_path, local_path)

    conn = SerialConnection()

    if not conn.is_connected():
        if not conn.connect():
            result['error_message'] = '无法连接串口 COM3'
            return result

    conn.pause_background_collection()
    try:
        if not enter_raw_repl(conn, timeout=timeout_sec):
            result['error_message'] = '无法进入 raw REPL 模式'
            return result

        try:
            # ── 构造下载代码 ──
            # 在 ESP32 端读取文件，base64 编码后分块输出
            download_code = (
                f"import ubinascii\r\n"
                f"try:\r\n"
                f"    with open('{remote_path}', 'rb') as f:\r\n"
                f"        data = f.read()\r\n"
                f"    b64 = ubinascii.b2a_base64(data)\r\n"
                f"    total = len(data)\r\n"
                f"    print('DL_START:' + str(total))\r\n"
                f"    for i in range(0, len(b64), 4096):\r\n"
                f"        print('DL_C:' + b64[i:i+4096].decode()"
                f".replace(chr(10), ''))\r\n"
                f"    print('DL_END')\r\n"
                f"except OSError:\r\n"
                f"    print('DL_FAIL:FileNotFound')\r\n"
            )

            success, output = raw_repl_execute(
                conn, download_code, timeout=timeout_sec)

            if not success:
                # 检查是否是文件不存在
                if 'DL_FAIL:FileNotFound' in output:
                    result['error_message'] = (
                        f'远程文件不存在: {remote_path}'
                    )
                else:
                    result['error_message'] = (
                        f'下载执行失败: {extract_error(output)}'
                    )
                return result

            # ── 解析下载数据 ──
            if 'DL_FAIL:FileNotFound' in output:
                result['error_message'] = f'远程文件不存在: {remote_path}'
                return result

            # 提取 expected_size
            start_marker = 'DL_START:'
            start_idx = output.find(start_marker)
            if start_idx < 0:
                result['error_message'] = '未找到下载开始标记'
                return result

            # 在 DL_START: 行中提取文件大小
            start_line_end = output.find('\n', start_idx)
            if start_line_end < 0:
                start_line_end = output.find('\r\n', start_idx)
            if start_line_end < 0:
                start_line_end = len(output)
            start_line = output[start_idx:start_line_end].strip()
            expected_size = int(start_line[len(start_marker):].strip())

            # 提取所有 DL_C: 块
            b64_parts = []
            lines = output.split('\n')
            in_data = False
            for line in lines:
                stripped = line.strip()
                if stripped == 'DL_END':
                    break
                if in_data:
                    if stripped.startswith('DL_C:'):
                        b64_parts.append(stripped[5:])
                elif stripped.startswith('DL_START:'):
                    in_data = True

            if not b64_parts:
                result['error_message'] = '未找到下载数据块'
                return result

            b64_data = ''.join(b64_parts)

            # Base64 解码
            try:
                file_bytes = base64.b64decode(b64_data)
            except Exception as e:
                result['error_message'] = f'Base64 解码失败: {e}'
                return result

            # ── 校验大小 ──
            if len(file_bytes) != expected_size:
                result['error_message'] = (
                    f'文件大小不匹配: 期望 {expected_size} 字节, '
                    f'实际 {len(file_bytes)} 字节'
                )
                return result

            # ── 写入本地文件 ──
            os.makedirs(os.path.dirname(local_path) or '.', exist_ok=True)
            with open(local_path, 'wb') as f:
                f.write(file_bytes)

            result['status'] = 'ok'
            result['bytes_transferred'] = len(file_bytes)
            logger.info("下载成功: %s → %s (%d 字节)",
                        remote_path, local_path, len(file_bytes))

        finally:
            exit_raw_repl(conn)

    finally:
        conn.resume_background_collection()

    return result


# ─── 独立测试入口 ───────────────────────────────────────────

if __name__ == '__main__':
    """
    独立测试文件上传功能。

    用法：
        cd toolchain
        python tools/file_transfer.py [本地文件] [远程路径]

    示例：
        # 创建测试文件并上传
        echo "print('hello from ESP32')" > test_upload.py
        python tools/file_transfer.py test_upload.py test_upload.py

        # 然后用 mpremote 验证
        mpremote connect COM3 run test_upload.py
    """
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(name)s: %(message)s',
    )

    local = sys.argv[1] if len(sys.argv) > 1 else 'test_upload_verify.py'
    remote = sys.argv[2] if len(sys.argv) > 2 else local

    print("=" * 60)
    print("  ESP32 文件上传测试")
    print("=" * 60)
    print(f"  本地: {local}")
    print(f"  远程: {remote}")
    print()

    if not os.path.isfile(local):
        # 如果指定文件不存在，自动创建一个测试文件
        if local == 'test_upload_verify.py':
            print("[!] 测试文件不存在，自动创建...")
            with open(local, 'w') as f:
                f.write("# test_upload_verify.py\n")
                f.write("print('UPLOAD_TEST_OK')\n")
                f.write(f"print('file: {local}')\n")
            print(f"    已创建: {local}")

    result = upload_file(local, remote)

    print(f"\n--- 上传结果 ---")
    print(f"状态: {result['status']}")
    print(f"本地: {result['local_path']}")
    print(f"远程: {result['remote_path']}")
    print(f"传输: {result['bytes_transferred']} 字节")
    if result['error_message']:
        print(f"错误: {result['error_message']}")

    if result['status'] == 'ok':
        print(f"\n上传成功！可以用 mpremote 运行验证:")
        print(f"  mpremote connect COM3 run {remote}")
