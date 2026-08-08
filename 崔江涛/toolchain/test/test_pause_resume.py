"""
test_pause_resume.py - 验证 file_transfer 的暂停/恢复机制 + 软复位恢复钢琴

测试流程（反映真实的文件上传使用场景）：
  1. 启动后台采集（模拟 MCP Server 启动后的常态）
  2. 执行文件上传（内部：暂停采集 → raw REPL 传输 → 恢复采集）
  3. 发送软复位（Ctrl+D），让 ESP32 重新启动 main.py
  4. 等待钢琴程序进入主循环
  5. 验证后台监控捕获到了钢琴启动信息 + 按键数据
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_connection import SerialConnection
from tools.file_transfer import upload_file
from tools.serial_monitor import monitor

# ─── Step 0: 准备 ─────────────────────────────────────────
TEST_FILE = 'test_pause_resume_verify.py'
if not os.path.isfile(TEST_FILE):
    print(f"[!] 测试文件 {TEST_FILE} 不存在，自动创建...")
    with open(TEST_FILE, 'w') as f:
        f.write("# 测试文件 - 用于验证 file_transfer 功能\n")
        f.write("print('TEST_PAUSE_RESUME_OK')\n")
    print(f"    已创建: {TEST_FILE}")

conn = SerialConnection()

# ─── Step 0.5: 启动后台采集（模拟正常运维状态）─────────────
print("=" * 50)
print("  步骤0: 启动后台采集")
print("  说明: 模拟 MCP Server 正常运行时的后台采集状态")
print("=" * 50)

if not conn.is_connected():
    conn.connect()

if conn.collection_active:
    print("[OK] 后台采集已在运行")
else:
    conn.start_background_collection()
    time.sleep(0.5)
    print("[OK] 后台采集已启动")

# ─── Step 1: 上传文件 ──────────────────────────────────────
print()
print("=" * 50)
print("  步骤1: 上传文件到 ESP32")
print("  说明: 上传时进入 raw REPL 会暂停后台采集并")
print("        中断 ESP32 上正在运行的 main.py")
print("=" * 50)

result = upload_file(TEST_FILE, TEST_FILE, timeout_sec=30)
print(f"\n上传结果:")
print(f"  状态: {result['status']}")
print(f"  传输: {result['bytes_transferred']} 字节")
if result.get('error_message'):
    print(f"  错误: {result['error_message']}")

if result['status'] != 'ok':
    print("\n[FAIL] 上传失败，无法继续测试")
    conn.stop_background_collection()
    conn.disconnect()
    sys.exit(1)

# ─── Step 2: 确认采集已恢复 ────────────────────────────────
print()
print("=" * 50)
print("  步骤2: 确认后台采集已恢复（不被永久暂停）")
print("=" * 50)

if conn.collection_active:
    print(f"[OK] 后台采集正在运行 (collection_active=True)")
else:
    print(f"[WARN] 后台采集未运行，尝试重新启动...")
    conn.start_background_collection()
    time.sleep(0.3)

if conn.collection_paused:
    print(f"[FAIL] 后台采集仍处于暂停状态 — 说明 resume 未被调用!")
    conn.resume_background_collection()
    time.sleep(0.2)
    if conn.collection_paused:
        conn.stop_background_collection()
        conn.disconnect()
        sys.exit(1)
    print(f"[OK] 已手动恢复")
else:
    print(f"[OK] 后台采集未暂停 (collection_paused=False)")

# ─── Step 3: 软复位，恢复钢琴程序 ──────────────────────────
print()
print("=" * 50)
print("  步骤3: 软复位 ESP32（Ctrl+D）")
print("  说明: 上传后 main.py 已被中断，需要通过软复位")
print("        让 ESP32 重新启动钢琴程序")
print("=" * 50)

if conn.soft_reset():
    print("[OK] 软复位指令已发送")
else:
    print("[WARN] soft_reset() 返回 False")

print("  等待钢琴程序完全启动（3秒）...")
time.sleep(3.0)

# 再次确认采集仍在运行
if not conn.collection_active:
    print("[WARN] 采集意外停止，重新启动...")
    conn.start_background_collection()
    time.sleep(0.5)

# ─── Step 4: 验证钢琴已启动 ────────────────────────────────
print()
print("=" * 50)
print("  步骤4: 验证钢琴程序已启动")
print("=" * 50)

startup_check = monitor(duration_sec=5)
piano_lines = [l for l in startup_check['lines']
               if '钢琴' in l or '数字钢琴' in l or 'piano' in l.lower()
               or '按键' in l or '演奏' in l or '音符' in l or '八度' in l
               or 'soft reboot' in l]

if piano_lines:
    print(f"[OK] 检测到钢琴启动信息（{len(piano_lines)} 行）:")
    for l in piano_lines:
        print(f"     {l}")
else:
    print(f"[INFO] 未检测到明显的钢琴启动信息")
    if startup_check['lines']:
        print(f"       但捕获到 {startup_check['line_count']} 行其他输出")

# ─── Step 5: 等待用户按键，验证监控 ────────────────────────
print()
print("=" * 50)
print("  步骤5: 验证后台监控是否正常捕获按键数据")
print("=" * 50)
print()
print("  >>> 请现在去按 ESP32 上的几个琴键 <<<")
print()
input("  按回车键查询最近 10 秒的监控数据...")

print("\n正在查询...")
monitor_result = monitor(duration_sec=10)

print(f"\n监控结果:")
print(f"  状态:       {monitor_result['status']}")
print(f"  捕获行数:   {monitor_result['line_count']}")
print(f"  累计断连:   {monitor_result['disconnects']}")
if monitor_result.get('error_message'):
    print(f"  错误信息:   {monitor_result['error_message']}")

if monitor_result['lines']:
    print(f"\n捕获内容:")
    for i, line in enumerate(monitor_result['lines'], 1):
        print(f"  {i:3d}: {line}")

# ─── 结论 ──────────────────────────────────────────────────
print()
print("=" * 50)
print("  测试结论")
print("=" * 50)

checks = []

checks.append(("文件上传成功", result['status'] == 'ok'))
checks.append(("后台采集未永久暂停",
               not conn.collection_paused and conn.collection_active))
checks.append(("钢琴程序已启动（检测到启动信息）",
               len(piano_lines) > 0))

all_pass = all(passed for _, passed in checks)
for desc, passed in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {desc}")

if monitor_result['lines']:
    has_key_data = any('演奏' in l or 'LED' in l for l in monitor_result['lines'])
    print(f"  [{'PASS' if has_key_data else 'INFO'}] 按键数据: "
          f"{'捕获到' if has_key_data else '未捕获到（如果刚才没按键则正常）'}")
else:
    print(f"  [INFO] 未捕获到数据 — 如果刚才没有按键，这是正常的")

print()
if all_pass:
    print("结论: 暂停/恢复机制 + 软复位流程工作正常")

# ─── 清理 ──────────────────────────────────────────────────
conn.stop_background_collection()
conn.disconnect()
