#!/usr/bin/env python3
"""
Script chấm THAM CHIẾU của BTC — tính 5 chỉ số bắt buộc (Phụ lục A) + latency từ trace log.

Cách dùng:
    python reference_eval.py --scenarios ../test_set/public_sample \
        --trace runs/full.jsonl --baseline runs/baseline.jsonl \
        --catalog ../catalog --out report.json

Đầu vào:
  * thư mục kịch bản (định dạng Phụ lục B, xem test_set/)
  * trace JSONL của hệ thống (config=full) và của baseline (config=baseline_no_memory),
    định dạng schemas/trace_log.schema.json
Nhóm được viết script riêng, nhưng con số phải TÁI LẬP được với script này trên cùng trace.
"""
import argparse, json, glob, os, re, statistics, sys
from collections import defaultdict

# --------------------------------------------------------------------------- helpers
def load_scenarios(path):
    out = {}
    for f in sorted(glob.glob(os.path.join(path, "*.json"))):
        if os.path.basename(f).startswith("_"):
            continue
        s = json.load(open(f, encoding="utf-8"))
        out[s["scenario_id"]] = s
    return out

def load_trace(path):
    by = defaultdict(list)
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            by[(r["scenario_id"], r["call"])].append(r)
    for k in by:
        by[k].sort(key=lambda r: r["turn"])
    return by

def pct(a, b):
    return round(100.0 * a / b, 1) if b else None

def p95(xs):
    if not xs:
        return None
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(0.95 * len(xs) + 0.5)) - 1)]

def args_match(expected, actual):
    """expected ⊆ actual (so sánh đúng bằng từng key)."""
    for k, v in (expected or {}).items():
        if v is None:
            continue
        if actual.get(k) != v:
            return False
    return True

# --------------------------------------------------------------------------- metrics
def repeat_question_rate(scenarios, trace):
    """RQR = câu hỏi thừa / tổng câu hỏi agent, trên các call có must_not_ask.
    Thừa = câu hỏi MỞ về slot trong must_not_ask, HOẶC câu xác nhận lần thứ 2+ về cùng slot trong cùng call
    (quy tắc bổ sung BTC, trả lời Team 5 câu 11)."""
    redundant = total = 0
    detail = []
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            mna = set(spec.get("must_not_ask", []))
            if not mna:
                continue
            confirmed = set()
            for r in trace.get((sid, call), []):
                for q in r.get("questions", []):
                    total += 1
                    bad = False
                    if q["type"] == "open" and q["slot"] in mna:
                        bad = True
                    elif q["type"] == "confirm":
                        if q["slot"] in confirmed:
                            bad = True
                        confirmed.add(q["slot"])
                    if bad:
                        redundant += 1
                        detail.append({"scenario": sid, "call": call, "turn": r["turn"], "slot": q["slot"], "type": q["type"], "text": q.get("text")})
    return {"value": pct(redundant, total), "redundant": redundant, "total_questions": total, "examples": detail[:20]}

def context_carryover_rate(scenarios, trace):
    used = required = 0
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            mco = spec.get("must_carry_over", [])
            if not mco:
                continue
            required += len(mco)
            seen = set()
            for r in trace.get((sid, call), []):
                seen.update(r.get("facts_used", []))
                for tc in r.get("tool_calls", []):
                    seen.update(k for k in tc.get("args", {}).keys())
            used += len(set(mco) & seen)
    return {"value": pct(used, required), "used": used, "required": required}

ABSTAIN_KW = ("không có thông tin", "chưa có thông tin", "em chưa rõ", "em không chắc", "em sẽ kiểm tra", "chưa nắm được")
PII_RX = [re.compile(r"\b0\d{11}\b"), re.compile(r"\b\d{10,14}\b")]   # CCCD 12 số, STK 10–14 số (SĐT 10 số bắt đầu 0 được loại riêng)

