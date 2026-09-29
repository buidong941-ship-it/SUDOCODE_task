#!/usr/bin/env python3
"""Sinh trace VÍ DỤ (giả lập agent lý tưởng và baseline hỏi lại) để nhóm thấy định dạng và chạy thử reference_eval.py.
   python make_example_trace.py ../test_set/public_sample  → runs/full.jsonl, runs/baseline.jsonl"""
import json, glob, os, random, sys
random.seed(1)
src = sys.argv[1] if len(sys.argv) > 1 else "../test_set/public_sample"
os.makedirs("runs", exist_ok=True)
full, base = open("runs/full.jsonl", "w", encoding="utf-8"), open("runs/baseline.jsonl", "w", encoding="utf-8")
for f in sorted(glob.glob(os.path.join(src, "*.json"))):
    if os.path.basename(f).startswith("_"): continue
    s = json.load(open(f, encoding="utf-8"))
    for call, spec in s["calls"].items():
        gt = spec.get("ground_truth_facts", {}); si = spec.get("success_if") or {}
        mna = spec.get("must_not_ask", []); mco = spec.get("must_carry_over", [])
        for cfg, out in (("full", full), ("baseline_no_memory", base)):
            turns = spec["customer_turns"]
            for t, ctext in enumerate(turns, start=1):
                row = dict(run_id="example", config=cfg, scenario_id=s["scenario_id"], call=call, turn=t, customer_text=ctext,
                           agent_text="", questions=[], facts_used=[], claims=[], tool_calls=[],
                           latency=dict(ttft_ms=random.randint(600, 2500), total_ms=random.randint(2500, 7000), ttfa_ms=None))
                if t == 1 and call != "call_1":
                    row["call_brief_latency_ms"] = random.randint(800, 4000) if cfg == "full" else None
                    if cfg == "full":
                        row["facts_used"] = list(mco)
                        row["agent_text"] = "Dạ em chào " + s["honorific"] + ", hôm trước bên em có tư vấn sản phẩm rồi ạ, mình còn băn khoăn gì không ạ?"
                        row["questions"] = [dict(slot="blocker", type="confirm", text="mình còn băn khoăn gì không ạ?")]
                    else:
                        row["agent_text"] = "Dạ anh/chị quan tâm sản phẩm nào ạ? Nhà mình bao nhiêu m², ngân sách khoảng bao nhiêu?"
                        row["questions"] = [dict(slot=x, type="open", text="hỏi " + x) for x in mna[:3]]
                if t == 2 and gt:
                    if cfg == "full":
                        row["claims"] = [dict(field=k, value=v) for k, v in gt.items() if k.startswith(("price", "promo", "in_stock", "delivery"))]
                    else:  # baseline hay báo lại giá cũ / bịa KM
                        row["claims"] = [dict(field=k, value=(v if random.random() > 0.3 else (v - 500000 if isinstance(v, int) and v > 1000000 else (not v if isinstance(v, bool) else v)))) for k, v in gt.items() if k.startswith(("price", "promo"))]
                if t == len(turns) and si.get("tool_called"):
                    if si["tool_called"] == "handoff.transfer":
                        args = dict(brief=dict(customer_phone=s["customer_phone"], customer_name=s["customer_name"], escalation_reason="cau_hoi_y_te",
                                               conversation_summary="Khách mua máy hút sữa cho em gái, hỏi câu y tế về kháng sinh.", product_advised="SKU-MB-PUMP1",
                                               price_quoted_vnd=4290000, open_questions=["uống kháng sinh hút sữa được không"], next_action="tư vấn y tế rồi chốt", generated_at="2026-10-15T10:00:00"))
                    else:
                        args = dict(si.get("args_match", {})); args.setdefault("customer_phone", s["customer_phone"])
                    if cfg == "full" or random.random() > 0.4:
                        row["tool_calls"] = [dict(name=si["tool_called"], args=args, result={"ok": True})]
                if si.get("agent_must_say") and t == 1:
                    row["agent_text"] = "Dạ câu này em chưa có thông tin, em ghi nhận và kiểm tra lại với kỹ thuật rồi báo chị ạ." if cfg == "full" else "Dạ có ạ, máy lọc được radon luôn ạ."
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
print("→ runs/full.jsonl, runs/baseline.jsonl")
