#!/usr/bin/env python3
"""Kiểm tra hai MCP server qua đúng giao thức (client MCP thật, stdio):

1. mcp-commerce có đủ tool trong schemas/tools.schema.json, đúng tên; tham số bắt buộc khớp.
2. Server từ chối lời gọi sai kiểu / thiếu tham số bắt buộc (inputSchema được thực thi).
3. Kết quả tool qua MCP == gọi eval/mock_tools.py trực tiếp (một vài lời gọi đại diện).
4. mcp-memory: ghi → đọc lại được; khách đổi ý → fact cũ superseded; chế độ MCP_MEMORY_MODE=ro không có tool ghi.

    python tests/mcp_check.py
"""
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/mcp_check.db")

from harness.mcp_client import SERVERS, McpConnection, McpToolError  # noqa: E402
from harness.tools import mt                                         # noqa: E402

ok = True


def check(cond, msg):
    global ok
    print(("  OK  " if cond else "  SAI ") + msg)
    ok &= bool(cond)


print("mcp-commerce")
com = McpConnection("commerce", SERVERS["commerce"])
spec = {t["name"]: t for t in json.load(open(os.path.join(ROOT, "schemas", "tools.schema.json"), encoding="utf-8"))["tools"]
        if not t["name"].startswith("memory.")}       # "memory.read / memory.write": BTC để nhóm tự thiết kế → mcp-memory
check(set(spec) <= set(com.tools), f"đủ {len(spec)} tool nghiệp vụ BTC: thiếu {sorted(set(spec) - set(com.tools)) or 'không'}")
for bad_args, why in (({"sku": 123}, "sku sai kiểu"), ({}, "thiếu sku"), ({"sku": "SKU-AP-X", "xyz": 1}, "tham số lạ")):
    try:
        com.call("inventory.check", bad_args); check(False, f"từ chối inventory.check ({why})")
    except McpToolError as e:
        check("validation" in str(e).lower(), f"từ chối inventory.check ({why}): {str(e)[:70]}")
try:
    com.call("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-X", "payment": "tien_mat"})
    check(False, "từ chối payment ngoài enum")
except McpToolError as e:
    check("validation" in str(e).lower(), "từ chối payment ngoài enum COD|bank|momo|zalopay")
com.call("world.reset", {})
for name, args in (("pricing.get_quote", {"sku": "SKU-AP-X", "on": "2026-10-15", "customer_phone": "0984726714"}),
                   ("inventory.check", {"sku": "SKU-AP-MINI", "on": "2026-10-15"}),
                   ("crm.get_customer", {"phone": "0984726714"}),
                   ("catalog.search", {"category": "gia-dung/may-loc-khong-khi"})):
    direct = json.loads(json.dumps(mt.TOOLS[name](**args), ensure_ascii=False, default=str))
    check(com.call(name, args) == direct, f"{name} qua MCP == gọi trực tiếp")
r = com.call("order.create", {"customer_phone": "0984726714", "sku": "SKU-AP-X", "price_vnd": 1, "on": "2026-10-15"})
check(r.get("error") == "price_mismatch", "order.create sai giá → price_mismatch (logic mock giữ nguyên)")
com.close()

print("mcp-memory (rw)")
mem = McpConnection("memory", SERVERS["memory"])
ns = {"ns": "check:full:X", "read_enabled": True}
mem.call("memory.wipe", ns)
mem.call("memory.upsert_customer", {**ns, "customer_id": "C1", "name": "Hoa", "phone": "0984726714",
                                    "identities_": [["phone", "0984726714"], ["zalo_id", "z1"]]})
check(mem.call("memory.lookup", {**ns, "kind": "zalo_id", "value": "z1"}) == ["C1"], "nhận diện qua Zalo ID")
mem.call("memory.write_fact", {**ns, "customer_id": "C1", "slot": "color", "value": "den", "source": "call_1#turn2",
                               "session_id": "s1", "today": "2026-10-15"})
w = mem.call("memory.write_fact", {**ns, "customer_id": "C1", "slot": "color", "value": "trang", "source": "call_1#turn5",
                                   "session_id": "s1", "today": "2026-10-15"})
check(w["op"] == "supersede" and w["previous"] == "den", "khách đổi ý: fact cũ bị thay (supersede), không còn 2 giá trị")
f = mem.call("memory.current_facts", {**ns, "customer_id": "C1", "today": "2026-10-17"})
check(f["color"]["value"] == "trang" and f["color"]["source"] == "call_1#turn5", "đọc lại fact hiện hành + nguồn gốc")
base = mem.call("memory.current_facts", {**ns, "read_enabled": False, "customer_id": "C1", "today": "2026-10-17"})
check(base == {}, "baseline (read_enabled=false) không đọc được bộ nhớ")
mem.close()

print("mcp-memory (ro)")
os.environ["MCP_MEMORY_MODE"] = "ro"
ro = McpConnection("memory-ro", SERVERS["memory"])
check(not any(t in ro.tools for t in ("memory.write_fact", "memory.wipe", "memory.forget_customer")), f"chỉ có tool đọc: {ro.tools}")
check(ro.call("memory.current_facts", {**ns, "customer_id": "C1", "today": "2026-10-17"})["color"]["value"] == "trang",
      "chế độ ro vẫn đọc được")
try:
    ro.call("memory.write_fact", {**ns, "customer_id": "C1", "slot": "color", "value": "x", "source": "s", "session_id": "s",
                                  "today": "2026-10-17"})
    check(False, "chế độ ro từ chối ghi")
except McpToolError:
    check(True, "chế độ ro từ chối ghi")
ro.close()

print("TẤT CẢ OK" if ok else "CÓ LỖI")
sys.exit(0 if ok else 1)
