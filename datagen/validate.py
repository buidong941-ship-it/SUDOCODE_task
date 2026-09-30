#!/usr/bin/env python3
"""
Validator kịch bản ↔ catalog/policy của BTC (thay cho eval/validate_scenarios.py mà README nhắc nhưng không phát).

Kiểm tra mỗi kịch bản (định dạng test_set/public_sample/):
  1. Cấu trúc: trường bắt buộc, call_1..call_n liên tục, key success_if hợp lệ, persona có trong personas.json, expected_outcome hợp lệ.
  2. Ngày: call_date/days_later hợp lệ, không rơi vào ngày nghỉ (LN-02); đổi trả không vào Chủ nhật.
  3. Khách: SĐT 10 số; nếu có trong CRM thì tên/xưng hô/định danh kênh khớp.
  4. Slot: must_not_ask / must_carry_over phải đã được thiết lập ở call trước (facts_established, seed_history, CRM).
  5. Ground truth qua mock_tools: price_quoted_vnd, promo_code/expiry, ground_truth_facts (price, in_stock, restock, promo_*_active,
     freeship, warranty…), success_if chạy thử được (order.create không lỗi giá/tồn/COD, order.update có đơn, callback không vào ngày nghỉ…).
  6. Lượt khách: không rỗng, không còn placeholder {{ }}, customer_turns_asr cùng số lượt.
  7. Smoke test bằng eval/reference_eval.py: trace "hoàn hảo" phải PASS, trace rỗng phải FAIL (nếu PASS → kịch bản chấm trivially).
  8. Toàn bộ tập: trùng scenario_id, SĐT dùng lại giữa các kịch bản, thống kê coverage.

Cách dùng:
    python validate.py out/dev out/test                    # thư mục hoặc file
    python validate.py ../BTC/BTC-Data-Vong1-TEAMS/test_set/public_sample
    python validate.py out/reproduce --diff-against ../BTC/BTC-Data-Vong1-TEAMS/test_set/public_sample
    python validate.py out --strict --report report.json   # warning cũng làm exit code ≠ 0
"""
import argparse, collections, copy, glob, json, os, re, sys
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BTC = os.path.join(HERE, "..", "BTC", "BTC-Data-Vong1-TEAMS")

TOP_REQUIRED = ["scenario_id", "level", "persona", "hard_case", "customer_phone", "customer_name", "honorific", "calls"]
TOP_ALLOWED = set(TOP_REQUIRED) | {"notes"}
CALL_ALLOWED = {"channel", "channel_identity", "call_date", "days_later", "customer_goal", "customer_turns", "customer_turns_asr",
                "input_mode", "seed_history", "facts_established", "must_carry_over", "must_not_ask", "success_if",
                "ground_truth_facts", "memory_expectation", "expected_outcome"}
SUCCESS_KEYS = {"tool_called", "args_match", "also_ordered", "total_match_vnd", "brief_must_contain", "must_say_any", "agent_must_say",
                "must_not_call_tools", "forbidden_claims", "trace_must_not_match", "max_agent_questions"}
OUTCOMES = {"hen_goi_lai", "chot_don", "chuyen_may", "tu_choi"}
CHANNELS = {"hotline", "chat_fanpage", "zalo_oa"}
INPUT_MODES = {"asr_transcript", "chat_teencode", "text"}
TOOLS = {"crm.get_customer", "catalog.search", "inventory.check", "order.create", "order.update", "schedule.callback",
         "handoff.transfer", "pricing.get_quote", "order.status"}
PAYMENTS = {"COD", "bank", "momo", "zalopay"}
UPDATE_ACTIONS = {"exchange_size", "exchange_product", "return", "update_address"}
DISCOUNT_TYPES = ("fixed", "percent", "percent_second_item", "gift")
# slot hệ thống biết được từ CRM khi khách có đơn/phiên cũ
CRM_SLOTS = {"order_id", "product_advised", "variant_sku", "owned_product", "address", "payment", "size", "color", "price_quoted_vnd"}
REGION_ADDR = {"bac": "Hà Nội", "trung": "Đà Nẵng", "nam": "TP HCM"}


class Report:
    def __init__(self, sid):
        self.sid, self.items = sid, []

    def add(self, level, where, code, msg):
        self.items.append({"level": level, "where": where, "code": code, "msg": msg})

    def err(self, where, code, msg): self.add("ERROR", where, code, msg)
    def warn(self, where, code, msg): self.add("WARN", where, code, msg)
    def info(self, where, code, msg): self.add("INFO", where, code, msg)


def load_btc(btc):
    sys.path.insert(0, os.path.join(btc, "eval"))
    import mock_tools, reference_eval  # noqa: E402
    personas = {p["persona_id"] for p in json.load(open(os.path.join(btc, "simulator", "personas.json"), encoding="utf-8"))["personas"]}
    return mock_tools, reference_eval, personas


