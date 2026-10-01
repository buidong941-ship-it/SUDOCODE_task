"""Client MCP đồng bộ cho harness (harness viết đồng bộ, mcp SDK là async).

Mỗi server chạy thành một tiến trình con (stdio). Một thread riêng giữ event loop + ClientSession sống suốt tiến trình
harness; `call()` gửi coroutine sang loop đó và chờ kết quả. Kết nối tạo lười theo PID, nên khi `run_eval.py --workers N`
fork tiến trình, mỗi worker tự mở server của mình (trạng thái mock không lẫn giữa các worker).
"""
import asyncio
import atexit
import json
import os
import sys
import threading

from core import log as cclog
from core.config import ROOT, settings

log = cclog.get("mcp")
SERVERS = {"commerce": os.path.join(ROOT, "mcp_servers", "commerce_server.py"),
           "memory": os.path.join(ROOT, "mcp_servers", "memory_server.py")}
_conns = {}


class McpToolError(RuntimeError):
    """Tool trả isError=True; thông điệp dạng '<TênLỗi>: <chi tiết>' như ngoại lệ gốc phía server."""


class McpConnection:
    def __init__(self, name, script, env=None):
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        self.name = name
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self.loop.run_forever, name=f"mcp-{name}", daemon=True)
        self._thread.start()
        self._ready, self._stop, self.session, self.tools = threading.Event(), None, None, []
        params = StdioServerParameters(command=sys.executable, args=[script], cwd=ROOT,
                                       env={**os.environ, "PYTHONPATH": ROOT, **(env or {})})

        async def main():
            # mở và đóng context trong CÙNG một task (yêu cầu của anyio)
            self._stop = asyncio.Event()
            async with stdio_client(params) as (r, w):
                async with ClientSession(r, w) as s:
                    await s.initialize()
                    self.tools = [t.name for t in (await s.list_tools()).tools]
                    self.session = s
                    self._ready.set()
                    await self._stop.wait()

        self._main = asyncio.run_coroutine_threadsafe(main(), self.loop)
        self._main.add_done_callback(lambda _: self._ready.set())
        if not self._ready.wait(settings.mcp_timeout_s) or self.session is None:
            err = self._main.exception() if self._main.done() else TimeoutError(f"MCP {name} không khởi động kịp")
            raise RuntimeError(f"không mở được MCP server {name}: {err!r}")
        log.info("MCP %s sẵn sàng (pid %s): %d tool", name, os.getpid(), len(self.tools))

    def call(self, tool, args):
        fut = asyncio.run_coroutine_threadsafe(self.session.call_tool(tool, args), self.loop)
        res = fut.result(settings.mcp_timeout_s)
        text = "".join(getattr(c, "text", "") for c in res.content)
        if res.isError:
            raise McpToolError(text)
        return json.loads(text) if text else None

    def close(self):
        if self._stop is not None and not self._main.done():
            self.loop.call_soon_threadsafe(self._stop.set)
            try:
                self._main.result(5)
            except Exception:
                pass
        self.loop.call_soon_threadsafe(self.loop.stop)


def connection(name):
    key = (name, os.getpid())
    if key not in _conns:
        _conns[key] = McpConnection(name, SERVERS[name])
    return _conns[key]


@atexit.register
def _close_all():
    for (_, pid), c in list(_conns.items()):
        if pid == os.getpid():
            c.close()