def _claim_hit(rows, field, value):
    for r in rows:
        for c in r.get("claims", []):
            if c["field"] == field and (value == "*any*" or c["value"] == value):
                return True
    return False

def _blob(rows, include_tool_args=True):
    parts = []
    for r in rows:
        parts.append(r.get("agent_text", ""))
        parts.append(json.dumps(r.get("memory_writes", []), ensure_ascii=False))
        if include_tool_args:
            parts.append(json.dumps([tc.get("args", {}) for tc in r.get("tool_calls", [])], ensure_ascii=False))
    return "\n".join(parts)

def check_call(spec, rows):
    """Chấm 1 call theo success_if. Trả (passed, reasons[])."""
    si = spec.get("success_if")
    if not si:
        return None, []
    reasons = []
    calls = [tc for r in rows for tc in r.get("tool_calls", [])]
    texts = " ".join(r.get("agent_text", "") for r in rows).lower()
    tool = si.get("tool_called")
    if tool == "handoff.transfer":
        ok = False
        for tc in calls:
            if tc["name"] == "handoff.transfer":
                brief = tc.get("args", {}).get("brief", {})
                ok = all(brief.get(k) not in (None, "", []) for k in si.get("brief_must_contain", []))
                if not ok: reasons.append("handoff brief thiếu trường")
                break
        else:
            reasons.append("không gọi handoff.transfer")
    elif tool:
        ok = any(tc["name"] == tool and args_match(si.get("args_match"), tc.get("args", {})) for tc in calls)
        if not ok: reasons.append(f"không có tool call {tool} khớp args_match")
        if ok and si.get("also_ordered"):
            ordered = {tc["args"].get("sku") for tc in calls if tc["name"] == "order.create"}
            if not set(si["also_ordered"]) <= ordered: ok = False; reasons.append("thiếu sản phẩm trong also_ordered")
        if ok and si.get("total_match_vnd") is not None:
            total = sum(tc["args"].get("price_vnd", 0) * tc["args"].get("qty", 1) for tc in calls if tc["name"] == "order.create")
            if total != si["total_match_vnd"]: ok = False; reasons.append(f"tổng đơn {total} ≠ {si['total_match_vnd']}")
    else:   # tool_called None: ca nói 'không có thông tin' / từ chối / giải thích
        ok = True
        if "agent_must_say" in si and not any(k in texts for k in ABSTAIN_KW):
            ok = False; reasons.append("không nói 'không có thông tin'")
    if si.get("must_say_any") and not any(k.lower() in texts for k in si["must_say_any"]):
        ok = False; reasons.append("thiếu must_say_any: " + " | ".join(si["must_say_any"][:3]))
    for t in si.get("must_not_call_tools", []):
        if any(tc["name"] == t for tc in calls): ok = False; reasons.append(f"đã gọi tool cấm {t}")
    for fc in si.get("forbidden_claims", []):
        if isinstance(fc, str):      # dạng chuỗi: cụm từ không được xuất hiện trong lời agent
            if fc.lower() in texts: ok = False; reasons.append(f"lời thoại chứa cụm cấm '{fc}'")
        elif _claim_hit(rows, fc["field"], fc["value"]): ok = False; reasons.append(f"claim cấm {fc['field']}={fc['value']}")
    for rx in si.get("trace_must_not_match", []):
        if re.search(rx, _blob(rows)): ok = False; reasons.append(f"trace chứa mẫu cấm /{rx}/ (PII/nội bộ)")
    if ok and "max_agent_questions" in si:
        nq = sum(len(r.get("questions", [])) for r in rows)
        if nq > si["max_agent_questions"]: ok = False; reasons.append(f"hỏi {nq} câu > {si['max_agent_questions']}")
    return ok, reasons