def reset_mock(mt):
    mt._ORDERS.clear(); mt._CALLBACKS.clear(); mt._TICKETS.clear(); mt._ONCE_USED.clear()


def call_dates(sc, ref):
    out, prev = {}, None
    for c in sorted(sc["calls"], key=lambda x: int(x.split("_")[1])):
        spec = sc["calls"][c]
        if spec.get("call_date"): d = spec["call_date"]
        elif prev is None: d = (date.fromisoformat(ref) + timedelta(days=spec.get("days_later", 0))).isoformat()
        else: d = (date.fromisoformat(prev) + timedelta(days=spec.get("days_later", 0))).isoformat()
        out[c] = d; prev = d
    return out


def price_forms(x):
    x = int(x); s = f"{x:,}"
    return {s.replace(",", "."), s, str(x)}


# --------------------------------------------------------------------------- kiểm tra 1 kịch bản
def validate_scenario(sc, ctx):
    mt, personas = ctx["mt"], ctx["personas"]
    sid = sc.get("scenario_id", "?")
    R = Report(sid)
    reset_mock(mt)

    # ---- 1. cấu trúc
    for k in TOP_REQUIRED:
        if k not in sc: R.err("top", "missing_field", f"thiếu trường '{k}'")
    for k in sc:
        if k not in TOP_ALLOWED and not k.startswith("_"): R.warn("top", "unknown_field", f"trường lạ '{k}'")
    if sc.get("level") not in ("M1", "M2"): R.err("top", "bad_level", f"level={sc.get('level')}")
    if sc.get("persona") not in personas: R.warn("top", "persona_unknown", f"persona '{sc.get('persona')}' không có trong simulator/personas.json")
    calls = sc.get("calls") or {}
    names = sorted(calls, key=lambda x: int(x.split("_")[1]) if re.fullmatch(r"call_\d+", x) else 99)
    if names != [f"call_{i}" for i in range(1, len(names) + 1)]: R.err("top", "call_names", f"calls phải là call_1..call_n liên tục: {list(calls)}")
    if len(names) > 3: R.warn("top", "too_many_calls", "trace_log.schema.json chỉ cho call_1..call_3")

    phone = sc.get("customer_phone", "")
    if not re.fullmatch(r"0\d{9}", str(phone)): R.err("top", "bad_phone", f"SĐT '{phone}' không đúng 10 số")
    crm_hits = [c for c in mt.CRM if c["phone"] == phone]
    if crm_hits:
        if not any(c["name"] == sc.get("customer_name") and c["honorific"] == sc.get("honorific") for c in crm_hits):
            R.err("top", "crm_mismatch", f"SĐT thuộc CRM {[c['customer_id'] for c in crm_hits]} nhưng tên/xưng hô '{sc.get('honorific')} {sc.get('customer_name')}' không khớp")
    crm = crm_hits[0] if len(crm_hits) == 1 else None

    try:
        D = call_dates(sc, mt.REF)
    except Exception as e:
        R.err("top", "bad_date", str(e)); return R

    meta_addr = (sc.get("_meta") or {}).get("address")
    base_addr = meta_addr or (REGION_ADDR.get(crm["region"]) if crm else None)
    known_slots, facts_all = set(), {}
    if crm and (crm.get("orders") or crm.get("sessions")): known_slots |= CRM_SLOTS
    prev_d = None
    order_map = {}   # order_id trong kịch bản -> order_id mock
    state = {}

    for cname in names:
        spec = calls[cname]; W = cname; d = D[cname]
        for k in spec:
            if k not in CALL_ALLOWED: R.warn(W, "unknown_field", f"trường lạ '{k}'")
        # ---- 2. ngày
        if prev_d and d < prev_d: R.err(W, "date_order", f"ngày {d} trước call trước {prev_d}")
        if d in mt.HOLIDAYS: R.err(W, "holiday", f"cuộc gọi vào ngày nghỉ {d} (LN-02: tổng đài không hoạt động)")
        wd = date.fromisoformat(d).weekday()
        si = spec.get("success_if") or {}
        if wd == 6 and si.get("tool_called") == "order.update": R.warn(W, "sunday_return", f"{d} là Chủ nhật — LN-01 không xử lý đổi trả")
        prev_d = d
        # ---- kênh
        ch = spec.get("channel", "hotline")
        if ch not in CHANNELS: R.err(W, "bad_channel", f"channel '{ch}'")
        if spec.get("channel_identity") and crm:
            exp = crm.get("fb_id") if ch == "chat_fanpage" else crm.get("zalo_id") if ch == "zalo_oa" else None
            if exp and spec["channel_identity"] != exp: R.err(W, "identity_mismatch", f"channel_identity {spec['channel_identity']} ≠ CRM {exp}")
        if spec.get("expected_outcome") and spec["expected_outcome"] not in OUTCOMES: R.err(W, "bad_outcome", spec["expected_outcome"])
        if spec.get("input_mode") and spec["input_mode"] not in INPUT_MODES: R.err(W, "bad_input_mode", spec["input_mode"])

        # ---- 6. lượt khách
        turns = spec.get("customer_turns")
        if not isinstance(turns, list) or not turns or not all(isinstance(t, str) and t.strip() for t in turns):
            R.err(W, "turns", "customer_turns rỗng hoặc không phải list chuỗi")
            turns = turns if isinstance(turns, list) else []
        asr = spec.get("customer_turns_asr")
        if asr is not None:
            if not isinstance(asr, list) or len(asr) != len(turns): R.err(W, "asr_len", "customer_turns_asr phải cùng số lượt với customer_turns")
            if not spec.get("input_mode"): R.warn(W, "asr_no_mode", "có customer_turns_asr nhưng thiếu input_mode")
        elif spec.get("input_mode") in ("asr_transcript", "chat_teencode"): R.err(W, "asr_missing", "input_mode ASR/teencode nhưng thiếu customer_turns_asr")
        blob = json.dumps(spec, ensure_ascii=False)
        if re.search(r"\{\{.*?\}\}", blob): R.err(W, "placeholder", "còn placeholder {{ }} chưa render")

        # ---- 4. slot
        if spec.get("seed_history"): known_slots |= CRM_SLOTS
        for fld in ("must_not_ask", "must_carry_over"):
            miss = [s for s in spec.get(fld, []) if s not in known_slots]
            if miss:
                (R.warn if cname != "call_1" else R.info)(W, f"{fld}_unknown", f"{fld} {miss} chưa được thiết lập ở call trước/CRM/seed_history")
        facts = spec.get("facts_established") or {}
        known_slots |= set(facts)
        facts_all.update(facts)
        addr = facts_all.get("address") or base_addr

        # ---- 5a. facts_established đối chiếu mock
        prod = facts.get("product_advised")
        vsku = facts.get("variant_sku")
        for s in (prod, vsku):
            if s and mt._parent(s)[0] is None: R.err(W, "unknown_sku", f"SKU {s} không có trong catalog")
        if vsku and prod and mt._parent(vsku)[0] and mt._parent(vsku)[0]["sku"] != prod:
            R.err(W, "variant_parent", f"variant_sku {vsku} không thuộc {prod}")
        qsku = vsku or prod
        if qsku and "price_quoted_vnd" in facts and mt._parent(qsku)[0]:
            qs = [mt.pricing_get_quote(qsku, on=d, customer_phone=phone, address=addr)["final_price_vnd"]]
            if prod and prod != qsku: qs.append(mt.pricing_get_quote(prod, on=d, customer_phone=phone, address=addr)["final_price_vnd"])
            if facts["price_quoted_vnd"] not in qs:
                R.err(W, "price_quoted", f"price_quoted_vnd={facts['price_quoted_vnd']} nhưng mock ngày {d} cho {qs[0]} ({qsku})")
        if qsku and facts.get("promo_code") and mt._parent(qsku)[0]:
            codes = [a["promo_code"] for a in mt.pricing_get_quote(qsku, on=d, customer_phone=phone, address=addr)["applied_promos"]]
            if prod and prod != qsku:
                codes += [a["promo_code"] for a in mt.pricing_get_quote(prod, on=d, customer_phone=phone, address=addr)["applied_promos"]]
            if facts["promo_code"] not in codes: R.err(W, "promo_code", f"promo_code {facts['promo_code']} không được áp ngày {d} (mock áp: {codes})")
        if facts.get("promo_code") and facts.get("promo_expiry"):
            pr = next((p for p in mt.PROMOS if p["promo_code"] == facts["promo_code"]), None)
            if pr and pr["end"] != facts["promo_expiry"]: R.err(W, "promo_expiry", f"promo_expiry {facts['promo_expiry']} ≠ end {pr['end']}")
        if facts.get("order_id") and any(o["order_id"] == facts["order_id"] for c in mt.CRM for o in c.get("orders", [])):
            R.warn(W, "order_id_collision", f"order_id {facts['order_id']} trùng đơn trong CRM")

        # ---- 5b. success_if
        call_sku = _call_sku(si, facts_all, spec)
        _check_success(R, W, mt, si, spec, d, phone, addr, facts_all, order_map, known_slots)

        # ---- 5c. ground_truth_facts
        if si.get("tool_called") == "order.create": state["last_order_date"] = d
        _check_gt(R, W, mt, spec.get("ground_truth_facts") or {}, call_sku, d, phone, addr, si, order_map, state)

        # tạo đơn mock cho call chốt đơn (để call sau order.update/order.status chạy được)
        if facts.get("order_id") and prod:
            r = mt.order_create(phone, vsku or prod, 1, None, None, facts.get("payment", "COD"), addr, d)
            if "order_id" in r: order_map[facts["order_id"]] = r["order_id"]
            else: R.err(W, "order_seed_fail", f"không tạo được đơn {facts['order_id']} trên mock: {r}")
    return R


