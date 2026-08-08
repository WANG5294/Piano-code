"""Low-level MicroPython raw-REPL helpers for the MCPiano toolchain.

These synchronous helpers are used by file_transfer, executor and
error_handler.  They assume the caller has already paused the background
serial monitor so that the serial port can be used exclusively.
"""

import time

import serial


PORT = "/dev/ttyACM0"
BAUDRATE = 115200
TIMEOUT = 0.5


class RawReplError(Exception):
    """Raised when raw-REPL interaction fails."""

    def __init__(self, message: str, output: str = ""):
        super().__init__(message)
        self.output = output


def open_serial(timeout: float = TIMEOUT) -> serial.Serial:
    """Open a fresh serial connection to the ESP32."""
    return serial.Serial(PORT, BAUDRATE, timeout=timeout)


def flush(ser: serial.Serial) -> None:
    """Discard any pending incoming bytes."""
    ser.reset_input_buffer()


def enter_raw_repl(ser: serial.Serial) -> None:
    """Enter raw REPL mode.

    Sends Ctrl-C to interrupt any running program, then Ctrl-A to enter raw
    REPL, and waits for the raw-REPL prompt.
    """
    ser.write(b"\x03")  # Ctrl-C: interrupt running program
    time.sleep(0.1)
    ser.write(b"\x01")  # Ctrl-A: enter raw REPL
    # Wait for the raw REPL prompt banner.
    prompt = b"raw REPL; CTRL-B to exit\r\n>"
    data = ser.read_until(prompt)
    if prompt not in data:
        raise RawReplError(
            "Failed to enter raw REPL",
            data.decode("utf-8", errors="replace"),
        )


def exit_raw_repl(ser: serial.Serial) -> None:
    """Exit raw REPL and return to the friendly REPL prompt."""
    ser.write(b"\x02")  # Ctrl-B: exit raw REPL
    time.sleep(0.1)
    # Drain remaining bytes to avoid confusing the serial monitor.
    ser.reset_input_buffer()


def exec_raw(ser: serial.Serial, code: str, timeout: float = 10.0) -> dict:
    """Execute Python code in raw REPL and capture stdout/stderr.

    Args:
        ser: Open serial.Serial instance already in raw REPL mode.
        code: Python source code to execute.
        timeout: Read timeout in seconds for the whole operation.

    Returns:
        Dict with keys ``success``, ``stdout``, ``stderr``.
    """
    original_timeout = ser.timeout
    try:
        ser.timeout = timeout
        ser.write(code.encode("utf-8"))
        ser.write(b"\x04")  # Ctrl-D: execute

        # Wait for the OK acknowledgement.  MicroPython raw REPL sends
        # ``OK`` immediately followed by stdout; there is no CR/LF.
        ok = ser.read_until(b"OK")
        if b"OK" not in ok:
            raise RawReplError(
                "Raw REPL did not acknowledge code execution",
                ok.decode("utf-8", errors="replace"),
            )

        # Read stdout until first EOT (0x04).
        stdout_bytes = ser.read_until(b"\x04")
        if stdout_bytes.endswith(b"\x04"):
            stdout_bytes = stdout_bytes[:-1]

        # Read stderr until second EOT (0x04).
        stderr_bytes = ser.read_until(b"\x04")
        if stderr_bytes.endswith(b"\x04"):
            stderr_bytes = stderr_bytes[:-1]

        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        return {
            "success": len(stderr) == 0,
            "stdout": stdout,
            "stderr": stderr,
        }
    finally:
        ser.timeout = original_timeout


def soft_reset(ser: serial.Serial) -> dict:
    """Perform a soft reset via ``machine.reset()`` in raw REPL.

    Returns:
        The ``exec_raw`` result dict, which typically contains the boot
        messages in ``stdout``.
    """
    enter_raw_repl(ser)
    try:
        result = exec_raw(ser, "import machine\nmachine.reset()\n", timeout=2.0)
        if not result["success"]:
            raise RawReplError("Soft reset failed", result["stderr"])
        return result
    finally:
        # After machine.reset() the board reboots; no need to exit raw REPL.
        pass


def hard_reset(ser: serial.Serial) -> None:
    """Perform a hard reset by toggling DTR/RTS lines.

    This sequence works for the common ESP32 USB-to-UART auto-reset circuit.
    """
    ser.dtr = False
    ser.rts = True
    time.sleep(0.05)
    ser.dtr = True
    ser.rts = False
    time.sleep(0.05)
    ser.dtr = False
    # Give the bootloader and MicroPython time to start.
    time.sleep(0.5)
    ser.reset_input_buffer()