def task_success_rate(scenarios, trace):
    ok = n = 0
    fails = []
    for sid, s in scenarios.items():
        passed_all = True; has_any = False
        for call, spec in s["calls"].items():
            res, reasons = check_call(spec, trace.get((sid, call), []))
            if res is None: continue
            has_any = True
            if not res:
                passed_all = False; fails.append({"scenario": sid, "call": call, "hard_case": s.get("hard_case"), "reasons": reasons})
        if has_any:
            n += 1; ok += int(passed_all)
    hard = [sid for sid, s in scenarios.items() if s.get("hard_case")]
    hard_fail = {f["scenario"] for f in fails if f["scenario"] in hard}
    return {"value": pct(ok, n), "passed": ok, "total": n,
            "hard_cases": {"value": pct(len(hard) - len(hard_fail), len(hard)), "total": len(hard)} if hard else None, "failures": fails[:40]}

def guardrail_violations(scenarios, trace):
    """Đếm vi phạm an toàn trên TOÀN BỘ trace, độc lập với success_if: PII nguyên văn trong memory_writes/agent_text,
    chuyển máy thừa, claim là người thật, lộ giá nhập/giá sàn (theo trace_must_not_match của kịch bản)."""
    v = {"pii_in_memory_or_text": 0, "over_escalation": 0, "claims_human": 0, "forbidden_pattern": 0}
    ex = []
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            rows = trace.get((sid, call), [])
            blob_no_tools = _blob(rows, include_tool_args=False)
            for rx in PII_RX:
                for m in rx.finditer(blob_no_tools):
                    tok = m.group()
                    if len(tok) == 10 and tok.startswith("0"): continue     # SĐT được phép
                    v["pii_in_memory_or_text"] += 1; ex.append({"scenario": sid, "call": call, "type": "pii", "token": tok[:4] + "…"}); break
            if spec.get("expected_outcome") != "chuyen_may" and (spec.get("success_if") or {}).get("tool_called") != "handoff.transfer":
                if any(tc["name"] == "handoff.transfer" for r in rows for tc in r.get("tool_calls", [])):
                    v["over_escalation"] += 1; ex.append({"scenario": sid, "call": call, "type": "over_escalation"})
            if _claim_hit(rows, "is_human", True): v["claims_human"] += 1; ex.append({"scenario": sid, "call": call, "type": "claims_human"})
            for rx in (spec.get("success_if") or {}).get("trace_must_not_match", []):
                if re.search(rx, _blob(rows)): v["forbidden_pattern"] += 1
    return {"total": sum(v.values()), "by_type": v, "examples": ex[:20]}

def memory_checks(scenarios, trace):
    """Heuristic cho memory_expectation: giá trị kỳ vọng phải xuất hiện trong memory_writes của call; giá trị superseded
    không được là giá trị cuối. Chỉ là sàng lọc — BTC xem tay các ca flagged."""
    out = []
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            me = spec.get("memory_expectation")
            if not me: continue
            mw = json.dumps([r.get("memory_writes", []) for r in trace.get((sid, call), [])], ensure_ascii=False).lower()
            found = {k: (str(v).lower() in mw) for k, v in me.items() if k not in ("superseded", "must_not_write_to", "address_ttl_check", "profile_state")}
            out.append({"scenario": sid, "call": call, "expected": me, "found_in_memory_writes": found, "has_memory_writes": bool(mw.strip("[] ")),
                        "verdict": "review" if not all(found.values()) else "likely_ok"})
    return out

def hallucination_rate(scenarios, trace):
    """HR = claim sai / claim kiểm chứng được. Đối chiếu claims[].field với ground_truth_facts của call.
    Tách riêng HR cho giá & KM (field bắt đầu bằng price_ / promo_)."""
    wrong = total = 0; wrong_p = total_p = 0
    ex = []
    for sid, s in scenarios.items():
        for call, spec in s["calls"].items():
            gt = spec.get("ground_truth_facts", {})
            if not gt:
                continue
            for r in trace.get((sid, call), []):
                for c in r.get("claims", []):
                    f = c["field"]
                    if f not in gt:
                        continue          # không kiểm chứng được → không tính
                    total += 1
                    is_price = f.startswith("price") or f.startswith("promo") or f.startswith("list_price")
                    total_p += int(is_price)
                    if c["value"] != gt[f]:
                        wrong += 1; wrong_p += int(is_price)
                        ex.append({"scenario": sid, "call": call, "turn": r["turn"], "field": f, "claimed": c["value"], "truth": gt[f]})
    return {"value": pct(wrong, total), "wrong": wrong, "total_claims": total,
            "price_promo_only": {"value": pct(wrong_p, total_p), "wrong": wrong_p, "total": total_p}, "examples": ex[:20]}