def _call_sku(si, facts_all, spec):
    am = si.get("args_match") or {}
    if si.get("tool_called") == "order.update" and am.get("new_variant_sku"): return am["new_variant_sku"]
    if am.get("sku"): return am["sku"]
    f = spec.get("facts_established") or {}
    return f.get("variant_sku") or f.get("product_advised") or facts_all.get("variant_sku") or facts_all.get("product_advised")


def _check_success(R, W, mt, si, spec, d, phone, addr, facts_all, order_map, known_slots):
    if not si:
        if spec.get("expected_outcome") in ("chot_don", "chuyen_may") and W != "call_1":
            R.info(W, "no_success_if", f"expected_outcome={spec['expected_outcome']} nhưng không có success_if (call không được chấm TSR)")
        return
    for k in si:
        if k not in SUCCESS_KEYS: R.err(W, "success_key", f"success_if có key lạ '{k}' (reference_eval bỏ qua)")
    tool = si.get("tool_called")
    am = si.get("args_match") or {}
    if tool is not None and tool not in TOOLS: R.err(W, "tool_unknown", f"tool '{tool}' không có trong tools.schema.json")
    for t in si.get("must_not_call_tools", []):
        if t not in TOOLS: R.warn(W, "tool_unknown", f"must_not_call_tools '{t}' lạ")
        if t == tool: R.err(W, "tool_conflict", f"tool_called và must_not_call_tools cùng là {t}")
    for rx in si.get("trace_must_not_match", []):
        try: re.compile(rx)
        except re.error as e: R.err(W, "bad_regex", f"trace_must_not_match /{rx}/: {e}")
    for fc in si.get("forbidden_claims", []):
        if not (isinstance(fc, str) or (isinstance(fc, dict) and "field" in fc and "value" in fc)):
            R.err(W, "forbidden_format", f"forbidden_claims phần tử sai định dạng: {fc}")
    oc = spec.get("expected_outcome")
    if oc == "chuyen_may" and tool != "handoff.transfer": R.err(W, "outcome_tool", "expected_outcome=chuyen_may nhưng tool_called ≠ handoff.transfer")
    if tool == "handoff.transfer" and oc and oc != "chuyen_may": R.warn(W, "outcome_tool", "handoff.transfer nhưng expected_outcome ≠ chuyen_may → reference_eval tính over_escalation")
    if oc == "chot_don" and tool not in ("order.create",): R.warn(W, "outcome_tool", f"expected_outcome=chot_don nhưng tool_called={tool}")

    if tool == "order.create":
        sku, price = am.get("sku"), am.get("price_vnd")
        p, v = mt._parent(sku) if sku else (None, None)
        if not sku or p is None: R.err(W, "order_sku", f"args_match.sku '{sku}' không hợp lệ"); return
        if p["variants"] and not v: R.warn(W, "order_parent_sku", f"{sku} có biến thể size/màu nhưng args_match dùng SKU cha")
        if p["attributes"].get("discontinued"): R.err(W, "order_discontinued", f"{sku} đã ngừng bán")
        if am.get("payment") and am["payment"] not in PAYMENTS: R.err(W, "payment", f"payment '{am['payment']}' ∉ {PAYMENTS}")
        items = si.get("also_ordered") or [sku]
        if sku not in items: R.err(W, "also_ordered", "also_ordered không chứa args_match.sku")
        total = 0
        for s in items:
            basket = [x for x in items if x != s]
            q = mt.pricing_get_quote(s, on=d, customer_phone=phone, address=addr, basket_skus=basket or None)
            if "error" in q: R.err(W, "order_sku", f"{s}: {q['error']}"); continue
            total += q["final_price_vnd"]
            if s == sku and price is not None and price != q["final_price_vnd"]:
                R.err(W, "order_price", f"args_match.price_vnd={price} nhưng mock ngày {d} = {q['final_price_vnd']} (order.create sẽ trả price_mismatch)")
            inv = mt.inventory_check(s, d)
            if not inv.get("in_stock"): R.err(W, "order_stock", f"{s} hết hàng ngày {d}: {inv}")
        if si.get("total_match_vnd") is not None and si["total_match_vnd"] != total:
            R.err(W, "total_match", f"total_match_vnd={si['total_match_vnd']} nhưng mock tổng = {total}")
        pay = am.get("payment", "COD")
        if pay == "COD" and total > 10_000_000: R.err(W, "cod_limit", f"tổng {total} > 10tr mà payment=COD (VC-03)")
        if total > 10_000_000 and "payment" not in am: R.warn(W, "cod_limit", "tổng > 10tr nhưng args_match không ràng buộc payment")
        if len(items) == 1 and price is not None:
            once = set(mt._ONCE_USED); n_orders = dict(mt._ORDERS)
            r = mt.order_create(phone, sku, 1, price, None, pay, addr, d)
            mt._ONCE_USED.clear(); mt._ONCE_USED.update(once)          # chạy thử không được "tiêu" KM once_per_customer
            mt._ORDERS.clear(); mt._ORDERS.update(n_orders)
            if "error" in r: R.err(W, "order_create_fail", f"mock order.create lỗi: {r}")
    elif tool == "order.update":
        oid = am.get("order_id")
        if am.get("action") not in UPDATE_ACTIONS: R.err(W, "update_action", f"action '{am.get('action')}' ∉ {UPDATE_ACTIONS}")
        known = oid in order_map or any(o["order_id"] == oid for c in mt.CRM for o in c.get("orders", []))
        if not known: R.err(W, "update_order", f"order_id {oid} không có ở call trước/CRM")
        if am.get("action", "").startswith("exchange"):
            nv = am.get("new_variant_sku")
            if not nv or mt._parent(nv)[0] is None: R.err(W, "update_variant", f"new_variant_sku '{nv}' không hợp lệ")
            elif not mt.inventory_check(nv, d).get("in_stock"): R.err(W, "update_stock", f"{nv} hết hàng ngày {d}")
        if known and oid in order_map:
            r = mt.order_update(order_map[oid], am.get("action"), am.get("new_variant_sku"), "validate", d)
            if "error" in r: R.err(W, "order_update_fail", f"mock order.update lỗi: {r}")
    elif tool == "schedule.callback":
        at = am.get("callback_at")
        if at:
            r = mt.schedule_callback(phone, at)
            if r.get("moved_from"): R.err(W, "callback_moved", f"callback_at {at} rơi vào ngày nghỉ/ngoài giờ, mock dời sang {r['callback_at']} → args_match không bao giờ khớp")
    elif tool == "handoff.transfer":
        req = set(mt.REQUIRED_BRIEF)
        extra = [k for k in si.get("brief_must_contain", []) if k not in req]
        if extra: R.info(W, "brief_extra", f"brief_must_contain có trường ngoài required của handoff_brief.schema: {extra}")
        if not si.get("brief_must_contain"): R.warn(W, "brief_empty", "handoff.transfer không có brief_must_contain → chỉ cần gọi tool là PASS")
    elif tool == "order.status":
        if not any(o for c in mt.CRM if c["phone"] == phone for o in c.get("orders", [])) and "order_id" not in facts_all:
            R.warn(W, "status_no_order", "order.status nhưng khách không có đơn trong CRM/call trước")
    elif tool is None:
        if not (si.get("must_say_any") or "agent_must_say" in si or si.get("max_agent_questions") is not None):
            R.warn(W, "trivial", "tool_called=null mà không có must_say_any/agent_must_say → trace rỗng cũng PASS")


