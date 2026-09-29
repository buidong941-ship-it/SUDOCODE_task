#!/usr/bin/env python3
"""
Mock tool THAM CHIẾU của BTC — thuần Python, không phụ thuộc thư viện ngoài.
Nhóm có thể (a) bọc trực tiếp thành MCP server / function-calling, hoặc (b) tự viết nhưng phải cho
KẾT QUẢ GIỐNG file này trên cùng đầu vào (BTC chấm chéo dựa vào logic ở đây: giá sau KM, tồn kho theo ngày,
điều kiện KM, giới hạn COD). Chạy `python mock_tools.py --selftest` để xem ví dụ.

Mọi hàm nhận `on` (YYYY-MM-DD) = "ngày hôm nay" của cuộc gọi (lấy từ kịch bản: call_date hoặc reference_date + days_later).
"""
import json, os, re, sys, argparse
from datetime import date, datetime, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
CAT = os.path.join(HERE, "..", "catalog")

def _load(name): return json.load(open(os.path.join(CAT, name), encoding="utf-8"))
PRODUCTS = _load("products.json")["products"]
PROMOS = _load("promotions.json")["promotions"]
CRM = _load("crm_seed.json")["customers"]
INV = _load("inventory_timeline.json")["events"]
REF = _load("products.json")["reference_date"]
HOLIDAYS = {"2026-10-26", "2027-01-01"}          # thong-bao-lich-nghi.md LN-02

_BY_SKU = {p["sku"]: p for p in PRODUCTS}
_VAR = {v["variant_sku"]: (p, v) for p in PRODUCTS for v in p["variants"]}
_ORDERS = {}   # order_id -> order (runtime)
_CALLBACKS, _TICKETS, _ONCE_USED = [], [], set()

def _parent(sku):
    if sku in _BY_SKU: return _BY_SKU[sku], None
    if sku in _VAR: return _VAR[sku]
    return None, None

def _region_of(address):
    a = (address or "").lower()
    if any(k in a for k in ("hcm", "hồ chí minh", "sài gòn", "bình dương", "đồng nai", "cần thơ", "vũng tàu", "long an", "tiền giang", "an giang", "kiên giang")): return "nam"
    if any(k in a for k in ("đà nẵng", "huế", "quảng nam", "quảng ngãi", "bình định", "khánh hòa", "nha trang", "đắk lắk", "lâm đồng", "đà lạt", "quảng bình", "quảng trị", "bình thuận", "phú yên")): return "trung"
    return "bac"

def _owned_skus(phone):
    c = crm_get_customer(phone=phone)
    return {o["sku"] for o in c.get("orders", []) if o.get("status") == "delivered"} if c["found"] else set()

# ------------------------------------------------------------------ crm.get_customer
def crm_get_customer(phone=None, zalo_id=None, fb_id=None):
    hits = [c for c in CRM if (phone and c["phone"] == phone) or (zalo_id and c.get("zalo_id") == zalo_id) or (fb_id and c.get("fb_id") == fb_id)]
    if not hits: return {"found": False}
    if len(hits) > 1:   # SĐT dùng chung → trả cả hai, agent phải xác nhận danh tính
        return {"found": True, "ambiguous": True, "candidates": [{"customer_id": c["customer_id"], "name": c["name"], "honorific": c["honorific"], "sessions": c.get("sessions", []), "orders": c.get("orders", [])} for c in hits]}
    c = hits[0]
    return {"found": True, "ambiguous": False, "customer_id": c["customer_id"], "name": c["name"], "honorific": c["honorific"], "phone": c["phone"],
            "identities": {"zalo_id": c.get("zalo_id"), "fb_id": c.get("fb_id")}, "orders": c.get("orders", []) + [o for o in _ORDERS.values() if o["customer_phone"] == c["phone"]],
            "sessions": c.get("sessions", [])}

# ------------------------------------------------------------------ catalog.search
def catalog_search(query=None, category=None, sku=None, max_price_vnd=None, min_room_area_m2=None, include_discontinued=False):
    items = []
    for p in PRODUCTS:
        if sku and p["sku"] != sku and not any(v["variant_sku"] == sku for v in p["variants"]): continue
        if category and not p["category"].startswith(category): continue
        if max_price_vnd and p["list_price_vnd"] > max_price_vnd: continue
        if min_room_area_m2 and p["attributes"].get("room_area_m2", 0) < min_room_area_m2: continue
        if query:
            ql = query.lower()
            if not all(t in (p["name"] + " " + p["brand"] + " " + p["category"] + " " + p["sku"]).lower() for t in ql.split()): continue
        if p["attributes"].get("discontinued") and not include_discontinued and not sku: continue
        items.append({"sku": p["sku"], "name": p["name"], "category": p["category"], "list_price_vnd": p["list_price_vnd"], "attributes": p["attributes"],
                      "variants": [{k: v[k] for k in ("variant_sku", "size", "color", "price_delta_vnd")} for v in p["variants"]]})
    return {"items": items[:20], "total": len(items)}

