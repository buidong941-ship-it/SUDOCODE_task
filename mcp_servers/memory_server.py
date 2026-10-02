#!/usr/bin/env python3
"""mcp-memory: đọc/ghi bộ nhớ khách hàng (profile facts, phiên/episodic, báo giá, danh tính đa kênh) qua MCP (stdio).

Bọc `harness/memory.py` (SQLAlchemy: SQLite mặc định, Postgres khi đặt DATABASE_URL). Mọi tool nhận:
- `ns`: namespace (<run_id>:<config>:<scenario_id>) — cùng một DB phục vụ nhiều lần chạy/kịch bản mà không lẫn.
- `read_enabled`: false = cấu hình baseline (không đọc phiên trước, vẫn ghi).

Phân quyền: `MCP_MEMORY_MODE=ro` chỉ mở các tool đọc (vd. giao diện xem dòng thời gian bộ nhớ, QA) — tool ghi không
xuất hiện trong list_tools và gọi vào sẽ bị từ chối. Mặc định `rw` (agent).

    python mcp_servers/memory_server.py        # thường do harness tự khởi động (TOOL_TRANSPORT=mcp)
"""
import inspect
import os

from common import run_server, schema_from_signature

from harness.memory import Memory

READ = {"lookup": "Tìm customer_id theo định danh (kind = phone | zalo_id | fb_id).",
        "status": "Trạng thái hồ sơ: active | merged | deletion_requested.",
        "past_sessions": "Các phiên trước của khách (tóm tắt episodic), cũ → mới; bỏ qua `before_session`.",
        "current_facts": "Fact hiện hành của khách {slot: {value, source, expires_on, expired, session_id}}; "
                         "`include_expired` để thấy cả fact quá TTL.",
        "past_quotes": "Các lần báo giá trước (sku, giá niêm yết, giá cuối, KM, ngày hết KM, ngày báo)."}
WRITE = {"upsert_customer": "Tạo hồ sơ nếu chưa có và gắn thêm định danh [(kind, value)].",
         "set_status": "Đổi trạng thái hồ sơ.",
         "add_session": "Ghi (hoặc ghi đè) tóm tắt một phiên.",
         "log_turn": "Ghi một lượt thoại (working memory) ngay trong cuộc gọi.",
         "write_fact": "Ghi fact profile. Cùng slot khác giá trị → fact cũ thành `superseded` (không xóa). "
                       "Trả bản ghi thay đổi, hoặc null nếu giá trị không đổi.",
         "forget_customer": "Yêu cầu xóa dữ liệu: xóa fact/báo giá/phiên, giữ dấu vết yêu cầu.",
         "add_quote": "Lưu một lần báo giá.",
         "merge_customer": "Gộp hồ sơ tạm `src` vào `dst` (identity resolution).",
         "wipe": "Xóa toàn bộ dữ liệu của namespace (dùng khi bắt đầu chạy lại một kịch bản)."}
TYPES = {"identities_": {"type": "array", "items": {"type": "array", "items": {"type": ["string", "null"]}, "minItems": 2, "maxItems": 2}},
         "blockers": {"type": "array", "items": {"type": "string"}}, "include_expired": {"type": "boolean"},
         "confidence": {"type": "number"}, "turn": {"type": "integer"}}


def _tool(method, ns_desc):
    fn = getattr(Memory, method)

    def call(ns, read_enabled=True, **kw):
        return getattr(Memory(ns, read_enabled=read_enabled), method)(**kw)

    sch = schema_from_signature(fn, TYPES)
    sch["properties"] = {"ns": {"type": "string", "description": ns_desc},
                         "read_enabled": {"type": "boolean", "default": True}, **sch["properties"]}
    sch["required"] = ["ns"] + sch["required"]
    return call, sch


def _tools(mode):
    ns_desc = "namespace <run_id>:<config>:<scenario_id>"
    allowed = dict(READ, **(WRITE if mode == "rw" else {}))
    out = {}
    for method, desc in allowed.items():
        call, sch = _tool(method, ns_desc)
        out[f"memory.{method}"] = (call, desc + ("" if method in READ else " [ghi]"), sch)
    return out


assert all(hasattr(Memory, m) and inspect.isfunction(getattr(Memory, m)) for m in {**READ, **WRITE})

if __name__ == "__main__":
    mode = os.environ.get("MCP_MEMORY_MODE", "rw")
    run_server("mcp-memory", _tools(mode),
               instructions=f"Bộ nhớ khách hàng xuyên phiên/kênh (mode={mode}). Fact có TTL và nguồn gốc (cuộc gọi#lượt).")
