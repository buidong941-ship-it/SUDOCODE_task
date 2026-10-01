"""Một cuộc gọi = CallSession. Vòng lặp mỗi lượt:

perceive → slot khách → ROUTER (Jev) quyết định intent/cờ → PLANNER gọi tool (giá/tồn/đơn chỉ từ tool) →
GENERATOR (DeepSeek) nói theo goals+facts → GUARDRAIL → EXTRACTOR (questions/claims/facts_used) → ghi BỘ NHỚ → trace.

Planner là code xác định (không để LLM tự chọn tham số tool): tham số order.create lấy từ báo giá tool vừa trả,
nên giá trong đơn luôn khớp mock của BTC. LLM chỉ lo câu chữ.
"""
import re
import time
from datetime import date, datetime, timedelta

from core.llm.generator import Generator
from core.llm.router import Router
from harness import extractor, guardrails, knowledge
from harness.textnorm import find_money, fold, perceive
from harness.tools import (ToolBox, find_by_model_token, find_products, find_variant, mt, product_name, public_view)

CATEGORY_WORDS = [("may loc khong khi", "gia-dung/may-loc-khong-khi"), ("may loc nuoc", "gia-dung/may-loc-nuoc"),
                  ("noi chien", "gia-dung/noi-chien"), ("quat", "gia-dung/quat"), ("giay", "thoi-trang/giay"),
                  ("ao khoac", "thoi-trang/ao"), ("may hut sua", "me-be"), ("xe day", "me-be"), ("binh sua", "me-be"),
                  ("may ham sua", "me-be"), ("ghe o to", "me-be")]
STACKABLE_SKIP = {"COD-0", "NAM-SHIP0"}         # KM phí ship/COD: không coi là "mã KM" của đơn
FILTER_OF = {"SKU-AP-X": "SKU-AP-FLT-X", "SKU-AP-Y": "SKU-AP-FLT-X", "SKU-AP-PRO": "SKU-AP-FLT-P",
             "SKU-XM-4L": "SKU-XM-FLT", "SKU-XM-4P": "SKU-XM-FLT"}


def _ddmm(d):
    return f"{int(d[8:10])}/{int(d[5:7])}"