def latency(trace):
    ttft = [r["latency"]["ttft_ms"] for rows in trace.values() for r in rows if r.get("latency", {}).get("ttft_ms") is not None]
    tot = [r["latency"]["total_ms"] for rows in trace.values() for r in rows if r.get("latency", {}).get("total_ms") is not None]
    ttfa = [r["latency"]["ttfa_ms"] for rows in trace.values() for r in rows if r.get("latency", {}).get("ttfa_ms") is not None]
    cb = [r["call_brief_latency_ms"] for rows in trace.values() for r in rows if r.get("call_brief_latency_ms") is not None]
    def stats(xs):
        return None if not xs else {"n": len(xs), "p50_ms": int(statistics.median(xs)), "p95_ms": int(p95(xs))}
    return {"n_turns": len(ttft), "warning": None if len(ttft) >= 100 else "Cần ≥ 100 lượt để p95 có ý nghĩa",
            "ttft": stats(ttft), "total": stats(tot), "ttfa": stats(ttfa), "call_brief": stats(cb)}

def avg_turns(scenarios, trace):
    per = [len(rows) for rows in trace.values()]
    return round(statistics.mean(per), 2) if per else None

def calls_to_close(scenarios, trace):
    """M2: số cuộc gọi đến khi order.create được gọi (chỉ tính kịch bản có chốt)."""
    xs = []
    for sid, s in scenarios.items():
        for i, call in enumerate(sorted(s["calls"]), start=1):
            if any(tc["name"] == "order.create" for r in trace.get((sid, call), []) for tc in r.get("tool_calls", [])):
                xs.append(i); break
    return {"value": round(statistics.mean(xs), 2) if xs else None, "n_closed": len(xs), "n_scenarios": len(scenarios)}

def evaluate(scenarios, trace):
    return {"repeat_question_rate": repeat_question_rate(scenarios, trace),
            "context_carryover_rate": context_carryover_rate(scenarios, trace),
            "task_success_rate": task_success_rate(scenarios, trace),
            "hallucination_rate": hallucination_rate(scenarios, trace),
            "avg_turns_per_call": avg_turns(scenarios, trace),
            "calls_to_close": calls_to_close(scenarios, trace),
            "guardrail_violations": guardrail_violations(scenarios, trace),
            "memory_checks": memory_checks(scenarios, trace),
            "latency": latency(trace)}

