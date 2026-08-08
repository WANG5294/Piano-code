"""Error reporting helper for the MCPiano ESP32 toolchain.

Parses recent serial output for MicroPython tracebacks and returns
structured error information.
"""

import re

from tools.serial_monitor import esp32_logs


# Matches a single frame:  File "name", line N, in function [optional code line]
_FRAME_RE = re.compile(
    r'  File "(.+)", line (\d+), in ([^\n]+)(?:\n    ([^\n]+))?\n'
)


def _parse_tracebacks(text: str) -> list[dict]:
    """Parse all MicroPython tracebacks from *text*.

    Returns a list of dicts, each containing ``frames``, ``type``,
    ``message`` and ``raw``.
    """
    results = []
    # Split into potential traceback blocks.
    blocks = re.split(r'(?=Traceback \(most recent call last\):)', text)
    for block in blocks:
        if not block.startswith("Traceback"):
            continue

        frames = [
            {
                "file": file_name,
                "line": int(line_no),
                "function": func,
                "code": code,
            }
            for file_name, line_no, func, code in _FRAME_RE.findall(block)
        ]

        # The exception line is the last line that looks like "Type: message".
        exc_match = re.search(r"\n(\w+): (.+?)(?:\n(?=Traceback|\Z)|\Z)", block, re.DOTALL)
        if not exc_match and frames:
            # Fallback: search anywhere in the block.
            exc_match = re.search(r"(\w+): (.+?)(?:\n|$)", block, re.DOTALL)

        if exc_match:
            results.append(
                {
                    "frames": frames,
                    "type": exc_match.group(1),
                    "message": exc_match.group(2).strip(),
                    "raw": block.strip(),
                }
            )

    return results


async def esp32_error(auto_parse: bool = True) -> dict:
    """Parse recent serial output for MicroPython errors.

    Args:
        auto_parse: If True, automatically detect Traceback blocks.

    Returns:
        Dict with detected error information or a placeholder message.
    """
    logs_result = esp32_logs(lines=200)
    if not logs_result.get("success"):
        return {"success": False, "message": "Failed to retrieve logs"}

    text = "\n".join(logs_result.get("logs", []))

    if not auto_parse:
        return {"success": True, "error": None, "raw_logs": text}

    tracebacks = _parse_tracebacks(text)
    if not tracebacks:
        return {"success": True, "error": None}

    return {"success": True, "error": tracebacks[-1]}
