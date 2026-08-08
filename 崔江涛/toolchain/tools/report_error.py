"""
report_error.py — 错误报告/异常检测工具
==========================================

解析后台采集缓冲区中的 MicroPython 运行时输出，
识别异常信息并生成结构化的诊断报告。

这是 6 项基本能力中的第 6 项（也是最后一项）。
"""

import re
import logging

logger = logging.getLogger(__name__)

# MicroPython 常见异常类型（用于模式匹配）
_KNOWN_EXCEPTIONS = [
    'ValueError', 'TypeError', 'ImportError', 'OSError',
    'SyntaxError', 'AttributeError', 'IndexError', 'KeyError',
    'NameError', 'MemoryError', 'RuntimeError', 'ZeroDivisionError',
    'OverflowError', 'StopIteration', 'IndentationError',
    'KeyboardInterrupt', 'UnicodeError', 'AssertionError',
]

# 匹配 "ExceptionType: message" 格式的行
_EXCEPTION_LINE_RE = re.compile(
    r'^(' + '|'.join(_KNOWN_EXCEPTIONS) + r'):\s*(.*)$'
)

# 匹配 Traceback 开头
_TRACEBACK_HEADER = 'Traceback (most recent call last):'

# 匹配常见的非标准错误行（用于 unclassified 兜底）
_ERROR_KEYWORD_RE = re.compile(r'(Error|Exception|error|exception)', re.IGNORECASE)


def report(context_lines: int = 50) -> dict:
    """
    检查最近的串口输出，识别 MicroPython 异常信息。

    Args:
        context_lines: 检查最近 N 行日志，默认 50

    Returns:
        dict:
            {
                "status": "ok" | "error",
                "errors": [{"type": str, "message": str, "line": str}, ...],
                "has_errors": bool,
                "message": str
            }
    """
    from serial_connection import SerialConnection

    result = {
        'status': 'ok',
        'errors': [],
        'has_errors': False,
        'message': '',
    }

    try:
        conn = SerialConnection()

        if not conn.is_connected():
            result['status'] = 'error'
            result['message'] = '串口未连接，无法检测错误'
            return result

        # ── 获取日志 ──
        entries = conn.get_recent_lines(n=context_lines)
        if not entries:
            result['has_errors'] = False
            result['message'] = '尚未开始监控，暂无缓存数据'
            return result

        lines = [e['line'] for e in entries]

        # ── 解析异常 ──
        errors = _parse_errors(lines)

        if errors:
            result['has_errors'] = True
            result['errors'] = errors
            result['message'] = f'检测到 {len(errors)} 个异常'
        else:
            result['has_errors'] = False
            result['message'] = '未检测到异常，运行状态正常'

        logger.info("report_error: 扫描 %d 行, 发现 %d 个异常",
                    len(lines), len(errors))

        return result

    except Exception as e:
        logger.error("report_error 未预期异常: %s", e, exc_info=True)
        result['status'] = 'error'
        result['message'] = f'错误检测过程发生异常: {str(e)}'
        return result


