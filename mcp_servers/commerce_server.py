#!/usr/bin/env python3
"""mcp-commerce: CRM + catalog + tồn kho + giá/KM + đơn hàng + hẹn gọi lại + chuyển máy, qua MCP (stdio).

Logic là `eval/mock_tools.py` của BTC (logic tham chiếu) — server chỉ đóng gói, không sửa kết quả.
Tên tool và tham số đúng `schemas/tools.schema.json`; kiểu dữ liệu lấy từ file đó nên server tự từ chối lời gọi
sai kiểu (MCP SDK kiểm inputSchema trước khi chạy tool).

Trạng thái runtime của mock (đơn mới, lịch gọi lại, ticket, KM 1 lần/khách) sống trong tiến trình server;
`world.reset` xóa nó khi harness chuyển sang kịch bản mới. Mỗi tiến trình harness có server riêng → không lẫn trạng thái.

    python mcp_servers/commerce_server.py      # thường do harness tự khởi động (TOOL_TRANSPORT=mcp)
"""
import importlib.util
import json
import os
import re

from common import ROOT, run_server, schema_from_signature

BTC_DIR = os.environ.get("BTC_DIR") or ROOT
_spec = importlib.util.spec_from_file_location("mock_tools", os.path.join(BTC_DIR, "eval", "mock_tools.py"))
mt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mt)


def _json_type(spec):
    """'string?' / 'int' / 'COD|bank' / 'date?' (… ghi chú) → JSON Schema."""
    s = re.sub(r"\s*\(.*\)$", "", str(spec)).strip().rstrip("?").strip()
    if "|" in s:
        return {"type": "string", "enum": s.split("|")}
    return {"string": {"type": "string"}, "int": {"type": "integer"}, "boolean": {"type": "boolean"},
            "array": {"type": "array"}, "date": {"type": "string", "format": "date"},
            "datetime": {"type": "string"}}.get(s, {"type": "object"} if s[:1].isupper() else {})


def _tools():
    spec = {t["name"]: t for t in json.load(open(os.path.join(ROOT, "schemas", "tools.schema.json"), encoding="utf-8"))["tools"]}
    out = {}
    for name, fn in mt.TOOLS.items():
        s = spec.get(name, {})
        types_ = {k: _json_type(v) for k, v in (s.get("input") or {}).items()}
        types_.setdefault("on", {"type": "string", "format": "date"})
        desc = (s.get("description") or name) + (f" [{s['level']}]" if s.get("level") else "")
        out[name] = (fn, desc, schema_from_signature(fn, types_))

    def reset():
        """Xóa trạng thái runtime của mock (giữa các kịch bản)."""
        mt._ORDERS.clear(); mt._CALLBACKS.clear(); mt._TICKETS.clear(); mt._ONCE_USED.clear()
        return {"ok": True}
    out["world.reset"] = (reset, "Nội bộ harness: xóa đơn/lịch/ticket/KM đã dùng của lần chạy trước (không phải tool cho khách).",
                          {"type": "object", "properties": {}, "additionalProperties": False})
    return out


if __name__ == "__main__":
    run_server("mcp-commerce", _tools(),
               instructions="Tool nghiệp vụ bán hàng. Giá/KM/tồn kho luôn lấy từ đây, không tự suy ra. Mọi tool nhận `on` = ngày cuộc gọi.")