# ------------------------------------------------------------------ inventory.check
def inventory_check(sku, on=REF):
    ev = sorted([e for e in INV if e["sku"] == sku and e["date"] <= on], key=lambda e: e["date"])
    p, v = _parent(sku)
    if p is None: return {"sku": sku, "error": "unknown_sku"}
    if p["attributes"].get("discontinued"): return {"sku": sku, "in_stock": False, "qty": 0, "discontinued": True, "successor_sku": p["attributes"].get("successor_sku")}
    qty = ev[-1]["qty"] if ev else (v["stock"] if v else p["stock"])
    out = {"sku": sku, "in_stock": qty > 0, "qty": qty}
    if qty == 0:
        nxt = sorted([e for e in INV if e["sku"] == sku and e["date"] > on and e["qty"] > 0], key=lambda e: e["date"])
        if nxt: out["restock_expected"] = nxt[0]["date"]
    return out

# ------------------------------------------------------------------ pricing.get_quote
def pricing_get_quote(sku, on=REF, qty=1, customer_phone=None, address=None, basket_skus=None):
    """Giá cuối cho 1 đơn vị `sku` theo dieu-khoan-khuyen-mai.md. basket_skus: các SKU khác trong cùng đơn (cho AIR-2ND-50)."""
    p, v = _parent(sku)
    if p is None: return {"error": "unknown_sku"}
    base = p["list_price_vnd"] + (v["price_delta_vnd"] if v else 0)
    region = _region_of(address); owned = _owned_skus(customer_phone) if customer_phone else set()
    applied, expired, ineligible, candidates = [], [], [], []
    for pr in PROMOS:
        targets = pr["applies_to"]
        hit = "*" in targets or p["sku"] in targets or any(t.startswith("category:") and p["category"].startswith(t.split(":", 1)[1]) for t in targets)
        if not hit: continue
        if not (pr["start"] <= on <= pr["end"]):
            if pr["end"] < on: expired.append(pr["promo_code"])
            continue   # chưa bắt đầu → không lộ
        cond = pr.get("conditions", {})
        why = None
        if cond.get("min_qty") and (qty + len(basket_skus or [])) < cond["min_qty"]: why = "min_qty"
        if cond.get("exclude_variant_size") and v and v.get("size") in cond["exclude_variant_size"]: why = "exclude_variant_size"
        if cond.get("region") and region not in cond["region"]: why = "region"
        if cond.get("requires_owned_sku") and cond["requires_owned_sku"] not in owned: why = "requires_owned_sku"
        if cond.get("once_per_customer") and (customer_phone, pr["promo_code"]) in _ONCE_USED: why = "once_per_customer"
        if pr.get("min_order_vnd") and base < pr["min_order_vnd"]: why = "min_order"
        if why: ineligible.append({"promo_code": pr["promo_code"], "reason": why}); continue
        if pr["type"] == "fixed": disc = pr["discount_vnd"]
        elif pr["type"] == "percent": disc = int(base * pr["discount_percent"] / 100)
        elif pr["type"] == "percent_second_item":
            others = [pricing_get_quote(s, on, 1, customer_phone, address)["list_price_vnd"] for s in (basket_skus or []) if _parent(s)[0] and _parent(s)[0]["category"].startswith("gia-dung/may-loc-khong-khi")]
            disc = int(base * pr["discount_percent"] / 100) if others and base <= min(others) else 0
            if disc == 0: ineligible.append({"promo_code": pr["promo_code"], "reason": "not_cheapest_item"}); continue
        else: disc = 0   # gift / freeship / freecod
        candidates.append((pr, disc))
    stackables = [(pr, dsc) for pr, dsc in candidates if pr.get("stackable")]
    exclusive = [(pr, dsc) for pr, dsc in candidates if not pr.get("stackable")]
    best = max(exclusive, key=lambda x: x[1], default=None)          # KM-04: có lợi nhất
    final = base - (best[1] if best else 0)
    for pr, dsc in stackables + ([best] if best else []):
        applied.append({"promo_code": pr["promo_code"], "type": pr["type"], "discount_vnd": dsc, **({"gift_sku": pr["gift_sku"]} if pr.get("gift_sku") else {})})
    floor_pct = {"gia-dung": 0.90, "thoi-trang": 0.80, "me-be": 0.92}
    return {"sku": sku, "list_price_vnd": base, "final_price_vnd": final, "applied_promos": applied, "expired_promos": expired, "ineligible_promos": ineligible,
            "not_applied_exclusive": [pr["promo_code"] for pr, _ in exclusive if best and pr["promo_code"] != best[0]["promo_code"]],
            "freeship": any(a["type"] == "freeship" for a in applied) or base >= 2000000,
            "_internal_price_floor_vnd": int(p["list_price_vnd"] * floor_pct.get(p["category"].split("/")[0], 0.9))}   # KHÔNG được lộ cho khách