def _check_gt(R, W, mt, gt, sku, d, phone, addr, si, order_map, state):
    if not gt: return
    q = inv = None
    if sku and mt._parent(sku)[0]:
        basket = [x for x in (si.get("also_ordered") or []) if x != sku] or None
        q = mt.pricing_get_quote(sku, on=d, customer_phone=phone, address=addr, basket_skus=basket)
        inv = mt.inventory_check(sku, d)
    applied = [a["promo_code"] for a in q["applied_promos"]] if q else []
    types = {p["promo_code"]: p["type"] for p in mt.PROMOS}
    p, _ = mt._parent(sku) if sku else (None, None)
    unchecked = []
    for k, v in gt.items():
        exp, ok = None, None
        if q and k == "price_vnd": exp = q["final_price_vnd"]
        elif q and k == "list_price_vnd": exp = q["list_price_vnd"]
        elif q and k == "freeship": exp = q["freeship"]
        elif q and k == "promo_active": exp = any(types.get(c) in DISCOUNT_TYPES for c in applied)
        elif q and re.fullmatch(r"promo_(.+)_active", k): exp = re.fullmatch(r"promo_(.+)_active", k).group(1) in applied
        elif inv and k == "in_stock": exp = bool(inv.get("in_stock"))
        elif k == "new_size_in_stock":
            nv = (si.get("args_match") or {}).get("new_variant_sku")
            if nv: exp = bool(mt.inventory_check(nv, d).get("in_stock"))
        elif inv and k == "restock_date":
            if inv.get("in_stock"):
                ok = True   # đã có hàng: restock_date chỉ là thông tin lịch sử
            else: exp = inv.get("restock_expected")
        elif p and k == "warranty_months": exp = p["attributes"].get("warranty_months")
        elif k == "return_days": exp = 7
        elif k == "exchange_fee_vnd": exp = 0
        elif k == "delivery_days": exp = 2 if any(x in (addr or "").lower() for x in ("hà nội", "ha noi", "hcm", "hồ chí minh", "đà nẵng")) else 4
        elif k == "estimated_delivery" and addr: exp = mt._eta(state.get("last_order_date") or d, addr)
        elif k == "total_vnd" and si.get("also_ordered"):
            items = si["also_ordered"]
            exp = sum(mt.pricing_get_quote(s, on=d, customer_phone=phone, address=addr, basket_skus=[x for x in items if x != s])["final_price_vnd"] for s in items)
        elif k == "refund_vnd":
            upd = (si.get("args_match") or {})
            oid = upd.get("order_id")
            if oid in order_map:
                o = mt._ORDERS.get(order_map[oid])
                if upd.get("action") == "return" and o: exp = o["price_vnd"]
                elif o and upd.get("new_variant_sku"):
                    exp = o["price_vnd"] - mt.pricing_get_quote(upd["new_variant_sku"], on=d, customer_phone=phone, address=addr)["final_price_vnd"]
        if ok is None and exp is None:
            unchecked.append(k); continue
        if ok is None and v != exp:
            if k == "promo_active":   # BTC không định nghĩa rõ: ở đây = có KM giảm giá/quà (không tính freeship/COD-0) đang áp
                R.warn(W, "gt_mismatch", f"ground_truth_facts.promo_active={v!r} nhưng mock ngày {d} ({sku}) áp {applied} → {exp!r}")
                continue
            lvl = R.err if k in ("price_vnd", "list_price_vnd", "in_stock", "restock_date", "total_vnd", "refund_vnd") or k.startswith("promo_") else R.warn
            lvl(W, "gt_mismatch", f"ground_truth_facts.{k}={v!r} nhưng mock ngày {d} ({sku}) = {exp!r}")
    if unchecked: R.info(W, "gt_unchecked", f"không tự kiểm được: {unchecked}")


