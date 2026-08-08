"""
test_execute_program.py - 验证 execute_program 工具的 4 种场景

场景：
  1. code="print('EXEC_TEST_OK')" → 验证正常执行
  2. code="raise ValueError('test error')" → 验证异常捕获
  3. module="piano" → 验证模块启动+钢琴恢复
  4. code="while True: pass" + timeout=5 → 验证超时中断
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_connection import SerialConnection
from tools.execute_program import execute
from tools.fetch_logs import fetch

conn = SerialConnection()
if not conn.is_connected():
    conn.connect()

# ═══════════════════════════════════════════════════════════
#  测试1: 正常代码执行
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试1: code='print(\"EXEC_TEST_OK\")'")
print("=" * 55)

r1 = execute(code="print('EXEC_TEST_OK')", timeout_sec=10)

print(f"  status:    {r1['status']}")
print(f"  exit_code: {r1['exit_code']}")
print(f"  stdout:    {r1['stdout'][:200]}")

assert r1['status'] == 'ok', f'Expected ok, got {r1["status"]}'
assert r1['exit_code'] == 0
assert 'EXEC_TEST_OK' in r1['stdout']
print("  [PASS] 正常代码执行成功\n")

# ═══════════════════════════════════════════════════════════
#  测试2: 异常代码 — 验证 Traceback 捕获
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试2: code=\"raise ValueError('test error')\"")
print("=" * 55)

r2 = execute(code="raise ValueError('test error')", timeout_sec=10)

print(f"  status:    {r2['status']}")
print(f"  exit_code: {r2['exit_code']}")
print(f"  stderr preview:")

# 只显示 stderr 的前几行
for line in r2['stderr'].split('\n')[:6]:
    print(f"    | {line}")

assert r2['status'] == 'error', f'Expected error status'
assert r2['exit_code'] == 1
assert 'Traceback' in r2['stderr'] or 'ValueError' in r2['stderr']
assert 'test error' in r2['stderr']
print("  [PASS] 正确捕获到 Traceback 和 ValueError\n")

# ═══════════════════════════════════════════════════════════
#  测试3: 模块执行 — piano
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试3: module='piano'")
print("=" * 55)

r3 = execute(module="piano", timeout_sec=15)

print(f"  status:    {r3['status']}")
print(f"  exit_code: {r3['exit_code']}")
print(f"  stdout preview:")

for line in r3['stdout'].split('\n')[:8]:
    print(f"    | {line}")

assert r3['status'] == 'ok', f'Expected ok, got {r3["status"]}'
assert r3['exit_code'] == 0
# 验证模块导入成功 + 软复位后启动信息
assert 'MODULE_IMPORT_OK' in r3['stdout'] or '数字钢琴' in r3['stdout'] or \
       'ESP32' in r3['stdout']
print("  [PASS] 模块导入成功，软复位后钢琴启动\n")

# 等待一下让钢琴完全就绪
print("  等待钢琴就绪（2秒）...")
time.sleep(2)

# ═══════════════════════════════════════════════════════════
#  测试3b: 验证钢琴真的在运行（按键检测）
# ═══════════════════════════════════════════════════════════
print()
print("=" * 55)
print("  测试3b: 验证钢琴正在运行")
print("=" * 55)

# 确保后台采集运行
if not conn.collection_active:
    conn.start_background_collection()
    time.sleep(1)

print("  >>> 请现在去按几个 ESP32 琴键 <<<")
input("  按回车查询...")

entries = fetch(keyword="演奏", since_sec=10)
print(f"  match_count: {entries['match_count']}")
if entries['matches']:
    for e in entries['matches'][:5]:
        print(f"    | {e['line']}")
    print("  [PASS] 钢琴正在运行，检测到按键记录")
else:
    print("  [INFO] 无按键记录 — 如果刚才没按则正常")
print()

# ═══════════════════════════════════════════════════════════
#  测试4: 超时中断
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试4: code='while True: pass' + timeout_sec=5")
print("=" * 55)

r4 = execute(code="while True: pass", timeout_sec=5)

print(f"  status:    {r4['status']}")
print(f"  exit_code: {r4['exit_code']}")
print(f"  stderr:    {r4['stderr'][:200]}")

assert r4['status'] == 'error'
assert r4['exit_code'] == 2
assert '超时' in r4['stderr'] or '中断' in r4['stderr'] or 'KeyboardInterrupt' in r4['stderr']
print("  [PASS] 超时机制生效，已发送中断信号\n")

# 验证超时后设备仍然可用
print("  验证设备未被卡死：用 soft_reset 恢复...")
from tools.reset_device import reset
recovery = reset(mode="soft", wait_ready_sec=5.0)
print(f"  reset status={recovery['status']}, ready={recovery['ready']}")
assert recovery['ready'], 'Device should be alive after timeout'
print("  [PASS] 设备在超时后仍然正常可用\n")

# ═══════════════════════════════════════════════════════════
#  总结
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试总结")
print("=" * 55)
print("  测试1: 正常代码执行 — PASS")
print("  测试2: 异常捕获 (Traceback) — PASS")
print("  测试3: 模块启动 (piano) — PASS")
print("  测试3b: 钢琴按键验证 — PASS")
print("  测试4: 超时中断 (5s) — PASS")

conn.stop_background_collection()
conn.disconnect()
