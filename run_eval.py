#!/usr/bin/env python3
"""Chạy hệ thống trên một thư mục kịch bản và xuất trace JSONL theo schemas/trace_log.schema.json.

    python run_eval.py --scenarios test_set/public_sample --config full --out runs/r0/full.jsonl
    python run_eval.py --scenarios test_set/public_sample --config baseline_no_memory --out runs/r0/baseline.jsonl
    python eval/reference_eval.py --scenarios test_set/public_sample --trace runs/r0/full.jsonl --baseline runs/r0/baseline.jsonl

Baseline và full chạy CÙNG code, cùng model, cùng tham số; chỉ khác: baseline không đọc bộ nhớ phiên trước.
Mỗi kịch bản có namespace bộ nhớ riêng (<run_id>:<config>:<scenario_id>) và trạng thái mock được reset.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)


def run_scenario(args):
    scen, config, run_id, router_backend, gen_backend = args
    from core.llm.generator import Generator
    from core.llm.router import Router
    from harness.agent import CallSession
    from harness.loader import agent_view
    from harness.memory import Memory
    from harness.tools import ToolBox

    view = agent_view(scen)
    sid = view["scenario_id"]
    mem = Memory(f"{run_id}:{config}:{sid}", read_enabled=(config == "full"))
    mem.wipe()
    ToolBox.reset_world()
    router, gen = Router(router_backend), Generator(gen_backend)
    rows = []
    try:
        for c in view["calls"]:
            sess = CallSession(memory=mem, today=c["date"], call_name=c["call"], session_id=f"{sid}:{c['call']}",
                               channel=c["channel"], channel_identity=c["channel_identity"],
                               phone=view["phone"] if c["channel"] == "hotline" else None,
                               input_mode=c["input_mode"], router=router, generator=gen, config=config)
            # lịch sử phiên cũ (seed_history) = dữ liệu CRM có trước cuộc gọi → nạp vào bộ nhớ
            if c["seed_history"]:
                sess.phone = sess.phone or view["phone"]
            sess.start()
            if c["seed_history"] and sess.customer:
                for h in c["seed_history"]:
                    cid = h.get("customer_id") or sess.customer["customer_id"]
                    sess.import_old_session(h, cid)
                if mem.read_enabled:   # nạp lại sau khi import
                    sess._bind(sess.customer["customer_id"], sess.customer["name"], sess.customer["honorific"], sess.customer["phone"], None)
                    sess.brief = sess._build_brief(); sess.brief["latency_ms"] = sess.brief_ms
                    sess.start_tool_log += sess.tools.take_log()
            for i, t in enumerate(c["turns"], start=1):
                row = sess.turn(t)
                rows.append({"run_id": run_id, "config": config, "scenario_id": sid, "call": c["call"], "turn": i, **row})
            sess.end()
    except Exception as e:
        rows.append({"run_id": run_id, "config": config, "scenario_id": sid, "call": "call_1", "turn": 999, "customer_text": "",
                     "agent_text": "", "questions": [], "claims": [], "tool_calls": [], "latency": {"ttft_ms": 0, "total_ms": 0, "ttfa_ms": None},
                     "error": f"{type(e).__name__}: {e}", "traceback": traceback.format_exc()[-1500:]})
    return sid, rows


def main():
    from core.config import settings
    from harness.loader import load_scenarios
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--config", choices=["full", "baseline_no_memory"], required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--router", default=settings.router_backend, choices=["jev", "llm", "rules"])
    ap.add_argument("--generator", default=settings.generator_backend, choices=["deepseek", "offline"])
    ap.add_argument("--workers", type=int, default=1, help="số tiến trình chạy song song (mỗi kịch bản độc lập)")
    ap.add_argument("--only", nargs="*", help="chỉ chạy các scenario_id này")
    a = ap.parse_args()

    scens = load_scenarios(a.scenarios)
    if a.only:
        scens = [s for s in scens if s["scenario_id"] in a.only]
    run_id = a.run_id or time.strftime("run-%Y%m%d-%H%M%S")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    from harness.memory import engine
    engine()                      # tạo bảng một lần trước khi chia tiến trình (tránh tranh chấp create_all)
    jobs = [(s, a.config, run_id, a.router, a.generator) for s in scens]
    t0 = time.time()
    if a.workers > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            results = list(ex.map(run_scenario, jobs))
    else:
        results = [run_scenario(j) for j in jobs]
    n_rows = n_err = 0
    with open(a.out, "w", encoding="utf-8") as fh:
        for sid, rows in sorted(results, key=lambda x: x[0]):
            for r in rows:
                if r.get("error"):
                    n_err += 1; print(f"[ERROR] {sid}: {r['error']}", file=sys.stderr); continue
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n"); n_rows += 1
    try:
        commit = subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        commit = None
    meta = {"run_id": run_id, "config": a.config, "scenarios": a.scenarios, "n_scenarios": len(scens), "n_rows": n_rows,
            "errors": n_err, "router": a.router, "generator": a.generator, "settings": settings.describe(), "commit": commit,
            "seconds": round(time.time() - t0, 1)}
    json.dump(meta, open(os.path.splitext(a.out)[0] + ".config.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"{len(scens)} kịch bản, {n_rows} lượt, {n_err} lỗi → {a.out}  ({meta['seconds']}s, router={a.router}, generator={a.generator})")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
