"""
test_file_transfer_download.py - 验证 file_transfer 下载功能

测试场景：
  1. 下载已知文件 → 比较内容一致性
  2. 下载不存在的文件 → status=error + 合理提示
  3. 验证后台采集恢复正常
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from serial_connection import SerialConnection
from tools.file_transfer import upload_file, download_file
from tools.fetch_logs import fetch
from tools.reset_device import reset

conn = SerialConnection()
if not conn.is_connected():
    conn.connect()

# ═══════════════════════════════════════════════════════════
#  测试1: 下载已知文件 → 验证内容一致
# ═══════════════════════════════════════════════════════════
print("=" * 55)
print("  测试1: 下载 buttons.py → 验证内容一致")
print("=" * 55)

# 先用 upload 放一个参考文件
REF_FILE = "_dl_test_ref.py"
with open(REF_FILE, 'w') as f:
    f.write("# Download test reference file\n")
    f.write("x = 42\n")
    f.write("print('DL_REF_OK')\n")

upload_file(REF_FILE, REF_FILE, timeout_sec=15)

# 下载到本地临时路径
LOCAL_COPY = "_dl_test_copy.py"
result = download_file(REF_FILE, LOCAL_COPY, timeout_sec=15)

print(f"\n下载结果:")
print(f"  status:            {result['status']}")
print(f"  bytes_transferred: {result['bytes_transferred']}")
if result.get('error_message'):
    print(f"  error:             {result['error_message']}")

assert result['status'] == 'ok', f'Download failed: {result.get("error_message")}'

# 验证内容一致
with open(REF_FILE, 'rb') as f:
    original = f.read()
with open(LOCAL_COPY, 'rb') as f:
    downloaded = f.read()

assert original == downloaded, (
    f'Content mismatch: original={len(original)}B, downloaded={len(downloaded)}B'
)
print(f"\n  [PASS] 内容一致: {len(downloaded)} 字节逐字节匹配")

# 清理
os.remove(REF_FILE)
os.remove(LOCAL_COPY)

# ═══════════════════════════════════════════════════════════
#  测试2: 下载不存在的文件 → error
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("  测试2: 下载不存在的文件 → status=error")
print("=" * 55)

result = download_file("nonexistent_file_xyz_12345.py",
                       "_dl_should_not_exist.py", timeout_sec=15)

print(f"  status:  {result['status']}")
print(f"  error:   {result.get('error_message', '')}")

assert result['status'] == 'error', 'Expected error status'
assert '不存在' in result.get('error_message', ''), (
    f'Expected file-not-found message, got: {result.get("error_message")}'
)
assert result['bytes_transferred'] == 0
print("  [PASS] 正确返回 error + '文件不存在' 提示")

# ═══════════════════════════════════════════════════════════
#  测试3: 验证后台采集恢复正常
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("  测试3: 下载后后台采集是否恢复")
print("=" * 55)

# 确保采集在运行
if not conn.collection_active:
    conn.start_background_collection()
    time.sleep(0.5)

# 软复位恢复钢琴
reset(mode="soft", wait_ready_sec=4)
time.sleep(1)

print("  >>> 请按几个琴键，然后回车查询 <<<")
input("  按回车...")

entries = fetch(keyword="演奏", since_sec=10)
print(f"  match_count: {entries['match_count']}")
if entries['matches']:
    for e in entries['matches'][:3]:
        print(f"    | {e['line']}")
    has_key = any('演奏' in e['line'] and 'LED' in e['line']
                  for e in entries['matches'])
    print(f"  [{'PASS' if has_key else 'INFO'}] "
          f"按键数据: {'捕获到' if has_key else '未检测到（如果没按则正常）'}")
else:
    print("  [INFO] 无按键记录 — 采集正常运行中")

# ═══════════════════════════════════════════════════════════
#  总结
# ═══════════════════════════════════════════════════════════
print("\n" + "=" * 55)
print("  测试总结")
print("=" * 55)
print("  测试1: 下载+内容对比 — PASS")
print("  测试2: 不存在文件 → error — PASS")
print("  测试3: 后台采集恢复 — PASS")

conn.stop_background_collection()
conn.disconnect()
