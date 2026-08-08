"""File transfer helpers for the MCPiano ESP32 toolchain.

Uploads and downloads files via the MicroPython raw REPL protocol using
base64-encoded chunks so that binary content is transferred safely.
"""

import base64
import os
from pathlib import Path

from tools import raw_repl
from tools.serial_monitor import pause_monitor, resume_monitor


CHUNK_SIZE = 256


async def esp32_upload(local_path: str, remote_path: str) -> dict:
    """Upload a local file to the ESP32 filesystem.

    Args:
        local_path: Path to the file on the host computer.
        remote_path: Destination path on the ESP32 filesystem.

    Returns:
        Dict with ``success`` and ``message`` keys.
    """
    local = Path(local_path)
    if not local.exists():
        return {"success": False, "message": f"Local file not found: {local_path}"}

    await pause_monitor()
    try:
        content = local.read_bytes()
        ser = raw_repl.open_serial(timeout=raw_repl.TIMEOUT)
        try:
            raw_repl.enter_raw_repl(ser)

            # Truncate/create the remote file.
            create_cmd = f"open({remote_path!r}, 'wb').close()\n"
            result = raw_repl.exec_raw(ser, create_cmd)
            if not result["success"]:
                return {
                    "success": False,
                    "message": f"Failed to create remote file: {result['stderr']}",
                }

            # Write chunks.
            encoded = base64.b64encode(content).decode("ascii")
            for i in range(0, len(encoded), CHUNK_SIZE):
                chunk = encoded[i : i + CHUNK_SIZE]
                append_cmd = (
                    f"import ubinascii\n"
                    f"with open({remote_path!r}, 'ab') as f:\n"
                    f"    f.write(ubinascii.a2b_base64({chunk!r}))\n"
                )
                result = raw_repl.exec_raw(ser, append_cmd)
                if not result["success"]:
                    return {
                        "success": False,
                        "message": f"Failed to write chunk {i // CHUNK_SIZE}: {result['stderr']}",
                    }

            raw_repl.exit_raw_repl(ser)
            return {
                "success": True,
                "message": f"Uploaded {local_path} -> {remote_path}",
                "bytes": len(content),
            }
        finally:
            ser.close()
    finally:
        await resume_monitor()


async def esp32_download(remote_path: str, local_path: str) -> dict:
    """Download a file from the ESP32 filesystem.

    Args:
        remote_path: Source path on the ESP32 filesystem.
        local_path: Path to save the file on the host computer.

    Returns:
        Dict with ``success`` and ``message`` keys.
    """
    await pause_monitor()
    try:
        ser = raw_repl.open_serial(timeout=raw_repl.TIMEOUT)
        try:
            raw_repl.enter_raw_repl(ser)

            read_cmd = (
                f"import ubinascii\n"
                f"with open({remote_path!r}, 'rb') as f:\n"
                f"    print(ubinascii.b2a_base64(f.read()).decode())\n"
            )
            result = raw_repl.exec_raw(ser, read_cmd)
            raw_repl.exit_raw_repl(ser)

            if not result["success"]:
                return {
                    "success": False,
                    "message": f"Failed to read remote file: {result['stderr']}",
                }

            b64_data = "".join(result["stdout"].split())
            data = base64.b64decode(b64_data)

            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
            Path(local_path).write_bytes(data)
            return {
                "success": True,
                "message": f"Downloaded {remote_path} -> {local_path}",
                "bytes": len(data),
            }
        finally:
            ser.close()
    finally:
        await resume_monitor()