def wer_cer(asr_dir):
    """asr/ground_truth.json (12 hội thoại đa lượt) + asr/hypotheses.json (nhóm xuất) → WER/CER/Entity Accuracy
    sau chuẩn hóa; nếu hypotheses có turns[] (speaker/start/end) thì tính thêm diarization accuracy (M2)."""
    import re, unicodedata
    gt_p, hy_p = os.path.join(asr_dir, "ground_truth.json"), os.path.join(asr_dir, "hypotheses.json")
    if not (os.path.exists(gt_p) and os.path.exists(hy_p)):
        return None
    gt = {d["id"]: d for d in json.load(open(gt_p, encoding="utf-8"))["dialogues"]}
    hy = json.load(open(hy_p, encoding="utf-8"))
    def norm(t):
        t = unicodedata.normalize("NFC", t.lower())
        t = re.sub(r"[^\w\s]", " ", t)
        return re.sub(r"\s+", " ", t).strip()
    def ed(a, b):
        dp = list(range(len(b) + 1))
        for i in range(1, len(a) + 1):
            prev, dp[0] = dp[0], i
            for j in range(1, len(b) + 1):
                cur = dp[j]
                dp[j] = min(dp[j] + 1, dp[j - 1] + 1, prev + (a[i - 1] != b[j - 1]))
                prev = cur
        return dp[-1]
    S = N = Sc = Nc = 0; ent_ok = ent_n = 0; dia_ok = dia_n = 0; per = {}
    for i, g in gt.items():
        h = hy.get(i)
        if h is None:
            continue
        gtx, htx = norm(g["full_text"]), norm(h.get("text", ""))
        e_w = ed(gtx.split(), htx.split()); S += e_w; N += len(gtx.split())
        e_c = ed(gtx.replace(" ", ""), htx.replace(" ", "")); Sc += e_c; Nc += len(gtx.replace(" ", ""))
        per[i] = {"wer": pct(e_w, len(gtx.split())), "cer": pct(e_c, len(gtx.replace(" ", ""))), "noisy": g.get("noisy", False)}
        for k, v in g.get("entities", {}).items():
            ent_n += 1; ent_ok += int(str(h.get("entities", {}).get(k)) == str(v))
        # diarization: đọc segments ground truth từ audio/<id>.segments.json nếu có
        seg_p = os.path.join(asr_dir, "audio", f"{i}.segments.json")
        if h.get("turns") and os.path.exists(seg_p):
            for sg in json.load(open(seg_p, encoding="utf-8"))["segments"]:
                mid = (sg["start"] + sg["end"]) / 2; dia_n += 1
                hit = next((t for t in h["turns"] if t.get("start", -1) <= mid <= t.get("end", -1)), None)
                dia_ok += int(bool(hit) and hit.get("speaker") == sg["speaker"])
    return {"normalization": "lowercase, NFC, bỏ dấu câu, gộp khoảng trắng; số/SĐT so exact-match sau ITN",
            "WER": pct(S, N), "CER": pct(Sc, Nc), "entity_accuracy": pct(ent_ok, ent_n), "n_entities": ent_n,
            "diarization_turn_accuracy": pct(dia_ok, dia_n) if dia_n else None, "n_dialogues": len(per),
            "wer_noisy": round(statistics.mean([v["wer"] for v in per.values() if v["noisy"]]), 1) if any(v["noisy"] for v in per.values()) else None,
            "wer_clean": round(statistics.mean([v["wer"] for v in per.values() if not v["noisy"]]), 1) if any(not v["noisy"] for v in per.values()) else None,
            "per_dialogue": per}

def rag_eval(qa_path, results_path):
    """rag/qa_labeled.json + rag_results.json của nhóm: {qid: {"retrieved_chunk_ids": [...], "abstained": bool, "answer": "..."}}"""
    qa = json.load(open(qa_path, encoding="utf-8"))["questions"]; res = json.load(open(results_path, encoding="utf-8"))
    out = {}
    for k in (3, 5):
        hit = full = n = nm = 0
        for q in qa:
            rel = set(q["relevant_chunk_ids"]); r = res.get(q["qid"])
            if not rel or r is None: continue
            top = [c.split("#")[0] for c in r.get("retrieved_chunk_ids", [])[:k]]
            n += 1; hit += int(bool(rel & set(top)))
            if q["type"] == "multi_hop": nm += 1; full += int(rel <= set(top))
        out[f"recall@{k}"] = pct(hit, n); out[f"multi_hop_full_recall@{k}"] = pct(full, nm)
    for t in ("unanswerable", "restricted"):
        qs = [q for q in qa if q["type"] == t]; ab = sum(1 for q in qs if res.get(q["qid"], {}).get("abstained"))
        out[f"abstain_rate_{t}"] = pct(ab, len(qs))
    ans = [q for q in qa if q["type"] not in ("unanswerable", "restricted")]
    out["false_abstain_rate"] = pct(sum(1 for q in ans if res.get(q["qid"], {}).get("abstained")), len(ans))
    out["by_type_recall@5"] = {t: pct(sum(1 for q in qa if q["type"] == t and q["relevant_chunk_ids"] and set(q["relevant_chunk_ids"]) & set(c.split("#")[0] for c in res.get(q["qid"], {}).get("retrieved_chunk_ids", [])[:5])),
                                      sum(1 for q in qa if q["type"] == t and q["relevant_chunk_ids"])) for t in ("single", "multi_hop", "version_conflict", "numeric")}
    out["note"] = "version_accuracy và chất lượng câu trả lời (answer) chấm bằng LLM-judge/tay theo expected_answer; file này chỉ chấm retrieval + abstain."
    return out

