"""
fetch_logs.py — 运行日志检索工具
==================================

从后台采集缓冲区中按关键字和时间范围检索日志行。
这是 serial_monitor 的"查询增强版"——底层复用同一个缓冲区和
get_recent_lines() 方法，逻辑层增加关键字过滤。

过滤策略全部在工具层实现，serial_connection.py 保持职责单一
（只负责存储和基础时间/数量检索，不涉及业务过滤逻辑）。
"""

import logging

logger = logging.getLogger(__name__)


def fetch(keyword: str | None = None,
          since_sec: float | None = None,
          max_lines: int = 100) -> dict:
    """
    从后台采集缓冲区中检索日志。

    过滤顺序：
      1. 获取全部缓冲区数据 → total_cached
      2. since_sec 过滤（时间窗口）→ 在 get_recent_lines 层完成
      3. keyword 过滤（大小写不敏感子串匹配）
      4. max_lines 截断（取最新的 max_lines 条）
      5. 组装消息

    Args:
        keyword: 关键字，只返回包含此关键字的行（不区分大小写）。
                 None 或空字符串表示不做关键字过滤。
        since_sec: 只检索最近 N 秒内的日志。
                   None 表示不限制时间范围。
        max_lines: 最多返回多少行。匹配结果超过此数时，
                   保留最新的 max_lines 条。默认 100。

    Returns:
        dict:
            {
                "status": "ok" | "error",
                "matches": [{"timestamp": float, "line": str}, ...],
                "match_count": int,       # 过滤后匹配的行数
                "total_cached": int,      # 缓冲区中总行数（过滤前）
                "message": str            # 辅助说明信息
            }
    """
    from serial_connection import SerialConnection

    result = {
        'status': 'ok',
        'matches': [],
        'match_count': 0,
        'total_cached': 0,
        'message': '',
    }

    try:
        conn = SerialConnection()

        if not conn.is_connected():
            result['status'] = 'error'
            result['message'] = '串口未连接，无法检索日志'
            return result

        # ── Step 1: 获取全部缓冲区数据 + total_cached ──
        # 先统计总数（不过滤任何条件）
        all_entries = conn.get_recent_lines()
        total_cached = len(all_entries)
        result['total_cached'] = total_cached

        # ── Step 2: 时间过滤（委托给 get_recent_lines）──
        if since_sec is not None:
            entries = conn.get_recent_lines(since_sec=since_sec)
        else:
            entries = all_entries

        # ── Step 3: 关键字过滤 ──
        if keyword and keyword.strip():
            kw = keyword.strip().lower()
            entries = [e for e in entries if kw in e['line'].lower()]

        # ── Step 4: 截断（取最新的 max_lines 条）──
        if len(entries) > max_lines:
            entries = entries[-max_lines:]

        result['matches'] = entries
        result['match_count'] = len(entries)

        # ── Step 5: 组装消息 ──
        if total_cached == 0:
            result['message'] = '尚未开始监控，暂无缓存数据'
        elif result['match_count'] == 0:
            result['message'] = '未找到匹配的日志，请调整过滤条件'
        else:
            parts = [f'找到 {result["match_count"]} 条匹配']
            if keyword:
                parts.append(f'(关键字: "{keyword}")')
            if since_sec is not None:
                parts.append(f'(时间范围: 最近 {since_sec} 秒)')
            if result['match_count'] > max_lines:
                parts.append(f'(已截断至 {max_lines} 条)')
            result['message'] = '，'.join(parts)

        logger.info("fetch_logs: total_cached=%d, match_count=%d, "
                    "keyword=%r, since_sec=%s",
                    total_cached, result['match_count'], keyword, since_sec)

        return result

    except Exception as e:
        logger.error("fetch_logs 未预期异常: %s", e, exc_info=True)
        result['status'] = 'error'
        result['message'] = f'检索过程发生异常: {str(e)}'
        return result


# ─── 独立测试入口 ───────────────────────────────────────────

if __name__ == '__main__':
    """
    独立测试 fetch_logs 工具。

    用法：
        cd toolchain
        python tools/fetch_logs.py [keyword] [since_sec] [max_lines]

    示例：
        python tools/fetch_logs.py                    # 查看所有日志
        python tools/fetch_logs.py 演奏               # 只看按键记录
        python tools/fetch_logs.py 演奏 10            # 最近10秒内的按键记录
        python tools/fetch_logs.py "" 30 50           # 最近30秒，最多50条
    """
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(name)s: %(message)s',
    )

    # ── 自动确保后台采集在运行 ──
    from serial_connection import SerialConnection
    conn = SerialConnection()
    if not conn.is_connected():
        print("[!] 串口未连接，正在连接 COM3...")
        if not conn.connect():
            print("[FAIL] 无法连接 COM3，请检查 ESP32 是否已接入")
            sys.exit(1)
        print("[OK] 已连接 COM3")
    if not conn.collection_active:
        print("[!] 后台采集未运行，正在启动...")
        if not conn.start_background_collection():
            print("[FAIL] 后台采集启动失败")
            sys.exit(1)
        # 新启动的采集需要等一会儿才有数据
        import time
        print("  等待缓冲区填充（2秒）...")
        time.sleep(2)
        print("[OK] 后台采集已启动")
    # ─────────────────────────────────────

    kw = sys.argv[1] if len(sys.argv) > 1 and sys.argv[1] else None
    sec = float(sys.argv[2]) if len(sys.argv) > 2 and sys.argv[2] else None
    ml = int(sys.argv[3]) if len(sys.argv) > 3 else 100

    print()
    print("=" * 50)
    print("  ESP32 日志检索")
    print(f"  keyword={kw!r}, since_sec={sec}, max_lines={ml}")
    print("=" * 50)

    result = fetch(keyword=kw, since_sec=sec, max_lines=ml)

    print(f"\n状态:      {result['status']}")
    print(f"缓冲区:    {result['total_cached']} 行")
    print(f"匹配:      {result['match_count']} 行")
    print(f"消息:      {result['message']}")
    print(f"\n匹配内容:")
    if result['matches']:
        for i, entry in enumerate(result['matches'], 1):
            ts_str = entry.get('timestamp', 0)
            if isinstance(ts_str, (int, float)):
                import time
                ts_str = time.strftime('%H:%M:%S', time.localtime(ts_str))
            print(f"  {i:3d}: [{ts_str}] {entry['line']}")
    else:
        print("  (无匹配)")
