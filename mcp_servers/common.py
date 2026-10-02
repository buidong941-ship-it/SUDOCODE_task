"""Phần dùng chung cho các MCP server (stdio, mcp Python SDK bản lowlevel để tự khai báo inputSchema).

Mỗi tool trả về đúng một TextContent chứa JSON. Lỗi trong tool → `isError=True` kèm "<TênLỗi>: <thông điệp>",
client (harness/mcp_client.py) đổi lại thành ngoại lệ — giống hệt khi gọi hàm Python trực tiếp.
"""
import asyncio
import inspect
import json
import logging
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import mcp.types as types                       # noqa: E402
from mcp.server.lowlevel import Server           # noqa: E402
from mcp.server.stdio import stdio_server        # noqa: E402

# server chạy dưới dạng tiến trình con: stdout là kênh giao thức, log chỉ được ra stderr
logging.basicConfig(stream=sys.stderr, level=os.environ.get("MCP_LOG_LEVEL", "WARNING"),
                    format="%(asctime)s %(levelname)s %(name)s %(message)s")


def schema_from_signature(fn, types_=None, descriptions=None):
    """JSON Schema cho tham số của `fn`: bắt buộc = tham số không có giá trị mặc định.
    `types_` = {tên: JSON Schema} để ép kiểu; tham số không khai báo kiểu thì nhận mọi giá trị."""
    types_, descriptions = types_ or {}, descriptions or {}
    props, required = {}, []
    for name, p in inspect.signature(fn).parameters.items():
        if name == "self" or p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        sch = dict(types_.get(name, {}))
        if p.default is not inspect.Parameter.empty:
            if "type" in sch and sch["type"] != "null":
                sch["type"] = [sch["type"], "null"] if isinstance(sch["type"], str) else sch["type"] + ["null"]
            if p.default is not None and isinstance(p.default, (str, int, float, bool)):
                sch["default"] = p.default
        else:
            required.append(name)
        if name in descriptions:
            sch["description"] = descriptions[name]
        props[name] = sch
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


def run_server(name, tools, instructions=None):
    """tools = {tên_tool: (hàm, mô tả, inputSchema)} → chạy server stdio cho tới khi client đóng."""
    server = Server(name, instructions=instructions)

    @server.list_tools()
    async def _list():
        return [types.Tool(name=n, description=d, inputSchema=s) for n, (_, d, s) in tools.items()]

    @server.call_tool()
    async def _call(tool, arguments):
        if tool not in tools:            # vd. tool ghi khi mcp-memory chạy chế độ ro
            return types.CallToolResult(isError=True, content=[types.TextContent(
                type="text", text=f"PermissionError: tool {tool} không có hoặc không được phép ở server {name}")])
        fn = tools[tool][0]
        try:
            out = fn(**(arguments or {}))
        except Exception as e:          # trả lỗi về client thay vì làm chết server
            logging.getLogger(name).warning("%s lỗi: %s: %s", tool, type(e).__name__, e)
            return types.CallToolResult(isError=True, content=[types.TextContent(type="text", text=f"{type(e).__name__}: {e}")])
        return [types.TextContent(type="text", text=json.dumps(out, ensure_ascii=False, default=str))]

    async def main():
        async with stdio_server() as (r, w):
            await server.run(r, w, server.create_initialization_options())

    asyncio.run(main())