class CallSession:
    def __init__(self, *, memory, today, call_name, session_id, channel, channel_identity, phone, input_mode,
                 router=None, generator=None, config="full"):
        self.mem, self.today, self.call_name, self.session_id = memory, today, call_name, session_id
        self.channel, self.channel_identity, self.phone, self.input_mode = channel or "hotline", channel_identity, phone, input_mode
        self.router, self.gen, self.config = router or Router(), generator or Generator(), config
        self.tools = ToolBox(today)
        self.customer = None            # {customer_id, name, honorific, phone}
        self.candidates = []            # SĐT dùng chung → chờ xác nhận
        self.carried = {}               # slot nạp từ phiên trước (để tính facts_used)
        self.known = {}                 # slot đã biết trong cuộc này (nạp + mới)
        self.focus = None               # SKU đang bàn
        self.quote = None               # báo giá gần nhất (public view)
        self.prev_quotes = []
        self.orders_created, self.history, self.turn_no = [], [], 0
        self.brief, self.brief_ms, self.start_tool_log = None, None, []
        self.outcome, self.blockers = None, []
        self.focus_by, self.price_change_told, self.category, self.updates_done = None, False, None, {}
        self.pending_size, self.buy_intent, self.deleted = None, False, False
        self.cart, self.discussed, self.expired, self._deleted_turn = [], [], {}, None
        self.size_asked = False

    # ================================================================== bắt đầu cuộc gọi: nhận diện + Call Brief
    def start(self):
        t0 = time.perf_counter()
        kind, val = ("fb_id", self.channel_identity) if self.channel == "chat_fanpage" else \
                    ("zalo_id", self.channel_identity) if self.channel == "zalo_oa" else ("phone", self.phone)
        if not val:
            kind, val = "phone", self.phone
        r = self.tools.call("crm.get_customer", **{kind: val})
        if r.get("found") and r.get("ambiguous"):
            self.candidates = r["candidates"]
        elif r.get("found"):
            self._bind(r["customer_id"], r.get("name"), r.get("honorific"), r.get("phone") or self.phone, r)
        else:
            ids = self.mem.lookup(kind, val) if val else []
            if ids:
                self._bind(ids[0], None, None, self.phone, None)
            elif val:
                self._bind(f"N-{val}", None, None, self.phone, None)
        self.brief = self._build_brief()
        self.brief_ms = int((time.perf_counter() - t0) * 1000)
        self.brief["latency_ms"] = self.brief_ms
        self.start_tool_log = self.tools.take_log()
        return self.brief

    def _bind(self, cid, name, honorific, phone, crm):
        self.customer = {"customer_id": cid, "name": name, "honorific": honorific or "anh/chị", "phone": phone}
        ids = [("phone", phone)]
        if crm:
            ids += [("zalo_id", (crm.get("identities") or {}).get("zalo_id")), ("fb_id", (crm.get("identities") or {}).get("fb_id"))]
        if self.channel_identity:
            ids.append(("fb_id" if self.channel == "chat_fanpage" else "zalo_id", self.channel_identity))
        self.mem.upsert_customer(cid, name, honorific, phone, ids)
        for kind, value in ids:                       # hồ sơ tạm cùng định danh → gộp vào hồ sơ này
            for other in (self.mem.lookup(kind, value) if value else []):
                if other != cid and other.startswith("N-"):
                    self.mem.merge_customer(other, cid)
        # lịch sử CRM (phiên cũ ngoài hệ thống) → bộ nhớ, kèm ngày gốc để xét TTL
        for s in (crm or {}).get("sessions", []) or []:
            self.import_old_session(s, cid)
        if self.mem.read_enabled and self.mem.status(cid) != "deletion_requested":
            self.carried = {k: v["value"] for k, v in self.mem.current_facts(cid, self.today).items()}
            self.known = dict(self.carried)
            self.prev_quotes = self.mem.past_quotes(cid)
            self.focus = self.known.get("product_chosen") or self.known.get("product_advised")
            self.focus_by = "memory" if self.focus else None

    def import_old_session(self, s, cid):
        sid = s["session_id"]
        if any(p["session_id"] == sid for p in self.mem.past_sessions(cid)):
            return
        self.mem.add_session(sid, cid, s.get("channel"), s.get("date"), s.get("outcome"), s.get("summary"), source="crm")
        text, d = s.get("summary", ""), s.get("date") or self.today
        slots = extractor.customer_slots(text, d)
        prods = find_products(text)
        if prods: slots["product_advised"] = prods[0]
        money = find_money(text)
        if money and prods: slots["price_quoted_vnd"] = money[0][2]
        for k in ("blocker", "callback_requested", "self_name", "competitor_price_vnd"):
            slots.pop(k, None)
        for k, v in slots.items():
            self.mem.write_fact(cid, k, v, f"crm:{sid}", sid, self.today, confidence=0.8, valid_from=d)

    def _build_brief(self):
        c = self.customer or {}
        cid = c.get("customer_id")
        past = self.mem.past_sessions(cid, self.session_id) if cid else []
        facts = self.mem.current_facts(cid, self.today, include_expired=True) if cid else {}
        stale, advised = [], []
        for slot, fct in facts.items():
            if fct["expired"]:
                stale.append(f"{slot} đã quá hạn (ghi ngày {fct.get('expires_on')}) — chỉ hỏi xác nhận")
                self.known.pop(slot, None); self.expired[slot] = fct["value"]
        # kiểm tra tính mới: báo giá cũ còn đúng không (chạy lúc nhận diện, tính vào latency)
        seen = set()
        for q in reversed(self.prev_quotes):
            if q["sku"] in seen or q["role"] not in ("advised", "chosen"):
                continue
            seen.add(q["sku"])
            now = public_view(self.tools.call("pricing.get_quote", sku=q["sku"], customer_phone=c.get("phone")))
            inv = self.tools.call("inventory.check", sku=q["sku"])
            active = bool(q["promo_code"]) and any(a["promo_code"] == q["promo_code"] for a in now.get("applied_promos", []))
            if q["promo_code"] and not active:
                stale.append(f"KM {q['promo_code']} báo cho {q['sku']} đã hết hạn")
            if now.get("final_price_vnd") != q["final_price_vnd"]:
                stale.append(f"giá {q['sku']} đổi {q['final_price_vnd']} → {now.get('final_price_vnd')}")
            if not inv.get("in_stock"):
                stale.append(f"{q['sku']} đang hết hàng")
            advised.append({"sku": q["sku"], "price_quoted_vnd": q["final_price_vnd"], "promo_code": q["promo_code"],
                            "promo_still_active": active if q["promo_code"] else None, "quoted_on": q["quoted_on"],
                            "current_price_vnd": now.get("final_price_vnd"), "in_stock_now": inv.get("in_stock")})
        last = past[-1] if past else None
        must_not_ask = sorted(k for k, v in facts.items() if not v["expired"])
        blockers = [self.known["blocker"]] if self.known.get("blocker") else []
        opening = None
        if last and self.focus:
            opening = f"Dạ em chào {c.get('honorific')} {c.get('name') or ''}, hôm {_ddmm(last['started_on'])} bên em có tư vấn mẫu {product_name(self.focus)}."
        return {"customer_phone": c.get("phone") or self.phone, "customer_name": c.get("name"), "honorific": c.get("honorific"),
                "is_returning": bool(past), "n_previous_sessions": len(past),
                "last_session": {"session_id": last["session_id"], "date": last["started_on"], "channel": last["channel"],
                                 "summary": last["summary"], "outcome": last["outcome"] or "khac"} if last else None,
                "profile_facts": {k: v["value"] for k, v in facts.items() if not v["expired"]},
                "products_advised": advised, "orders": [], "open_blockers": blockers, "open_questions": [],
                "must_not_ask": must_not_ask, "stale_warnings": stale, "suggested_opening": opening,
                "suggested_next_action": "xác nhận tiếp nối, giải quyết rào cản rồi chốt" if blockers else None,
                "generated_at": datetime.now().isoformat(timespec="seconds"), "latency_ms": None,
                "precomputed_parts": ["sessions.summary", "facts"], "ambiguous_candidates": [x["name"] for x in self.candidates]}

    # ================================================================== một lượt
    def turn(self, raw):
        t_start = time.perf_counter()
        self.turn_no += 1
        p = perceive(raw, self.today)
        text = p["text"]
        slots = extractor.customer_slots(text, self.today)
        if p["phone"] and self.customer and self.customer.get("customer_id") and not self.candidates:
            cid = self.customer["customer_id"]
            self.mem.upsert_customer(cid, identities_=[("phone", p["phone"])])
            self.customer["phone"] = self.customer.get("phone") or p["phone"]
            if cid.startswith("N-"):                  # khách chat đọc SĐT → có thể là khách CRM
                r = self.tools.call("crm.get_customer", phone=p["phone"])
                if r.get("found") and not r.get("ambiguous"):
                    self.mem.merge_customer(cid, r["customer_id"])
                    keep = dict(self.known)
                    self._bind(r["customer_id"], r.get("name"), r.get("honorific"), p["phone"], r)
                    self.known.update(keep)
        if self.candidates and slots.get("self_name"):
            self._resolve_candidate(slots["self_name"])
        ctx = {"recent": self.history[-4:], "summary": (self.brief or {}).get("last_session") and self.brief["last_session"]["summary"] or ""}
        route = self.router.route(text, ctx)
        goals, facts = self._plan(text, slots, route)
        tool_log = (self.start_tool_log if self.turn_no == 1 else []) + self.tools.take_log()
        plan = {"honorific": (self.customer or {}).get("honorific") or "anh/chị", "customer_name": (self.customer or {}).get("name"),
                "call": self.call_name, "is_returning": bool(self.brief and self.brief["is_returning"]),
                "customer_said": text, "intent": route["intent"], "goals": goals, "facts": facts,
                "KNOWN": {k: v for k, v in self.known.items() if k not in ("self_name",)}}
        allowed = set(p["money"]) | {v for v in self.known.values() if isinstance(v, int)}
        internal = set()
        for tc in tool_log:
            allowed |= guardrails.collect_numbers(tc["result"])
            internal |= {int(v) for k, v in (tc["result"] or {}).items() if str(k).startswith("_") and isinstance(v, (int, float))} if isinstance(tc["result"], dict) else set()
        for q in self.prev_quotes:
            allowed |= {q["final_price_vnd"], q["list_price_vnd"]}
        text_out, ttft, total_gen, usage = self.gen.generate(plan)
        problems = guardrails.check(text_out, allowed, internal)
        guard = {"problems": problems, "action": None}
        if problems:
            text2, ttft2, tot2, _ = self.gen.generate(plan, retry_note="; ".join(problems))
            if not guardrails.check(text2, allowed, internal):
                text_out, guard["action"] = text2, "regenerated"
            else:
                from core.llm.generator import render_offline
                text_out, guard["action"] = render_offline(plan), "safe_template"
            total_gen += tot2
        # ---- trích cho trace
        known_for_q = {k: v for k, v in self.known.items()}
        questions = extractor.agent_questions(text_out, known_for_q)
        claims = extractor.agent_claims(text_out)
        used = extractor.facts_used(text_out, [tc["args"] for tc in tool_log], self.carried)
        mem_writes = self._remember(slots, route)
        self.history += [{"role": "customer", "text": text}, {"role": "agent", "text": text_out}]
        if self.customer and self.customer.get("customer_id"):
            self.mem.log_turn(self.session_id, self.turn_no, text, text_out, {"focus": self.focus, "intent": route["intent"]})
        total_ms = int((time.perf_counter() - t_start) * 1000)
        pre_ms = total_ms - total_gen
        row = {"customer_text": text, "agent_text": text_out, "questions": questions, "facts_used": used, "claims": claims,
               "tool_calls": [{"name": tc["name"], "args": tc["args"], "result": tc["result"]} for tc in tool_log],
               "latency": {"ttft_ms": pre_ms + ttft, "total_ms": total_ms, "ttfa_ms": None},
               "memory_writes": mem_writes,
               "customer_input_mode": {"asr_transcript": "asr_transcript", "chat_teencode": "chat_teencode"}.get(self.input_mode, "clean"),
               "router": {k: route.get(k) for k in ("intent", "confidence", "flags", "backend", "ms", "fallback")},
               "goals": goals, "guardrail": guard, "llm_usage": usage}
        if self.turn_no == 1:
            row["call_brief_latency_ms"] = self.brief_ms if self.call_name != "call_1" else None
            row["call_brief"] = self.brief
        return row

    def _resolve_candidate(self, name):
        for c in self.candidates:
            if fold(c["name"]) == fold(name):
                full = self.tools.call("crm.get_customer", phone=self.phone)
                self._bind(c["customer_id"], c["name"], c["honorific"], self.phone, {"sessions": c.get("sessions", []), "identities": {}})
                self.candidates = []
                return

    # ================================================================== planner
    def _quote(self, sku, role="advised", basket=None):
        c = self.customer or {}
        q = public_view(self.tools.call("pricing.get_quote", sku=sku, customer_phone=c.get("phone"),
                                        address=self.known.get("address"), basket_skus=basket))
        inv = self.tools.call("inventory.check", sku=sku)
        promos = [a["promo_code"] for a in q.get("applied_promos", []) if a["promo_code"] not in STACKABLE_SKIP]
        names = []
        for code in promos:
            pr = next((x for x in mt.PROMOS if x["promo_code"] == code), None)
            if pr: names.append(f"{pr['name']} (đến {_ddmm(pr['end'])})")
        view = {"sku": sku, "name": product_name(sku), "list_price_vnd": q.get("list_price_vnd"), "final_price_vnd": q.get("final_price_vnd"),
                "promo_codes": promos, "promo_names": names, "freeship": q.get("freeship"),
                "expired_promos": [x.get("promo_code") if isinstance(x, dict) else x for x in q.get("expired_promos", [])],
                "in_stock": inv.get("in_stock"), "restock_expected": inv.get("restock_expected"),
                "discontinued": inv.get("discontinued"), "successor_sku": inv.get("successor_sku")}
        p, _ = mt._parent(sku)
        if p: view["attributes"] = {k: v for k, v in p["attributes"].items() if not str(k).startswith("_")}
        pr_end = next((x["end"] for x in mt.PROMOS if promos and x["promo_code"] == promos[0]), None)
        view["promo_end"] = pr_end
        if role in ("advised", "chosen"):
            self.quote = view
        par = p["sku"] if p else sku
        if par not in [mt._parent(d)[0]["sku"] for d in self.discussed if mt._parent(d)[0]]:
            self.discussed.append(sku)
        if q.get("final_price_vnd") and self.customer and self.customer.get("customer_id"):
            self.mem.add_quote(self.customer["customer_id"], self.session_id, sku, role, q.get("list_price_vnd"), q["final_price_vnd"],
                               promos[0] if promos else None, pr_end, self.today)
        return view

    def _recommend(self, text):
        f = fold(text)
        cat = next((c for w, c in CATEGORY_WORDS if w in f), None) or self.category
        if not cat:
            return None
        self.category = cat
        if cat == "gia-dung/may-loc-khong-khi" and not ({"has_children", "budget_vnd"} & set(self.known)):
            return "ASK_NEED"
        area, budget, kids = self.known.get("room_area_m2"), self.known.get("budget_vnd"), self.known.get("has_children")
        items = mt.catalog_search(category=cat)["items"]
        cands = []
        for it in items:
            a = it["attributes"]
            if it["list_price_vnd"] < 400000 or not self.tools.call("inventory.check", sku=it["sku"]).get("in_stock"):
                continue
            if area and a.get("room_area_m2") and a["room_area_m2"] < area:
                continue
            score = (2 if kids and a.get("child_safe_lock") else 0) - (1 if budget and it["list_price_vnd"] > budget * 1.1 else 0)
            cands.append((-score, it["list_price_vnd"], it["sku"]))
        self.tools.log.append({"name": "catalog.search", "args": {"category": cat}, "result": {"total": len(items)}, "ms": 0})
        return sorted(cands)[0][2] if cands else None

    def _plan(self, text, slots, route):
        it, fl = route["intent"], route.get("flags", {})
        goals, facts = [], {}
        c = self.customer or {}
        y = lambda k, th=0.6: fl.get(k, 0) >= th
        # --- slot khách nói lượt này cập nhật "known" ngay (để planner dùng)
        for k, v in slots.items():
            if k not in ("self_name", "claimed_prices"):
                self.known[k] = v
        if self.candidates:
            return ["ask_identity"], facts
        # --- sản phẩm khách nhắc lượt này
        f = fold(text)
        mentioned = find_products(text)
        if re.search(r"\bmang loc\b", f):                # "màng lọc thay thế cho máy AirPure Pro" → SKU màng lọc
            base = mentioned or ([self.focus] if self.focus else [])
            mentioned = [FILTER_OF.get(mt._parent(x)[0]["sku"], x) for x in base]
        alt = None if mentioned else (find_by_model_token(text, self.focus) if self.focus else None)
        sents = [x for x in re.split(r"(?<=[.!?])\s+", text.strip()) if x]
        last = fold(sents[-1]) if sents else f
        asking = sents[-1].rstrip().endswith("?") if sents else False
        asking = asking or (bool(re.search(r"\b(bao nhieu|duoc khong|the nao)\b", last))
                            and not re.search(r"\b(len don|chot|dat hang)\b", last))
        takes = bool(re.search(r"\b(lay|them|chot|mua (luon|them|ca|cho|nhe|nha))\b", f))
        compare = bool(alt) or bool(mentioned and self.focus and mt._parent(mentioned[-1])[0]["sku"] != mt._parent(self.focus)[0]["sku"]
                                    and re.search(r"\bcon\b", f) and not takes)
        prev_focus = self.focus
        new_focus = None
        if mentioned and not compare:
            new_focus = mentioned[-1]
            self.focus, self.focus_by = new_focus, "customer"
        if takes and mentioned and not compare:
            for m_ in mentioned:
                self._cart_add(m_)
        if re.search(r"lay (du|ca|het|tat ca)|ca hai|ca 2|lay du", f):
            for d in self.discussed:
                self._cart_add(d)
        # --- lượt 1 của khách quay lại: xác nhận tiếp nối
        if self.turn_no == 1:
            if self.brief and self.brief["is_returning"] and prev_focus:
                last = self.brief["last_session"]
                facts["brief"] = {"product_name": product_name(prev_focus), "price_quoted_vnd": self.known.get("price_quoted_vnd"),
                                  "last_date_ddmm": _ddmm(last["date"]) if last else None, "blocker": self.known.get("blocker"),
                                  "stale_warnings": self.brief["stale_warnings"]}
                goals.append("opening_returning")
                if any("KM" in w for w in self.brief["stale_warnings"]):
                    goals.append("stale_promo")
        # --- an toàn / meta trước
        if y("asks_if_bot") or (it == "meta" and not y("wants_data_deleted")):
            goals.append("is_bot")
        if y("wants_data_deleted"):
            if c.get("customer_id"):
                self.mem.forget_customer(c["customer_id"])
            self.known, self.carried, self.deleted, self._deleted_turn = {}, {}, True, self.turn_no
            facts["deleted"] = True; goals.append("data_deleted")
            return goals, facts
        if it == "out_of_scope" or y("medical_question", 0.7):
            brief = self._handoff_brief(text, "cau_hoi_y_te" if y("medical_question", 0.5) else "khach_yeu_cau_gap_nguoi")
            facts["handoff"] = self.tools.call("handoff.transfer", brief=brief)
            goals.append("handoff"); self.outcome = "chuyen_may"
            return goals, facts
        if y("asks_internal_cost"):
            goals.append("refuse_internal")
        # --- đơn đã mua
        if it == "order_change":
            g = self._plan_order_change(text, facts)
            if g != ["WINDOW_PASSED"]:
                return goals + g, facts
            goals.append("exchange_window_passed"); it = "product_inquiry"
        if it == "order_status":
            r = self.tools.call("order.status", customer_phone=c.get("phone") or self.phone)
            facts["orders"] = [{k: o.get(k) for k in ("order_id", "sku", "status", "tracking", "created_on", "date")} for o in r.get("orders", [])]
            goals.append("order_status")
            return goals, facts
        if it == "policy_question" or (it == "greeting_or_other" and "?" in text and not self.focus):
            hits = knowledge.search(text, k=2)
            facts["policy"] = [{"chunk_id": h["chunk_id"], "text": h["text"][:600]} for h in hits]
            goals.append("policy_answer" if hits else "no_info")
        # --- tư vấn: gợi ý khi chưa có sản phẩm (hoặc khách vừa nói thêm nhu cầu)
        sales_turn = it not in ("order_change", "order_status", "meta", "out_of_scope")
        profile_news = any(k in slots for k in ("room_area_m2", "has_children", "budget_vnd"))
        if sales_turn and not mentioned and not alt and (self.focus is None or (self.focus_by == "recommend" and profile_news)):
            rec = self._recommend(text)
            if rec == "ASK_NEED":
                goals.append("ask_need"); facts["need_slots_missing"] = [k for k in ("has_children", "budget_vnd", "room_area_m2") if k not in self.known]
                rec = None
            elif rec and rec != self.focus:
                old = self.focus
                self.focus, self.focus_by = rec, "recommend"
                facts["quote"] = self._quote(self._resolve_variant(rec, text), "advised"); goals.append("recommend")
                if old:
                    facts["alternative"] = self._quote(old, "alternative")
            if not rec and self.focus is None and "ask_need" not in goals and it in ("product_inquiry", "price_promo"):
                goals.append("ask_product")
        # --- báo giá (theo đúng biến thể khách đã nói)
        asks_price = it in ("price_promo", "negotiate", "product_inquiry") or (new_focus and new_focus != prev_focus) or bool(alt) or compare \
            or (it == "place_order" and asking) or "exchange_window_passed" in goals
        if sales_turn and "recommend" not in goals and asks_price:
            target = (alt or mentioned[-1]) if compare else self.focus
            if target and not compare and self._price_depends_on_size(target, text):
                if not self.size_asked:          # hỏi size 1 lần; khách không nói thì báo giá phổ biến kèm lưu ý
                    self.size_asked = True
                    goals.append("ask_size_for_price"); target = None
                else:
                    facts["size_note"] = "giá này cho size thường; size lớn có phụ thu và không áp một số khuyến mãi"
            if target:
                q = self._quote(self._resolve_variant(target, text), "alternative" if compare else "advised")
                if q.get("discontinued") and q.get("successor_sku"):
                    facts["discontinued_name"], facts["successor_name"] = q["name"], product_name(q["successor_sku"])
                    goals.append("discontinued")
                    if not compare:
                        self.focus = q["successor_sku"]
                    q = self._quote(self._resolve_variant(q["successor_sku"], text), "advised")
                if compare:
                    facts["alternative"] = q; goals.append("alternative_quote")
                else:
                    facts["quote"] = q
                    if q.get("in_stock") is False:
                        goals.append("out_of_stock"); facts["restock_expected"] = q.get("restock_expected")
                    else:
                        goals.append("quote")
                    claimed = [v for v in slots.get("claimed_prices", []) if v != q.get("final_price_vnd")]
                    if claimed and q.get("expired_promos"):
                        facts["claimed_price_vnd"] = claimed[0]; goals.append("explain_price_change")
        # --- giỏ hàng: tổng tiền / COD
        if self.cart and asking and re.search(r"\b(tong|het bao nhieu|tat ca|ca hai|giam gi|duoc giam)\b", f):
            facts["cart"] = self._cart_quote(text); goals.append("cart_total")
        if asking and re.search(r"\b(cod|thanh toan khi nhan)\b", f):
            tot = (facts.get("cart") or self._cart_quote(text) if self.cart else {}).get("total_vnd") if self.cart else (facts.get("quote") or {}).get("final_price_vnd")
            facts["cod_total_vnd"] = tot
            goals.append("cod_limit" if tot and tot > 10_000_000 else "cod_ok")
        if "?" in text and sales_turn and it != "place_order":
            hits = knowledge.search(text, k=2)                # câu hỏi phụ (bảo hành, ship…) → kèm trích chính sách
            if hits:
                facts.setdefault("policy", [{"chunk_id": h["chunk_id"], "text": h["text"][:600]} for h in hits])
        if it == "negotiate":
            goals.append("no_competitor_comment" if y("mentions_competitor", 0.5) else "refuse_discount")
        # --- chốt đơn: chỉ khi khách đồng ý và không còn đang hỏi; báo trước nếu giá đổi so với lần trước
        wants = it == "place_order" and (y("agrees_to_buy", 0.5) or self.router.backend == "rules")
        if wants:
            self.buy_intent = True
            if not self.cart and self.focus:
                self._cart_add(self.focus)
        pending = self.buy_intent and not asking and it not in ("callback", "negotiate", "order_change", "order_status") \
            and any(k in slots for k in ("address", "payment", "size", "color"))
        if self.orders_created and slots.get("address"):
            goals += self._update_address(slots["address"], facts)
        elif (wants and not asking) or pending:
            stale = [w for w in (self.brief or {}).get("stale_warnings", []) if self.focus and mt._parent(self.focus)[0]
                     and mt._parent(self.focus)[0]["sku"] in w and ("KM" in w or "giá" in w)]
            if stale and not self.price_change_told:
                self.price_change_told = True
                facts["quote"] = facts.get("quote") or self._quote(self._resolve_variant(self.focus, text), "advised")
                goals += ["stale_promo", "quote", "confirm_new_price"]
            else:
                goals += self._plan_order(text, facts)
        elif wants and asking and "quote" in goals:
            goals.append("confirm_order")
        if "stale_promo" in goals and not self.price_change_told:
            self.price_change_told = True
            if self.focus and "quote" not in facts:
                facts["quote"] = self._quote(self._resolve_variant(self.focus, text), "advised")
            goals.append("quote")
        # --- hẹn gọi lại
        if slots.get("callback_requested"):
            goals += self._plan_callback(slots["callback_requested"], facts)
        elif (it == "callback" and y("defers_decision", 0.5)) or y("defers_decision", 0.8):
            goals.append("defer_ack"); self.outcome = self.outcome or "hen_goi_lai"
        if not goals:
            goals.append("greet" if self.turn_no == 1 else "closing")
        return list(dict.fromkeys(goals)), facts

    # ------------------------------------------------------------------ giỏ hàng / biến thể
    def _cart_add(self, sku):
        if sku and sku not in self.cart and mt._parent(sku)[0]:
            par = mt._parent(sku)[0]["sku"]
            self.cart = [x for x in self.cart if mt._parent(x)[0]["sku"] != par] + [sku]

    def _resolve_variant(self, sku, text):
        p, v = mt._parent(sku)
        if not p or not p["variants"] or v:
            return sku
        return find_variant(p["sku"], text, self.known.get("size"), self.known.get("color")) or sku

    def _price_depends_on_size(self, sku, text):
        """Sản phẩm có biến thể mà chưa biết size, và giá thay đổi theo size (phụ thu size lớn / KM loại trừ size)."""
        p, v = mt._parent(sku)
        if not p or not p["variants"] or v or self._resolve_variant(sku, text) != sku:
            return False
        if any(x.get("price_delta_vnd") for x in p["variants"]):
            return True
        for pr in mt.PROMOS:
            if (p["sku"] in pr.get("applies_to", []) or any(p["category"].startswith(c) for c in pr.get("applies_to_categories", []))) \
                    and (pr.get("conditions") or {}).get("exclude_variant_size"):
                return True
        return False

    def _cart_quote(self, text):
        items = [self._resolve_variant(s, text) for s in self.cart]
        qs = [self._quote(s, "chosen", basket=[x for x in items if x != s]) for s in items]
        return {"items": [{"name": q["name"], "final_price_vnd": q["final_price_vnd"], "promo_names": q["promo_names"]} for q in qs],
                "total_vnd": sum(q["final_price_vnd"] or 0 for q in qs), "budget_vnd": self.known.get("budget_vnd")}

    def _update_address(self, address, facts):
        out = []
        for o in self.orders_created:
            r = self.tools.call("order.update", order_id=o["order_id"], action="update_address", reason=f"địa chỉ mới: {address}")
            out.append(r)
        facts["address_update"] = {"orders": [o["order_id"] for o in self.orders_created], "address": address}
        return ["address_updated"]

    def _plan_order(self, text, facts):
        c = self.customer or {}
        items = list(self.cart) or ([self.focus] if self.focus else [])
        if not items:
            return ["ask_product"]
        resolved = []
        for sku in items:
            r = self._resolve_variant(sku, text)
            p, v = mt._parent(r)
            if p and p["variants"] and not v:
                facts["need_variant_for"] = product_name(sku)
                return ["ask_variant"]
            resolved.append(r)
        new = [s for s in resolved if not any(o["sku"] == s for o in self.orders_created)]
        if not new:
            o = self.orders_created[-1]
            facts["order"] = {"order_id": o["order_id"], "total_vnd": o["total_vnd"], "estimated_delivery": o.get("estimated_delivery"),
                              "payment": self.known.get("payment", "COD"), "address": self.known.get("address"), "items": [product_name(o["sku"])]}
            return ["order_exists"]
        if not self.known.get("address") and self.expired.get("address") and re.search(r"(dia chi cu|cho cu|nhu cu)", fold(text)):
            facts["old_address"] = self.expired["address"]
            return ["confirm_old_address"]
        payment = self.known.get("payment", "COD")
        quotes = [self._quote(s, "chosen", basket=[x for x in new if x != s]) for s in new]
        total = sum(q["final_price_vnd"] or 0 for q in quotes)
        if any(q.get("in_stock") is False for q in quotes):
            bad = next(q for q in quotes if q.get("in_stock") is False)
            facts["quote"], facts["restock_expected"] = bad, bad.get("restock_expected")
            return ["out_of_stock"]
        if payment == "COD" and total > 10_000_000:
            facts["cod_total_vnd"] = total; facts["cart"] = {"items": [{"name": q["name"], "final_price_vnd": q["final_price_vnd"]} for q in quotes], "total_vnd": total}
            return ["cod_limit"]
        made = []
        for q in quotes:
            args = dict(customer_phone=c.get("phone") or self.phone, sku=q["sku"], qty=1, price_vnd=q["final_price_vnd"],
                        promo_code=(q["promo_codes"] or [None])[0], payment=payment, address=self.known.get("address"),
                        basket_skus=[x for x in new if x != q["sku"]] or None)
            r = self.tools.call("order.create", **args)
            if r.get("error") == "price_mismatch":
                args["price_vnd"] = r["expected_price_vnd"]; r = self.tools.call("order.create", **args)
            if r.get("error"):
                facts["order_error"] = r["error"]; return ["order_failed"]
            made.append({**r, "sku": q["sku"], "price_vnd": args["price_vnd"]})
        self.orders_created += made
        facts["order"] = {"order_id": ", ".join(o["order_id"] for o in made), "total_vnd": sum(o["total_vnd"] for o in made),
                          "estimated_delivery": made[0].get("estimated_delivery"), "payment": payment,
                          "address": self.known.get("address"), "items": [product_name(o["sku"]) for o in made]}
        sku = made[0]["sku"]
        self.known["product_chosen"] = sku
        self.known["order_id"] = made[0]["order_id"]
        if sku != mt._parent(sku)[0]["sku"]:
            self.known["variant_sku"] = sku
        self.outcome = "chot_don"
        goals = ["order_created"]
        if not self.known.get("address"):
            goals.append("ask_address")
        return goals

    def _customer_orders(self):
        c = self.customer or {}
        r = self.tools.call("order.status", customer_phone=c.get("phone") or self.phone)
        return r.get("orders", [])

    def _plan_order_change(self, text, facts):
        orders = self._customer_orders()
        if not orders:
            hits = knowledge.search(text, k=2)
            facts["policy"] = [{"chunk_id": h["chunk_id"], "text": h["text"][:600]} for h in hits]
            return ["policy_answer"] if hits else ["order_not_found"]
        want = self.known.get("variant_sku") or self.known.get("product_chosen")
        o = next((x for x in reversed(orders) if want and x.get("sku") == want), orders[-1])
        f = fold(text)
        od = o.get("created_on") or o.get("date")
        if od and (date.fromisoformat(self.today) - date.fromisoformat(od)).days > 7 + 4:   # 7 ngày từ khi nhận (~4 ngày giao)
            facts["old_order"] = {"order_id": o["order_id"], "product": product_name(o["sku"]), "date": od}
            self.focus, self.focus_by = o["sku"], "memory"
            return ["WINDOW_PASSED"]
        if re.search(r"tra hang|hoan tien|khong dung nua|tra lai", f):
            r = self.tools.call("order.update", order_id=o["order_id"], action="return", reason="khach yeu cau tra hang")
        else:
            parent, ov = mt._parent(o["sku"])
            m = None
            other = [s for s in find_products(text) if s != parent["sku"]]
            if other:
                new_sku = find_variant(other[0], text, None, None) or other[0]
                action = "exchange_product"
            else:
                m = re.search(r"(?:đổi|lên|sang|lấy|thành)\s*(?:size|cỡ|số)?\s*(\d{2}|xs|s|m|l|xl|xxl)\b", text.lower())
                size = m.group(1).upper() if m else self.pending_size
                if not ov or not size or str(size) == str(ov["size"]).upper():
                    facts["current_variant"] = product_name(o["sku"])
                    return ["ask_new_size"]
                self.pending_size = size
                new_sku = next((v["variant_sku"] for v in parent["variants"] if str(v["size"]).upper() == size and v["color"] == ov["color"]), None)
                if not new_sku:
                    return ["ask_variant"]
                action = "exchange_size"
            key = (o["order_id"], action, new_sku)
            if key in self.updates_done:              # khách xác nhận lại → không tạo yêu cầu đổi lần 2 (tránh tính phí lần 2)
                facts["update"] = self.updates_done[key]
                return ["order_updated"]
            if not re.search(r"(lam thu tuc|doi (cho|giup|luon)|dong y|ok|duoc|chot)", f) and m and "?" in text:
                facts["exchange_preview"] = {"order_id": o["order_id"], "new_variant": product_name(new_sku),
                                             "in_stock": self.tools.call("inventory.check", sku=new_sku).get("in_stock")}
                hits = knowledge.search("đổi size phí lần đầu", k=1)
                facts["policy"] = [{"chunk_id": h["chunk_id"], "text": h["text"][:600]} for h in hits]
                return ["exchange_offer"]
            r = self.tools.call("order.update", order_id=o["order_id"], action=action, new_variant_sku=new_sku)
            if not r.get("error"):
                self.updates_done[key] = public_view(r)
        if r.get("error"):
            facts["order_error"] = r["error"]
            if r.get("restock_expected"): facts["restock_expected"] = r["restock_expected"]
            return ["out_of_stock" if "out_of_stock" in r["error"] else "order_failed"]
        facts["update"] = public_view(r)
        return ["order_updated"]

    def _plan_callback(self, when, facts):
        c = self.customer or {}
        dt = datetime.fromisoformat(when)
        reason = None
        while dt.date().isoformat() in mt.HOLIDAYS or dt.weekday() == 6:
            reason = f"ngày {_ddmm(dt.date().isoformat())} bên em nghỉ" if dt.date().isoformat() in mt.HOLIDAYS else "chủ nhật bên em nghỉ"
            dt += timedelta(days=1)
        at = dt.strftime("%Y-%m-%dT%H:%M")
        r = self.tools.call("schedule.callback", customer_phone=c.get("phone") or self.phone, callback_at=at,
                            note=f"hẹn gọi lại: {self.known.get('blocker') or ''}".strip())
        facts["callback"] = {**r, "moved_reason": reason, "weekday": ["thứ hai", "thứ ba", "thứ tư", "thứ năm", "thứ sáu", "thứ bảy", "chủ nhật"][dt.weekday()],
                             "ddmm": _ddmm(dt.date().isoformat())}
        self.known["callback_requested"] = at
        self.outcome = self.outcome or "hen_goi_lai"
        return ["callback_scheduled"]

    def _handoff_brief(self, text, reason):
        c = self.customer or {}
        conv = " / ".join(h["text"] for h in self.history[-6:]) or text
        return {"customer_phone": c.get("phone") or self.phone, "customer_name": c.get("name"), "customer_id": c.get("customer_id"),
                "channel": self.channel if self.channel in ("hotline", "chat_fanpage", "zalo_oa") else "other",
                "escalation_reason": reason, "escalation_reason_detail": text,
                "conversation_summary": f"Khách {c.get('name') or ''} ({self.call_name}): {conv}"[:780].ljust(20, "."),
                "product_advised": self.focus or self.known.get("product_advised"),
                "price_quoted_vnd": (self.quote or {}).get("final_price_vnd") or self.known.get("price_quoted_vnd"),
                "facts_confirmed": {k: v for k, v in self.known.items() if k != "self_name"},
                "open_questions": [text], "sentiment": "binh_thuong",
                "next_action": "trả lời câu hỏi chuyên môn của khách rồi tiếp tục tư vấn/chốt sản phẩm đang bàn",
                "history_refs": [self.session_id], "generated_at": datetime.now().isoformat(timespec="seconds")}

    # ================================================================== ghi nhớ
    def _remember(self, slots, route):
        c = self.customer or {}
        cid = c.get("customer_id")
        if not cid or self.candidates or self.deleted:
            return [{"key": "*", "value": None, "op": "delete", "source": f"{self.call_name}#turn{self.turn_no}", "customer_id": cid}] \
                if self.deleted and self.turn_no == self._deleted_turn else []
        src = f"{self.call_name}#turn{self.turn_no}"
        writes = []
        for k, v in slots.items():
            if k in ("self_name", "claimed_prices"):
                continue
            w = self.mem.write_fact(cid, k, v, src, self.session_id, self.today)
            if w: writes.append(w)
        if self.focus:
            q = self.quote if self.quote and self.quote["sku"] in (self.focus, mt._parent(self.focus)[0] and mt._parent(self.focus)[0]["sku"]) else None
            for k, v in (("product_advised", self.focus), ("price_quoted_vnd", q and q["final_price_vnd"]),
                         ("promo_code", q and (q["promo_codes"] or [None])[0]), ("promo_expiry", q and q["promo_end"])):
                if v is not None:
                    w = self.mem.write_fact(cid, k, v, src, self.session_id, self.today)
                    if w: writes.append(w); self.known[k] = v
        for k in ("product_chosen", "order_id", "variant_sku"):
            if self.known.get(k):
                w = self.mem.write_fact(cid, k, self.known[k], src, self.session_id, self.today)
                if w: writes.append(w)
        return writes

    def end(self):
        c = self.customer or {}
        if not c.get("customer_id") or self.deleted:
            return
        parts = []
        if self.focus:
            parts.append(f"tư vấn {product_name(self.focus)}" + (f" giá {self.known.get('price_quoted_vnd'):,}đ".replace(",", ".") if self.known.get("price_quoted_vnd") else ""))
        if self.orders_created:
            parts.append("đã lên đơn " + ", ".join(o["order_id"] for o in self.orders_created))
        if self.known.get("blocker") and self.outcome != "chot_don":
            parts.append(f"rào cản: {self.known['blocker']}")
        if self.known.get("callback_requested"):
            parts.append(f"hẹn gọi lại {self.known['callback_requested']}")
        summary = f"{self.call_name} ({_ddmm(self.today)}, {self.channel}): " + "; ".join(parts or ["trao đổi chung"])
        blockers = [self.known["blocker"]] if self.known.get("blocker") and self.outcome != "chot_don" else []
        self.mem.add_session(self.session_id, c["customer_id"], self.channel, self.today, self.outcome or "khac", summary, blockers)
