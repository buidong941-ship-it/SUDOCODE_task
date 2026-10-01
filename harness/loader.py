"""Đọc kịch bản (định dạng test_set/public_sample) và CHỈ lộ phần agent được thấy.

Agent nhận: lượt khách (customer_turns_asr nếu có, ngược lại customer_turns), kênh, định danh kênh, ngày gọi, SĐT gọi đến,
seed_history (nạp vào bộ nhớ như lịch sử CRM). Bị ẩn: facts_established, must_*, success_if, ground_truth_facts,
memory_expectation, expected_outcome, notes, customer_name, _meta — đó là đáp án để chấm.
"""
import glob
import json
import os
from datetime import date, timedelta

REF_DATE = "2026-10-15"


def load_scenarios(path):
    files = sorted(glob.glob(os.path.join(path, "**", "*.json"), recursive=True)) if os.path.isdir(path) else [path]
    out = []
    for f in files:
        b = os.path.basename(f)
        if b.startswith(("_", "manifest")) or b in ("validate_report.json", "report.json"):
            continue
        s = json.load(open(f, encoding="utf-8"))
        if isinstance(s, dict) and "calls" in s and "scenario_id" in s:
            out.append(s)
    return out


def agent_view(s):
    """Kịch bản → danh sách cuộc gọi chỉ chứa thông tin agent được biết."""
    calls, prev = [], None
    for name in sorted(s["calls"], key=lambda c: int(c.split("_")[1])):
        c = s["calls"][name]
        if c.get("call_date"):
            d = c["call_date"]
        elif prev is None:
            d = (date.fromisoformat(REF_DATE) + timedelta(days=int(c.get("days_later", 0)))).isoformat()
        else:
            d = (date.fromisoformat(prev) + timedelta(days=int(c.get("days_later", 0)))).isoformat()
        prev = d
        turns = c.get("customer_turns_asr") or c.get("customer_turns") or []
        calls.append({"call": name, "date": d, "channel": c.get("channel", "hotline"), "channel_identity": c.get("channel_identity"),
                      "input_mode": c.get("input_mode") or ("asr_transcript" if c.get("customer_turns_asr") else "text"),
                      "turns": turns, "seed_history": c.get("seed_history", [])})
    return {"scenario_id": s["scenario_id"], "phone": s["customer_phone"], "calls": calls}