def _parse_errors(lines: list[str]) -> list[dict]:
    """
    从日志行列表中提取所有异常信息。

    解析策略：
      1. 先扫描 Traceback 块，提取其中的异常信息
      2. 再扫描剩余行（不在 Traceback 块中的），检查是否有
         独立的异常类名+消息行
      3. 最后对仍然看起来像错误的行做 unclassified 兜底

    Returns:
        [{"type": str, "message": str, "line": str}, ...]
    """
    errors = []
    traceback_ranges = _find_traceback_ranges(lines)
    covered = set()  # 已被 Traceback 覆盖的行索引

    # ── 解析 Traceback 块 ──
    for start, end in traceback_ranges:
        for i in range(start, end):
            covered.add(i)

        # Traceback 块的最后一行通常是异常类型和消息
        error_line = ''
        for i in range(end - 1, start - 1, -1):
            stripped = lines[i].strip()
            if stripped and not stripped.startswith('File '):
                error_line = stripped
                break

        if error_line:
            err = _classify_error_line(error_line)
            errors.append(err)

    # ── 扫描独立异常行（不在 Traceback 块中）──
    for i, line in enumerate(lines):
        if i in covered:
            continue
        stripped = line.strip()
        if not stripped:
            continue

        m = _EXCEPTION_LINE_RE.match(stripped)
        if m:
            err = {
                'type': m.group(1),
                'message': m.group(2).strip(),
                'line': line,
            }
            errors.append(err)
            covered.add(i)

    # ── unclassified 兜底 ──
    for i, line in enumerate(lines):
        if i in covered:
            continue
        stripped = line.strip()
        if not stripped:
            continue
        # 包含 Error/Exception 关键字但不是已知格式
        if _ERROR_KEYWORD_RE.search(stripped) and ':' not in stripped.split(' ')[0]:
            # 可能是 "Error: ..." 等变体
            pass  # 不过度匹配，减少误报
        # 对包含 Traceback（但不完整）的行做兜底
        if stripped.startswith('Traceback') and i not in covered:
            errors.append({
                'type': 'unclassified',
                'message': stripped[:200],
                'line': line,
            })

    return errors


def _find_traceback_ranges(lines: list[str]) -> list[tuple[int, int]]:
    """
    找出所有 Traceback 块的起止行号。

    一个 Traceback 块从 "Traceback (most recent call last):" 开始，
    到下一个空行或下一个 Traceback 块开始之前结束。

    Returns:
        [(start_idx, end_idx), ...] 每个元组表示 [start, end) 区间
    """
    ranges = []
    n = len(lines)

    i = 0
    while i < n:
        if lines[i].strip() == _TRACEBACK_HEADER:
            start = i
            # 找 Traceback 块结束位置
            i += 1
            while i < n:
                stripped = lines[i].strip()
                # 结束条件：空行 或 下一个 Traceback 或 正常的日志行
                # 正常日志行不含 "File " 前缀且不是缩进的
                if not stripped:
                    break  # 空行结束
                if stripped == _TRACEBACK_HEADER:
                    break  # 新 Traceback 开始
                if (not stripped.startswith('File ') and
                        not stripped.startswith('  ') and
                        not _is_exception_line(stripped)):
                    # 可能是正常输出混在 traceback 后
                    # 检查：如果这行不像是 traceback 的一部分，结束当前块
                    if not _EXCEPTION_LINE_RE.match(stripped):
                        break
                i += 1
            ranges.append((start, i))
        else:
            i += 1

    return ranges


def _is_exception_line(line: str) -> bool:
    """判断一行是否像异常行（异常类型: 消息）。"""
    return bool(_EXCEPTION_LINE_RE.match(line.strip()))


def _classify_error_line(error_line: str) -> dict:
    """
    将错误行分类为已知异常类型或 unclassified。

    Args:
        error_line: 已清洗的错误行文本

    Returns:
        {"type": str, "message": str, "line": str}
    """
    m = _EXCEPTION_LINE_RE.match(error_line.strip())
    if m:
        return {
            'type': m.group(1),
            'message': m.group(2).strip(),
            'line': error_line,
        }
    else:
        return {
            'type': 'unclassified',
            'message': error_line.strip()[:200],
            'line': error_line,
        }


# ─── 独立测试入口 ───────────────────────────────────────────

if __name__ == '__main__':
    """独立测试错误检测。"""
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(name)s: %(message)s',
    )

    lines_arg = int(sys.argv[1]) if len(sys.argv) > 1 else 50

    print("=" * 50)
    print(f"  ESP32 错误检测 (检查最近 {lines_arg} 行)")
    print("=" * 50)

    result = report(context_lines=lines_arg)

    print(f"\n状态:       {result['status']}")
    print(f"has_errors: {result['has_errors']}")
    print(f"消息:       {result['message']}")

    if result['errors']:
        print(f"\n检测到 {len(result['errors'])} 个异常:")
        for i, e in enumerate(result['errors'], 1):
            print(f"  {i}. [{e['type']}] {e['message']}")
            print(f"     原文: {e['line'][:100]}")
    else:
        print("\n未检测到异常。")
