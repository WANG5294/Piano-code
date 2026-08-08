"""MCPiano ESP32 MCP server.

Exposes six hardware-oriented tools to KimiCode over stdio JSON-RPC:
``esp32_upload``, ``esp32_execute``, ``esp32_reset``, ``esp32_serial``,
``esp32_logs``, ``esp32_error``.
"""

import asyncio
import json

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from tools.file_transfer import esp32_upload, esp32_download
from tools.executor import esp32_execute, esp32_reset
from tools.error_handler import esp32_error
from tools.serial_monitor import esp32_serial, esp32_logs


app = Server("mcpiano-esp32")


@app.list_tools()
async def list_tools() -> list[Tool]:
    """Return the list of tools exposed by this server."""
    return [
        Tool(
            name="esp32_upload",
            description="Upload a local file to the ESP32 filesystem.",
            inputSchema={
                "type": "object",
                "properties": {
                    "local_path": {"type": "string"},
                    "remote_path": {"type": "string"},
                },
                "required": ["local_path", "remote_path"],
            },
        ),
        Tool(
            name="esp32_execute",
            description="Execute or stop a MicroPython file on the ESP32.",
            inputSchema={
                "type": "object",
                "properties": {
                    "entry_file": {"type": "string"},
                    "action": {"type": "string", "enum": ["run", "stop"]},
                },
                "required": ["entry_file"],
            },
        ),
        Tool(
            name="esp32_reset",
            description="Soft or hard reset the ESP32 microcontroller.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["soft", "hard"]},
                },
            },
        ),
        Tool(
            name="esp32_serial",
            description="Start, stop, or read the ESP32 serial monitor.",
            inputSchema={
                "type": "object",
                "properties": {
                    "action": {"type": "string", "enum": ["start", "stop", "read"]},
                    "duration": {"type": "integer", "default": 5},
                },
                "required": ["action"],
            },
        ),
        Tool(
            name="esp32_logs",
            description="Retrieve recent lines from the serial log buffer.",
            inputSchema={
                "type": "object",
                "properties": {
                    "lines": {"type": "integer", "default": 50},
                    "filter": {"type": "string", "default": ""},
                },
            },
        ),
        Tool(
            name="esp32_error",
            description="Parse recent serial output for MicroPython errors.",
            inputSchema={
                "type": "object",
                "properties": {
                    "auto_parse": {"type": "boolean", "default": True},
                },
            },
        ),
    ]


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Route incoming tool calls to the appropriate backend function."""
    if name == "esp32_upload":
        result = await esp32_upload(
            arguments.get("local_path", ""),
            arguments.get("remote_path", ""),
        )
    elif name == "esp32_execute":
        result = await esp32_execute(
            arguments.get("entry_file", ""),
            arguments.get("action", "run"),
        )
    elif name == "esp32_reset":
        result = await esp32_reset(arguments.get("mode", "soft"))
    elif name == "esp32_serial":
        result = await esp32_serial(
            arguments.get("action", "read"),
            arguments.get("duration", 5),
        )
    elif name == "esp32_logs":
        result = esp32_logs(
            arguments.get("lines", 50),
            arguments.get("filter", ""),
        )
    elif name == "esp32_error":
        result = await esp32_error(arguments.get("auto_parse", True))
    else:
        result = {"success": False, "message": f"Unknown tool: {name}"}

    return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]


async def main():
    """Run the MCP server over stdio."""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options(),
        )


if __name__ == "__main__":
    asyncio.run(main())