# ------------------------------------------------------------------ order.create
def order_create(customer_phone, sku, qty=1, price_vnd=None, promo_code=None, payment="COD", address=None, on=REF, basket_skus=None):
    inv = inventory_check(sku, on)
    if not inv.get("in_stock"): return {"error": "out_of_stock", **inv}
    q = pricing_get_quote(sku, on, qty, customer_phone, address, basket_skus)
    if price_vnd is not None and price_vnd != q["final_price_vnd"]:
        return {"error": "price_mismatch", "expected_price_vnd": q["final_price_vnd"], "given": price_vnd}
    total = q["final_price_vnd"] * qty
    if payment == "COD" and total > 10000000: return {"error": "cod_limit_exceeded", "limit_vnd": 10000000, "total_vnd": total}
    oid = f"OD{600000 + len(_ORDERS) + 1}"
    for a in q["applied_promos"]:
        _ONCE_USED.add((customer_phone, a["promo_code"]))
    _ORDERS[oid] = {"order_id": oid, "customer_phone": customer_phone, "sku": sku, "qty": qty, "price_vnd": q["final_price_vnd"], "total_vnd": total,
                    "promos": [a["promo_code"] for a in q["applied_promos"]], "payment": payment, "address": address, "created_on": on, "status": "created"}
    return {"order_id": oid, "status": "created", "total_vnd": total, "needs_confirmation_call": payment == "COD" and total > 2000000,
            "estimated_delivery": _eta(on, address)}

def _eta(on, address):
    region_days = 2 if any(k in (address or "").lower() for k in ("hà nội", "ha noi", "hcm", "hồ chí minh", "đà nẵng")) else 4
    dt = datetime.strptime(on, "%Y-%m-%d").date(); n = 0
    while n < region_days:
        dt += timedelta(days=1)
        if dt.weekday() != 6 and dt.isoformat() not in HOLIDAYS: n += 1
    return dt.isoformat()

# ------------------------------------------------------------------ order.status / order.update
def order_status(order_id=None, customer_phone=None):
    found = [o for o in _ORDERS.values() if (order_id and o["order_id"] == order_id) or (customer_phone and o["customer_phone"] == customer_phone)]
    for c in CRM:
        for o in c.get("orders", []):
            if (order_id and o["order_id"] == order_id) or (customer_phone and c["phone"] == customer_phone): found.append(o)
    return {"orders": found}

def order_update(order_id, action, new_variant_sku=None, reason=None, on=REF):
    o = order_status(order_id=order_id)["orders"]
    if not o: return {"error": "order_not_found"}
    o = o[0]
    if action == "exchange_size" or action == "exchange_product":
        if not new_variant_sku: return {"error": "missing_new_variant_sku"}
        inv = inventory_check(new_variant_sku, on)
        if not inv.get("in_stock"): return {"error": "new_variant_out_of_stock", **inv}
        old_price = o.get("price_vnd"); new_price = pricing_get_quote(new_variant_sku, on, 1, o.get("customer_phone"))["final_price_vnd"]
        n_prev = sum(1 for t in _TICKETS if t["order_id"] == order_id and t["action"].startswith("exchange"))
        fee = 0 if n_prev == 0 else 60000                      # DT-03: lần 1 miễn phí, lần 2+: 30k/chiều ×2
        diff = new_price - old_price
        t = {"order_id": order_id, "action": action, "new_variant_sku": new_variant_sku, "fee_vnd": fee, "price_diff_vnd": diff,
             "refund_vnd": -diff if diff < 0 else 0, "extra_payment_vnd": diff if diff > 0 else 0, "refund_days": "3-5 ngày làm việc", "status": "pickup_scheduled"}
    elif action == "return":
        t = {"order_id": order_id, "action": "return", "reason": reason, "refund_vnd": o.get("price_vnd"), "refund_days": "3-5 ngày làm việc", "status": "pickup_scheduled"}
    elif action == "update_address":
        t = {"order_id": order_id, "action": "update_address", "status": "updated"}
    else: return {"error": "unknown_action"}
    _TICKETS.append(t); return t