# --------------------------------------------------------------------------- smoke test với reference_eval
def smoke(sc, ctx, R):
    mt, ev = ctx["mt"], ctx["ev"]
    sid = sc["scenario_id"]
    D = call_dates(sc, mt.REF)
    phone = sc["customer_phone"]
    addr = (sc.get("_meta") or {}).get("address")
    perfect, empty = [], []
    for cname, spec in sc["calls"].items():
        si = spec.get("success_if") or {}
        row = {"run_id": "smoke", "config": "full", "scenario_id": sid, "call": cname, "turn": 1,
               "customer_text": (spec.get("customer_turns") or [""])[0], "agent_text": "", "questions": [],
               "facts_used": list(spec.get("must_carry_over", [])), "claims": [], "tool_calls": [], "memory_writes": [],
               "latency": {"ttft_ms": 1, "total_ms": 1}}
        empty.append(copy.deepcopy(row))
        texts = []
        if si.get("must_say_any"): texts.append(si["must_say_any"][0])
        if "agent_must_say" in si: texts.append("em không có thông tin về vấn đề này")
        row["agent_text"] = " . ".join(texts) or "Dạ vâng ạ."
        row["claims"] = [{"field": k, "value": v} for k, v in (spec.get("ground_truth_facts") or {}).items()]
        tool, am = si.get("tool_called"), dict(si.get("args_match") or {})
        if tool == "handoff.transfer":
            row["tool_calls"].append({"name": tool, "args": {"brief": {k: "x" for k in set(mt.REQUIRED_BRIEF) | set(si.get("brief_must_contain", []))}}})
        elif tool == "order.create":
            items = si.get("also_ordered") or [am.get("sku")]
            for s in items:
                if s == am.get("sku"): args = {**am}
                else:
                    args = {"sku": s, "price_vnd": mt.pricing_get_quote(s, on=D[cname], customer_phone=phone, address=addr,
                                                                     basket_skus=[x for x in items if x != s])["final_price_vnd"]}
                if "price_vnd" not in args:
                    args["price_vnd"] = mt.pricing_get_quote(s, on=D[cname], customer_phone=phone, address=addr)["final_price_vnd"]
                args.setdefault("qty", 1); args.setdefault("customer_phone", phone)
                row["tool_calls"].append({"name": "order.create", "args": args})
        elif tool:
            am.setdefault("customer_phone", phone)
            row["tool_calls"].append({"name": tool, "args": am})
        perfect.append(row)
    scen = {sid: sc}
    tr_p = collections.defaultdict(list); tr_e = collections.defaultdict(list)
    for r in perfect: tr_p[(sid, r["call"])].append(r)
    for r in empty: tr_e[(sid, r["call"])].append(r)
    if not any((c.get("success_if")) for c in sc["calls"].values()):
        R.warn("smoke", "no_tsr", "kịch bản không có success_if nào → không tính vào TSR"); return
    tp = ev.task_success_rate(scen, tr_p)
    te = ev.task_success_rate(scen, tr_e)
    if tp["passed"] != tp["total"]:
        R.err("smoke", "perfect_fails", f"trace hoàn hảo vẫn FAIL → success_if tự mâu thuẫn: {[f['reasons'] for f in tp['failures']]}")
    if te["passed"] == te["total"]:
        R.warn("smoke", "empty_passes", "trace RỖNG vẫn PASS → kịch bản chấm trivially (thêm must_say_any/tool_called)")
    g = ev.guardrail_violations(scen, tr_p)
    if g["total"]: R.err("smoke", "perfect_guardrail", f"trace hoàn hảo bị tính vi phạm guardrail: {g['by_type']}")
    h = ev.hallucination_rate(scen, tr_p)
    if h["wrong"]: R.err("smoke", "perfect_hr", f"claim = ground_truth mà vẫn bị tính sai: {h['examples'][:3]}")