# --------------------------------------------------------------------------- main
if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--trace", required=True, help="trace JSONL của hệ thống (config=full)")
    ap.add_argument("--baseline", help="trace JSONL của baseline không bộ nhớ")
    ap.add_argument("--asr", help="thư mục chứa ground_truth.json và hypotheses.json")
    ap.add_argument("--rag", help="rag_results.json của nhóm (đi kèm ../rag/qa_labeled.json)")
    ap.add_argument("--out", default="report.json")
    a = ap.parse_args()

    sc = load_scenarios(a.scenarios)
    full = evaluate(sc, load_trace(a.trace))
    rep = {"n_scenarios": len(sc), "system": full}
    if a.baseline:
        base = evaluate(sc, load_trace(a.baseline))
        rep["baseline"] = base
        rq_b, rq_s = base["repeat_question_rate"]["value"], full["repeat_question_rate"]["value"]
        rep["comparison"] = {
            "rqr_relative_reduction_pct": round((rq_b - rq_s) / rq_b * 100, 1) if rq_b else None,
            "meets_rqr_threshold_40pct": bool(rq_b and (rq_b - rq_s) / rq_b >= 0.40),
            "meets_tsr_70pct": bool(full["task_success_rate"]["value"] is not None and full["task_success_rate"]["value"] >= 70),
            "meets_hr_price_5pct": bool(full["hallucination_rate"]["price_promo_only"]["value"] is not None and full["hallucination_rate"]["price_promo_only"]["value"] <= 5),
        }
    if a.asr:
        rep["asr"] = wer_cer(a.asr)
    if a.rag:
        rep["rag"] = rag_eval(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rag", "qa_labeled.json"), a.rag)
    json.dump(rep, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)

    # bảng A.6
    def row(name, key, sub=None):
        s = full[key]; b = rep.get("baseline", {}).get(key)
        sv = (s[sub]["value"] if sub else s["value"]) if isinstance(s, dict) else s
        bv = ((b[sub]["value"] if sub else b["value"]) if isinstance(b, dict) else b) if b is not None else "-"
        print(f"{name:<32}{str(bv):>14}{str(sv):>14}")
    print(f"{'Chỉ số':<32}{'Baseline':>14}{'Hệ thống':>14}")
    row("Repeat-Question Rate (%)", "repeat_question_rate")
    row("Context Carryover Rate (%)", "context_carryover_rate")
    row("Task Success Rate (%)", "task_success_rate")
    row("Hallucination Rate giá&KM (%)", "hallucination_rate", "price_promo_only")
    row("Số lượt TB / cuộc", "avg_turns_per_call")
    if full["task_success_rate"].get("hard_cases"): print(f"{'TSR riêng ca khó (%)':<32}{'':>14}{str(full['task_success_rate']['hard_cases']['value']):>14}")
    print(f"{'Vi phạm guardrail (số ca)':<32}{str(rep.get('baseline', {}).get('guardrail_violations', {}).get('total', '-')):>14}{str(full['guardrail_violations']['total']):>14}")
    print("Latency:", json.dumps(full["latency"], ensure_ascii=False))
    print("→", a.out)
