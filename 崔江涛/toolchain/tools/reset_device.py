"""
reset_device.py — 微控制器复位工具
====================================

通过软复位（Ctrl+D）或硬件复位（DTR）触发 ESP32 重启，
等待设备就绪并返回启动信息。

依赖 serial_connection.py 中的 SerialConnection 单例
（复用已有的后台采集线程捕获启动信息）。
"""

import time
import logging

logger = logging.getLogger(__name__)

# ESP32 钢琴固件启动横幅关键字，用于判断设备是否已就绪
_BOOT_BANNER_KEYWORDS = ['ESP32', '数字钢琴']


def reset(mode: str = "soft", wait_ready_sec: float = 5.0) -> dict:
    """
    复位 ESP32 设备，等待就绪后返回启动信息。

    Args:
        mode: "soft"（默认，Ctrl+D 软复位）或 "hard"（DTR 硬件复位）
        wait_ready_sec: 等待设备就绪的超时时间（秒），默认 5.0

    Returns:
        dict:
            {
                "status": "ok" | "error",
                "boot_msg": str,        # 复位过程中捕获的启动信息
                "ready": bool,          # 是否检测到预期启动横幅
            }

        当 mode="hard" 且 DTR 复位失败时，会自动回退到 soft 模式。
        此时 boot_msg 开头会包含 "[回退到软复位]" 标记。
    """
    from serial_connection import SerialConnection

    result = {
        'status': 'error',
        'boot_msg': '',
        'ready': False,
    }

    try:
        conn = SerialConnection()

        if not conn.is_connected():
            logger.info("reset_device: 串口未连接，尝试连接...")
            if not conn.connect():
                result['boot_msg'] = '无法连接串口 COM3'
                return result

        # ── 执行复位 ────────────────────────────────────
        if mode == 'hard':
            logger.info("reset_device: 尝试 DTR 硬件复位...")
            boot_msg = conn.hard_reset(capture_timeout=wait_ready_sec)

            if not boot_msg:
                # DTR 复位失败（驱动不支持或未生效），自动回退到软复位
                logger.warning("DTR 硬复位失败，回退到软复位")
                boot_msg = conn.soft_reset(capture_timeout=wait_ready_sec)
                if boot_msg:
                    boot_msg = '[回退到软复位] DTR硬复位失败，已自动使用Ctrl+D软复位\n' + boot_msg
                else:
                    result['boot_msg'] = (
                        '硬复位失败（DTR 可能不被 CH9102 驱动支持），'
                        '且软复位也未捕获到启动信息'
                    )
                    return result
        else:  # mode == 'soft'
            logger.info("reset_device: 执行 Ctrl+D 软复位...")
            boot_msg = conn.soft_reset(capture_timeout=wait_ready_sec)

        result['boot_msg'] = boot_msg

        # ── 就绪检测 ────────────────────────────────────
        if boot_msg:
            # 检查启动信息中是否包含预期的横幅关键字
            ready = all(kw in boot_msg for kw in _BOOT_BANNER_KEYWORDS)
            result['ready'] = ready
            result['status'] = 'ok'

            if ready:
                logger.info("reset_device: 设备就绪（检测到启动横幅）")
            else:
                logger.info("reset_device: 复位已执行，但未检测到启动横幅 "
                            "（可能运行的不是钢琴固件）")
        else:
            # 复位指令已发送但未捕获到任何信息
            result['status'] = 'ok'  # 复位动作本身执行了
            result['ready'] = False
            result['boot_msg'] = '(未捕获到启动信息，复位可能已执行但无输出)'
            logger.warning("reset_device: 复位后未捕获到启动信息")

        return result

    except Exception as e:
        logger.error("reset_device 未预期异常: %s", e, exc_info=True)
        result['status'] = 'error'
        result['boot_msg'] = f'复位过程发生异常: {str(e)}'
        result['ready'] = False
        return result


# ─── 独立测试入口 ───────────────────────────────────────────

if __name__ == '__main__':
    """
    独立测试复位工具。

    用法：
        cd toolchain
        python tools/reset_device.py [soft|hard] [等待秒数]

    示例：
        python tools/reset_device.py soft   # 软复位，默认等待5秒
        python tools/reset_device.py hard 10  # 硬复位，等待10秒
    """
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(name)s: %(message)s',
    )

    mode = sys.argv[1] if len(sys.argv) > 1 else 'soft'
    wait = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

    print("=" * 50)
    print(f"  ESP32 复位测试 (mode={mode}, wait={wait}s)")
    print("=" * 50)
    print()

    result = reset(mode=mode, wait_ready_sec=wait)

    print(f"状态:   {result['status']}")
    print(f"就绪:   {result['ready']}")
    print(f"启动信息 ({len(result['boot_msg'])} 字符):")
    print(f"{'─' * 50}")
    print(result['boot_msg'])
    print(f"{'─' * 50}")