# --------------------------------------------------------------------------- so với SAMPLE gốc
DIFF_FIELDS = ["facts_established", "must_carry_over", "must_not_ask", "success_if", "ground_truth_facts", "expected_outcome", "channel", "input_mode"]


def diff_against(scs, ref_dir):
    refs = {}
    for f in glob.glob(os.path.join(ref_dir, "*.json")):
        s = json.load(open(f, encoding="utf-8")); refs[s["scenario_id"]] = s
    out = []
    for sc in scs:
        rid = (sc.get("_meta") or {}).get("reproduces")
        if not rid: continue
        ref = refs.get(rid)
        if not ref: out.append((sc["scenario_id"], rid, ["không tìm thấy kịch bản gốc"])); continue
        diffs = []
        for k in ("persona", "hard_case", "customer_phone", "customer_name", "honorific"):
            if sc.get(k) != ref.get(k): diffs.append(f"{k}: gen={sc.get(k)!r} ref={ref.get(k)!r}")
        rd, gd = call_dates(ref, "2026-10-15"), call_dates(sc, "2026-10-15")
        if rd != gd: diffs.append(f"dates: gen={gd} ref={rd}")
        for c in sorted(set(ref["calls"]) | set(sc["calls"])):
            a, b = sc["calls"].get(c, {}), ref["calls"].get(c, {})
            for f in DIFF_FIELDS:
                va, vb = a.get(f), b.get(f)
                if isinstance(va, dict) and isinstance(vb, dict):
                    for kk in sorted(set(va) | set(vb)):
                        if va.get(kk) != vb.get(kk): diffs.append(f"{c}.{f}.{kk}: gen={va.get(kk)!r} ref={vb.get(kk)!r}")
                elif isinstance(va, list) and isinstance(vb, list) and sorted(map(str, va)) == sorted(map(str, vb)):
                    continue
                elif va != vb:
                    diffs.append(f"{c}.{f}: gen={va!r} ref={vb!r}")
        out.append((sc["scenario_id"], rid, diffs))
    return out


