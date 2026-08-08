"""Program execution and reset helpers for the MCPiano ESP32 toolchain."""

import time

from tools import raw_repl
from tools.serial_monitor import append_log, pause_monitor, resume_monitor


async def esp32_execute(entry_file: str, action: str = "run") -> dict:
    """Execute or stop a MicroPython file on the ESP32.

    Args:
        entry_file: Name of the file to execute on the ESP32.
        action: One of ``"run"`` or ``"stop"``.

    Returns:
        Dict with ``success`` and ``message`` keys.
    """
    if action == "stop":
        await pause_monitor()
        try:
            ser = raw_repl.open_serial(timeout=raw_repl.TIMEOUT)
            try:
                ser.write(b"\x03")  # Ctrl-C: interrupt running program
                time.sleep(0.1)
                return {"success": True, "message": "Sent Ctrl-C to ESP32"}
            finally:
                ser.close()
        finally:
            await resume_monitor()

    if action != "run":
        return {"success": False, "message": f"Unknown action: {action}"}

    await pause_monitor()
    try:
        ser = raw_repl.open_serial(timeout=raw_repl.TIMEOUT)
        try:
            raw_repl.enter_raw_repl(ser)
            code = f"exec(open({entry_file!r}).read())\n"
            result = raw_repl.exec_raw(ser, code)
            raw_repl.exit_raw_repl(ser)

            # Make captured output available to esp32_logs / esp32_error.
            if result.get("stdout"):
                append_log(result["stdout"])
            if result.get("stderr"):
                append_log(result["stderr"])

            if not result["success"]:
                return {
                    "success": False,
                    "message": f"Execution failed: {result['stderr']}",
                }
            return {
                "success": True,
                "message": f"Executed {entry_file}",
                "output": result["stdout"],
            }
        finally:
            ser.close()
    finally:
        await resume_monitor()


async def esp32_reset(mode: str = "soft") -> dict:
    """Reset the ESP32 microcontroller.

    Args:
        mode: ``"soft"`` for a software reset via REPL, ``"hard"`` for
            toggling DTR/RTS lines.

    Returns:
        Dict with ``success`` and ``message`` keys.
    """
    await pause_monitor()
    try:
        ser = raw_repl.open_serial(timeout=raw_repl.TIMEOUT)
        try:
            if mode == "soft":
                result = raw_repl.soft_reset(ser)
                if result.get("stdout"):
                    append_log(result["stdout"])
                return {"success": True, "message": "Soft reset triggered"}
            if mode == "hard":
                raw_repl.hard_reset(ser)
                return {"success": True, "message": "Hard reset triggered"}
            return {"success": False, "message": f"Unknown reset mode: {mode}"}
        finally:
            # After a reset the serial port may briefly disconnect; close
            # cleanly to avoid errors.
            try:
                ser.close()
            except Exception:
                pass
    finally:
        # Give MicroPython time to boot before resuming the monitor so that
        # the boot messages are captured.
        time.sleep(0.5)
        await resume_monitor()
