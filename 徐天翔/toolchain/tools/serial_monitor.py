"""Serial monitor for the MCPiano ESP32 toolchain.

Provides asynchronous background monitoring of the ESP32 USB-UART and a
ring buffer for recent log lines.
"""

import asyncio
from collections import deque

import serial


PORT = "/dev/ttyACM0"
BAUDRATE = 115200
TIMEOUT = 0.1

_serial_conn = None
_log_buffer = deque(maxlen=1000)
_monitor_task = None


async def _open_serial():
    """Open the serial port singleton.

    Returns:
        serial.Serial: The opened serial connection.

    Raises:
        serial.SerialException: If the port cannot be opened.
    """
    global _serial_conn
    if _serial_conn is None or not _serial_conn.is_open:
        _serial_conn = serial.Serial(PORT, BAUDRATE, timeout=TIMEOUT)
    return _serial_conn


def _read_line(ser):
    """Read one line from the serial port in a worker thread.

    Args:
        ser: Open serial.Serial instance.

    Returns:
        Decoded line string, or empty string on error/no data.
    """
    try:
        raw = ser.readline()
        if not raw:
            return ""
        return raw.decode("utf-8", errors="replace").rstrip("\r\n")
    except Exception:
        return ""


def append_log(text: str) -> None:
    """Append one or more lines of text to the log ring buffer.

    This lets other tools (e.g. ``esp32_execute``) make captured output
    visible to ``esp32_logs`` and ``esp32_error``.
    """
    for line in text.splitlines():
        if line:
            _log_buffer.append(line)


async def _monitor_loop():
    """Background coroutine that continuously reads serial lines."""
    try:
        ser = await _open_serial()
        while True:
            line = await asyncio.to_thread(_read_line, ser)
            if line:
                _log_buffer.append(line)
    except asyncio.CancelledError:
        raise
    except Exception as exc:
        _log_buffer.append(f"[serial_monitor error] {exc}")
        raise


async def _stop_monitor():
    """Cancel the background monitor task and close the serial port."""
    global _monitor_task
    if _monitor_task:
        _monitor_task.cancel()
        try:
            await _monitor_task
        except asyncio.CancelledError:
            pass
        _monitor_task = None
    if _serial_conn and _serial_conn.is_open:
        await asyncio.to_thread(_serial_conn.close)


async def _start_monitor():
    """Open the serial port and start the background monitor task."""
    global _monitor_task
    if _monitor_task is None or _monitor_task.done():
        _monitor_task = asyncio.create_task(_monitor_loop())


async def pause_monitor() -> dict:
    """Pause the monitor so another tool can use the serial port.

    The log ring buffer is preserved.  Call :func:`resume_monitor` to restart
    background reading afterwards.
    """
    await _stop_monitor()
    return {"success": True, "message": "Serial monitor paused"}


async def resume_monitor() -> dict:
    """Resume the background serial monitor after another tool finishes."""
    await _start_monitor()
    return {"success": True, "message": "Serial monitor resumed"}


async def esp32_serial(action: str, duration: int = 5) -> dict:
    """Control the serial monitor.

    Args:
        action: One of ``"start"``, ``"stop"``, or ``"read"``.
        duration: For ``"read"``, number of seconds to collect output.

    Returns:
        Dict with operation result. ``"read"`` returns collected ``lines``.
    """
    if action == "start":
        await _start_monitor()
        return {"success": True, "message": "Serial monitor started"}

    if action == "stop":
        await _stop_monitor()
        return {"success": True, "message": "Serial monitor stopped"}

    if action == "read":
        if _monitor_task is None or _monitor_task.done():
            await _start_monitor()
        await asyncio.sleep(duration)
        return {"success": True, "lines": list(_log_buffer)}

    return {"success": False, "message": f"Unknown action: {action}"}


def esp32_logs(lines: int = 50, filter_str: str = "") -> dict:
    """Retrieve recent lines from the serial log buffer.

    Args:
        lines: Maximum number of recent lines to return.
        filter_str: If non-empty, only return lines containing this string.

    Returns:
        Dict with ``success`` and ``logs`` keys.
    """
    result = list(_log_buffer)[-lines:]
    if filter_str:
        result = [line for line in result if filter_str in line]
    return {"success": True, "logs": result}