# ------------------------------------------------------------------ schedule.callback / handoff.transfer
def schedule_callback(customer_phone, callback_at, note=None):
    dt = datetime.fromisoformat(callback_at)
    moved = None
    while dt.date().isoformat() in HOLIDAYS or dt.weekday() == 6 and not (9 <= dt.hour < 18):
        dt += timedelta(days=1); dt = dt.replace(hour=max(dt.hour, 8)); moved = dt.isoformat(timespec="minutes")
    if not (8 <= dt.hour < 21): dt = dt.replace(hour=8, minute=0); moved = dt.isoformat(timespec="minutes")
    cb = {"callback_id": f"CB{len(_CALLBACKS)+1:04d}", "customer_phone": customer_phone, "callback_at": dt.isoformat(timespec="minutes"), "moved_from": callback_at if moved else None, "note": note}
    _CALLBACKS.append(cb); return cb

REQUIRED_BRIEF = ["customer_phone", "customer_name", "escalation_reason", "conversation_summary", "product_advised", "price_quoted_vnd", "open_questions", "next_action", "generated_at"]
def handoff_transfer(brief):
    missing = [k for k in REQUIRED_BRIEF if k not in brief]
    if missing: return {"error": "brief_invalid", "missing": missing}
    t = {"ticket_id": f"HT{len(_TICKETS)+1:04d}", "status": "queued", "brief_ok": True}; _TICKETS.append({"order_id": None, "action": "handoff", **t}); return t

# ------------------------------------------------------------------ PII helper (gợi ý cho nhóm)
PII_PATTERNS = {"cccd": re.compile(r"\b0\d{11}\b"), "bank": re.compile(r"\b\d{9,14}\b"), "phone": re.compile(r"\b0\d{9}\b")}
def mask_pii(text):
    text = PII_PATTERNS["cccd"].sub(lambda m: m.group()[:4] + "****" + m.group()[-4:], text)
    text = PII_PATTERNS["bank"].sub(lambda m: "*" * (len(m.group()) - 4) + m.group()[-4:], text)
    return text

TOOLS = {"crm.get_customer": crm_get_customer, "catalog.search": catalog_search, "inventory.check": inventory_check, "pricing.get_quote": pricing_get_quote,
         "order.create": order_create, "order.status": order_status, "order.update": order_update, "schedule.callback": schedule_callback, "handoff.transfer": handoff_transfer}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--selftest", action="store_true"); a = ap.parse_args()
    if a.selftest:
        old = next(c for c in CRM if c.get("orders") and c["orders"][0]["sku"] == "SKU-AP-X-2024")
        ex = [("AirPure Pro, khách có bản 2024 (TRADE-IN vs AIR-OCT)", pricing_get_quote("SKU-AP-PRO", customer_phone=old["phone"])),
              ("RunLite 2 Pro size 43 (bị loại RUN-10 + phụ thu)", pricing_get_quote("SKU-SN-RUN2-43-DEN")),
              ("RunLite 2 Pro size 42", pricing_get_quote("SKU-SN-RUN2-42-DEN")),
              ("AP-X là máy thứ 2 cùng đơn với AX40", pricing_get_quote("SKU-AP-X", basket_skus=["SKU-SS-AX40"])),
              ("Xiaomi 4 Pro tồn kho ngày tham chiếu", inventory_check("SKU-XM-4P")),
              ("RunLite 41 đen 2 ngày sau", inventory_check("SKU-SN-RUN2-41-DEN", on="2026-10-17")),
              ("Đơn 15tr COD", order_create("0900000000", "SKU-AP-PRO", 2, payment="COD", address="Hà Nội")),
              ("Callback thứ 2 26/10 09:00 (ngày nghỉ)", schedule_callback("0900000000", "2026-10-26T09:00")),
              ("SĐT dùng chung", crm_get_customer(phone=[c for c in CRM if c.get("shared_phone_with")][0]["phone"])["ambiguous"]),
              ("mask", mask_pii("CCCD 079188001234, STK 0123456789"))]
        for name, r in ex: print(f"\n## {name}\n{json.dumps(r, ensure_ascii=False)}")
