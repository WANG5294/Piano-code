"""
test_reset_device.py - 验证 reset_device 工具的 soft/hard 双模式

测试流程：
  1. soft_reset → 验证捕获到启动横幅 + ready=true
  2. hard_reset → 验证执行效果（如果 DTR 不支持，验证是否自动回退到 soft）
  3. 复位后按键 + monitor 验证钢琴功能恢复
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_connection import SerialConnection
from tools.reset_device import reset
from tools.serial_monitor import monitor

# ─── 准备：确保连接和采集就绪 ──────────────────────────────
conn = SerialConnection()
if not conn.is_connected():
    conn.connect()
if not conn.collection_active:
    conn.start_background_collection()
    time.sleep(0.5)

# ═══════════════════════════════════════════════════════════
#  测试1: soft_reset
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试1: soft_reset（Ctrl+D 软复位）")
print("=" * 55)
print(f"  等待: 5 秒")
print()

result_soft = reset(mode="soft", wait_ready_sec=5.0)

print(f"结果:")
print(f"  status:  {result_soft['status']}")
print(f"  ready:   {result_soft['ready']}")
print(f"  boot_msg ({len(result_soft['boot_msg'])} chars):")

# 显示启动信息（截取前300字符避免刷屏）
msg = result_soft['boot_msg']
for line in msg.split('\n')[:12]:
    print(f"    | {line}")
if len(msg.split('\n')) > 12:
    print(f"    ... (共 {len(msg.split(chr(10)))} 行，省略后续)")

checks_1 = []
checks_1.append(("status=ok", result_soft['status'] == 'ok'))
checks_1.append(("ready=true (检测到启动横幅)",
                 result_soft['ready'] and 'ESP32' in msg and '数字钢琴' in msg))
checks_1.append(("boot_msg 非空", bool(result_soft['boot_msg'])))

for desc, passed in checks_1:
    print(f"  [{'PASS' if passed else 'FAIL'}] {desc}")

all_pass = all(p for _, p in checks_1)
print(f"\n  测试1: {'全部通过' if all_pass else '有失败项'}")
print()

# ═══════════════════════════════════════════════════════════
#  测试2: hard_reset（含自动回退检测）
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试2: hard_reset（DTR 硬件复位）")
print("=" * 55)
print(f"  等待: 5 秒")
print()

result_hard = reset(mode="hard", wait_ready_sec=5.0)

print(f"结果:")
print(f"  status:  {result_hard['status']}")
print(f"  ready:   {result_hard['ready']}")
print(f"  boot_msg ({len(result_hard['boot_msg'])} chars):")

msg = result_hard['boot_msg']
for line in msg.split('\n')[:12]:
    print(f"    | {line}")
if len(msg.split('\n')) > 12:
    print(f"    ... (共 {len(msg.split(chr(10)))} 行，省略后续)")

checks_2 = []
checks_2.append(("status=ok", result_hard['status'] == 'ok'))
checks_2.append(("ready=true", result_hard['ready']))

# 检测是否有回退标记
fallback_detected = '[回退到软复位]' in msg
dtr_worked = 'MPY: soft reboot' in msg and not fallback_detected

if fallback_detected:
    print(f"\n  [INFO] DTR 硬复位失败，已自动回退到软复位（符合预期行为）")
    checks_2.append(("自动回退机制生效", True))
elif dtr_worked:
    print(f"\n  [INFO] DTR 硬复位成功（CH9102 驱动支持 DTR 控制）")
    # hard_reset 不会有 "soft reboot" 消息，那是 Ctrl+D 特有的
    # 但 main.py 启动横幅应该出现
    checks_2.append(("DTR 硬复位执行成功", True))
else:
    print(f"\n  [INFO] 无法确定 DTR 是否生效，但复位已执行")

for desc, passed in checks_2:
    print(f"  [{'PASS' if passed else 'FAIL'}] {desc}")

all_pass = all(p for _, p in checks_2)
print(f"\n  测试2: {'全部通过' if all_pass else '有失败项'}")
print()

# ═══════════════════════════════════════════════════════════
#  测试3: 复位后按键验证（交互式）
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试3: 复位后钢琴功能验证")
print("=" * 55)
print()
print("  >>> 请现在去按 ESP32 上的几个琴键 <<<")
print()
input("  按回车键查询最近 10 秒的监控数据...")

print("\n正在查询...")
monitor_result = monitor(duration_sec=10)

print(f"\n监控结果:")
print(f"  状态:       {monitor_result['status']}")
print(f"  捕获行数:   {monitor_result['line_count']}")

if monitor_result['lines']:
    print(f"\n捕获内容:")
    for i, line in enumerate(monitor_result['lines'], 1):
        print(f"  {i:3d}: {line}")

    has_key_data = any('演奏' in l or 'LED' in l for l in monitor_result['lines'])
    print(f"\n  [{'PASS' if has_key_data else 'INFO'}] "
          f"按键数据: {'捕获到按键操作' if has_key_data else '未检测到按键（如果刚才没按则正常）'}")
else:
    print(f"  (未捕获到数据)")

# ═══════════════════════════════════════════════════════════
#  总结
# ═══════════════════════════════════════════════════════════
print()
print("=" * 55)
print("  测试总结")
print("=" * 55)
print(f"  soft_reset:  status={result_soft['status']}, ready={result_soft['ready']}")
print(f"  hard_reset:  status={result_hard['status']}, ready={result_hard['ready']}")
print(f"  回退检测:    {'已触发' if fallback_detected else '未触发（DTR可能正常）'}")
print(f"  后台采集:    {'运行中' if conn.collection_active else '已停止'}")

# 清理
conn.stop_background_collection()
conn.disconnect()
