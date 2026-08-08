"""
live_monitor.py — 实时串口监控（tail -f 风格）
================================================

用于视频录制/演示的辅助脚本。连接 ESP32 后持续显示
实时输出的日志行，效果类似 `tail -f`。

复用 SerialConnection 的后台采集线程，不需要重新写连接逻辑。
后台采集线程在连接建立时已启动，本脚本只做"取数据 → 打印新增行"。

运行方式：
    cd toolchain
    python live_monitor.py

退出：按 Ctrl+C
"""

import sys
import os
import time

# 确保 toolchain 目录在 sys.path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from serial_connection import SerialConnection, list_available_ports


def main():
    print("=" * 50)
    print("  ESP32 实时串口监控 (live_monitor)")
    print("=" * 50)
    print()

    # 显示可用端口
    ports = list_available_ports()
    if ports:
        for p in ports:
            print(f"  检测到: {p['device']} - {p['description']}")
    else:
        print("  [!] 未检测到任何串口！请检查 ESP32 连接。")
        return 1
    print()

    # 建立连接
    conn = SerialConnection()
    print("正在连接 COM3...")
    if not conn.connect():
        print(f"  [FAIL] 连接失败: {conn.last_error}")
        return 1
    print(f"  [OK] 已连接 COM3 @ 115200")

    # 确保后台采集已启动
    if not conn.collection_active:
        print("正在启动后台采集...")
        if not conn.start_background_collection():
            print("  [FAIL] 后台采集启动失败")
            return 1
        # 刚启动时缓冲区为空，等一小会儿让后台线程开始工作
        time.sleep(0.3)

    print(f"  [OK] 后台采集运行中（缓冲区容量 1000 行）")
    print()

    # 游标：记录"上次已打印到第几条"，避免重复打印旧数据
    last_printed_count = 0
    run_start_time = time.time()

    print("实时监控已启动，按下琴键查看效果 (Ctrl+C 退出)")
    print("-" * 50)

    try:
        while True:
            # 从后台缓冲区获取全部缓存条目
            all_entries = conn.get_recent_lines()

            # 计算有多少条是"新"的（自上次打印后新增的）
            current_total = len(all_entries)

            if current_total > last_printed_count:
                # 只处理游标之后的新条目
                new_entries = all_entries[last_printed_count:]
                for entry in new_entries:
                    ts = time.strftime('%H:%M:%S',
                                       time.localtime(entry['timestamp']))
                    print(f"[{ts}] {entry['line']}")

                # 更新游标
                last_printed_count = current_total

            time.sleep(0.1)

    except KeyboardInterrupt:
        elapsed = time.time() - run_start_time
        print()
        print("-" * 50)
        print(f"监控已停止（运行了 {elapsed:.0f} 秒，共捕获 {current_total} 行）")

        # 优雅关闭
        conn.stop_background_collection()
        conn.disconnect()
        return 0

    except Exception as e:
        print(f"\n[FAIL] 运行异常: {e}")
        conn.stop_background_collection()
        conn.disconnect()
        return 1


if __name__ == '__main__':
    sys.exit(main())