# --------------------------------------------------------------------------- main
def load_paths(paths):
    files = []
    for p in paths:
        if os.path.isdir(p): files += sorted(glob.glob(os.path.join(p, "**", "*.json"), recursive=True))
        else: files.append(p)
    out = []
    for f in files:
        if os.path.basename(f).startswith(("_", "manifest")) or os.path.basename(f) == "report.json": continue
        try: s = json.load(open(f, encoding="utf-8"))
        except Exception as e: print(f"[ERROR] {f}: JSON lỗi: {e}"); continue
        if isinstance(s, dict) and "calls" in s: s["_file"] = f; out.append(s)
    return out


def coverage(scs, mt):
    cov = collections.Counter(); per = collections.defaultdict(collections.Counter)
    for s in scs:
        cov["scenarios"] += 1; cov["calls"] += len(s["calls"])
        cov["hard"] += bool(s.get("hard_case"))
        per["hard_case"][s.get("hard_case") or "(thường)"] += 1
        per["persona"][s["persona"]] += 1
        per["level"][s["level"]] += 1
        split = (s.get("_meta") or {}).get("split", "-"); per["split"][split] += 1
        chans = []
        for c in s["calls"].values():
            cov["turns"] += len(c.get("customer_turns", []))
            ch = c.get("channel", "hotline"); per["channel"][ch] += 1; chans.append(ch)
            per["input_mode"][c.get("input_mode", "text")] += 1
            per["outcome"][c.get("expected_outcome", "-")] += 1
            si = c.get("success_if") or {}
            per["tool_called"][str(si.get("tool_called")) if si else "(không chấm)"] += 1
            f = c.get("facts_established") or {}
            sku = (si.get("args_match") or {}).get("sku") or f.get("product_advised")
            if sku and mt._parent(sku)[0]: per["category"][mt._parent(sku)[0]["category"]] += 1
        if len(set(chans)) > 1: cov["multi_channel_customers"] += 1
    return cov, per


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--btc", default=DEFAULT_BTC)
    ap.add_argument("--no-smoke", action="store_true")
    ap.add_argument("--strict", action="store_true", help="WARN cũng tính là lỗi")
    ap.add_argument("--show-info", action="store_true")
    ap.add_argument("--diff-against", help="thư mục SAMPLE gốc để so với kịch bản có _meta.reproduces")
    ap.add_argument("--report", help="ghi báo cáo JSON")
    a = ap.parse_args()

    mt, ev, personas = load_btc(os.path.abspath(a.btc))
    ctx = {"mt": mt, "ev": ev, "personas": personas}
    scs = load_paths(a.paths)
    if not scs: print("Không có kịch bản nào."); return 2

    reports = []
    for sc in scs:
        try:
            R = validate_scenario(sc, ctx)
            if not a.no_smoke and not any(i["level"] == "ERROR" and i["where"] == "top" for i in R.items): smoke(sc, ctx, R)
        except Exception as e:   # validator không được chết vì 1 kịch bản hỏng
            R = Report(sc.get("scenario_id", "?")); R.err("top", "crash", f"{type(e).__name__}: {e}")
        reports.append((sc, R))

    # toàn tập
    ids = collections.Counter(s["scenario_id"] for s in scs)
    phones = collections.defaultdict(list)
    for s in scs: phones[s["customer_phone"]].append(s["scenario_id"])
    glob_issues = [f"scenario_id trùng: {k} ×{v}" for k, v in ids.items() if v > 1]
    glob_warn = [f"SĐT {p} dùng ở {len(v)} kịch bản: {v}" for p, v in phones.items() if len(v) > 1]

    n_err = n_warn = 0
    for sc, R in reports:
        errs = [i for i in R.items if i["level"] == "ERROR"]; warns = [i for i in R.items if i["level"] == "WARN"]
        infos = [i for i in R.items if i["level"] == "INFO"]
        n_err += len(errs); n_warn += len(warns)
        tag = "FAIL" if errs else ("WARN" if warns else "OK")
        try: shown = os.path.relpath(sc["_file"])
        except ValueError: shown = sc["_file"]          # khác ổ đĩa trên Windows
        print(f"[{tag:<4}] {R.sid:<18} {shown}")
        for i in errs + warns + (infos if a.show_info else []):
            print(f"        {i['level']:<5} {i['where']:<7} {i['code']:<20} {i['msg']}")
    for g in glob_issues: print(f"[FAIL] (toàn tập) {g}"); n_err += 1
    for g in glob_warn: print(f"[WARN] (toàn tập) {g}"); n_warn += 1

    cov, per = coverage(scs, mt)
    print(f"\n== Coverage: {cov['scenarios']} kịch bản, {cov['calls']} phiên, {cov['turns']} lượt khách, "
          f"{cov['hard']} ca khó ({round(100 * cov['hard'] / max(1, cov['scenarios']))}%), {cov['multi_channel_customers']} kịch bản đa kênh")
    for k in ("split", "level", "hard_case", "persona", "category", "channel", "input_mode", "outcome", "tool_called"):
        print(f"  {k:<11} " + ", ".join(f"{a_}={b_}" for a_, b_ in per[k].most_common()))
    missing_p = sorted(personas - set(per["persona"]))
    if missing_p: print(f"  persona chưa có kịch bản: {missing_p}")

    diffs = []
    if a.diff_against:
        diffs = diff_against(scs, a.diff_against)
        print("\n== So với kịch bản gốc")
        for sid, rid, ds in diffs:
            print(f"  {sid} ↔ {rid}: {'KHỚP' if not ds else str(len(ds)) + ' khác biệt'}")
            for x in ds: print(f"      - {x}")

    if a.report:
        json.dump({"errors": n_err, "warnings": n_warn,
                   "scenarios": [{"scenario_id": R.sid, "file": sc["_file"], "issues": R.items} for sc, R in reports],
                   "global": {"errors": glob_issues, "warnings": glob_warn},
                   "coverage": {"totals": cov, **{k: dict(v) for k, v in per.items()}},
                   "diff": [{"scenario_id": s, "reproduces": r, "diffs": d} for s, r, d in diffs]},
                  open(a.report, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"\n{len(scs)} kịch bản: {n_err} lỗi, {n_warn} cảnh báo")
    return 1 if n_err or (a.strict and n_warn) else 0


if __name__ == "__main__":
    sys.exit(main())
