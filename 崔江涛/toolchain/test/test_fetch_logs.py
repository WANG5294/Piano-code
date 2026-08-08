"""
test_fetch_logs.py - 验证 fetch_logs 的四种过滤场景

测试前需要：
  1. ESP32 已连接，钢琴程序正在运行
  2. 后台采集已启动
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_connection import SerialConnection
from tools.fetch_logs import fetch

# ─── 准备：确保连接和采集就绪 ──────────────────────────────
conn = SerialConnection()
if not conn.is_connected():
    conn.connect()
if not conn.collection_active:
    conn.start_background_collection()
    time.sleep(0.5)

print("=" * 55)
print("  fetch_logs 功能验证")
print("=" * 55)

# ═══════════════════════════════════════════════════════════
#  测试1: 无参数查询（返回已有数据）
# ═══════════════════════════════════════════════════════════
print("\n" + "─" * 55)
print("  测试1: 无参数 — 返回缓冲区全部已有数据")
print("─" * 55)

r1 = fetch()

print(f"  total_cached: {r1['total_cached']}")
print(f"  match_count:  {r1['match_count']}")
print(f"  message:      {r1['message']}")
print(f"  status:       {r1['status']}")

# 显示前5行预览
if r1['matches']:
    print(f"  预览 (前5行):")
    for i, e in enumerate(r1['matches'][:5], 1):
        ts = time.strftime('%H:%M:%S', time.localtime(e['timestamp']))
        print(f"    {i}: [{ts}] {e['line'][:60]}")
    print(f"  [PASS] 无参数查询成功，返回 {r1['match_count']} 行")
else:
    print(f"  [INFO] 缓冲区为空（钢琴可能未运行），请先按几个琴键再测")

# ═══════════════════════════════════════════════════════════
#  测试2: keyword="演奏"
# ═══════════════════════════════════════════════════════════
print("\n" + "─" * 55)
print("  测试2: keyword='演奏' — 只返回按键记录")
print("  >>> 请现在去按几个琴键（生成'演奏'日志）<<<")
print("─" * 55)
input("  按回车继续...")

r2 = fetch(keyword="演奏")

print(f"  match_count:  {r2['match_count']}")
print(f"  message:      {r2['message']}")

if r2['matches']:
    print(f"  匹配内容:")
    for i, e in enumerate(r2['matches'], 1):
        ts = time.strftime('%H:%M:%S', time.localtime(e['timestamp']))
        print(f"    {i:2d}: [{ts}] {e['line']}")

    # 验证：所有匹配行都包含"演奏"
    all_contain = all('演奏' in e['line'] for e in r2['matches'])
    print(f"  [{'PASS' if all_contain else 'FAIL'}] "
          f"所有匹配行都包含'演奏': {all_contain}")

    # 验证：不应该包含启动横幅
    has_banner = any('ESP32' in e['line'] for e in r2['matches'])
    print(f"  [{'PASS' if not has_banner else 'INFO'}] "
          f"过滤掉了启动横幅: {not has_banner}")
else:
    print(f"  [INFO] 无匹配 — 如果刚才没按键则正常")

# ═══════════════════════════════════════════════════════════
#  测试3: 不存在的关键字
# ═══════════════════════════════════════════════════════════
print("\n" + "─" * 55)
print("  测试3: keyword='xyz_not_exist_12345' — 验证无匹配提示")
print("─" * 55)

r3 = fetch(keyword="xyz_not_exist_12345")

print(f"  total_cached: {r3['total_cached']}")
print(f"  match_count:  {r3['match_count']}")
print(f"  message:      {r3['message']}")
print(f"  status:       {r3['status']}")

# 验证点
no_match = r3['match_count'] == 0
has_help = '调整过滤条件' in r3['message'] or '未找到' in r3['message']
print(f"  [{'PASS' if no_match else 'FAIL'}] match_count=0: {no_match}")
print(f"  [{'PASS' if has_help else 'FAIL'}] 提示信息合理: {has_help}")
print(f"  [{'PASS' if r3['status'] == 'ok' else 'FAIL'}] status=ok: {r3['status']}")

# ═══════════════════════════════════════════════════════════
#  测试4: since_sec 时间过滤
# ═══════════════════════════════════════════════════════════
print("\n" + "─" * 55)
print("  测试4: since_sec=5 — 验证时间过滤")
print("  流程: 按几个键 → 等待6秒 → 按几个新键 → 查询最近5秒")
print("─" * 55)

print("  [第1轮] 请按几个琴键，然后等待提示...")
input("  按回车开始第2轮前等待...")
print("  等待 6 秒（让第1轮的按键超过5秒时间窗口）...")
for i in range(6, 0, -1):
    print(f"    {i}...", end='', flush=True)
    time.sleep(1)
print()

print("  [第2轮] 现在再按几个琴键（这些应该出现在结果中）")
input("  按完键后按回车立即查询...")

r4 = fetch(since_sec=5)

print(f"\n  match_count:  {r4['match_count']}")
print(f"  message:      {r4['message']}")

if r4['matches']:
    print(f"  最近5秒内的数据:")
    for i, e in enumerate(r4['matches'], 1):
        ts = time.strftime('%H:%M:%S', time.localtime(e['timestamp']))
        print(f"    {i:2d}: [{ts}] {e['line']}")

    # 验证：所有结果的时间戳应该在最近5秒内
    now = time.time()
    all_recent = all((now - e['timestamp']) <= 6.0 for e in r4['matches'])
    print(f"  [{'PASS' if all_recent else 'FAIL'}] "
          f"所有结果在最近5秒窗口内: {all_recent}")

    # 验证：should see fewer lines than without filter
    r_all = fetch()
    filtered_less = r4['match_count'] <= r_all['match_count']
    print(f"  [{'PASS' if filtered_less else 'INFO'}] "
          f"时间过滤后行数 ≤ 全量行数: {filtered_less}")
else:
    print(f"  [INFO] 最近5秒内无数据 — 如果第2轮没按键则正常")

# ═══════════════════════════════════════════════════════════
#  测试5: 组合过滤 (keyword + since_sec + max_lines)
# ═══════════════════════════════════════════════════════════
print("\n" + "─" * 55)
print("  测试5: 组合过滤 — keyword='演奏' + since_sec=30 + max_lines=5")
print("─" * 55)

r5 = fetch(keyword="演奏", since_sec=30, max_lines=5)

print(f"  total_cached: {r5['total_cached']}")
print(f"  match_count:  {r5['match_count']}")
print(f"  message:      {r5['message']}")

# 验证 max_lines 截断
within_limit = r5['match_count'] <= 5
all_contain_kw = all('演奏' in e['line'].lower() for e in r5['matches'])

print(f"  [{'PASS' if within_limit else 'FAIL'}] "
      f"结果不超过 max_lines=5: {within_limit}")
print(f"  [{'PASS' if all_contain_kw else 'FAIL'}] "
      f"所有结果包含'演奏': {all_contain_kw}")

# ═══════════════════════════════════════════════════════════
#  总结
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("  测试完成")
print("=" * 55)

# 清理
conn.stop_background_collection()
conn.disconnect()
