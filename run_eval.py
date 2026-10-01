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


def _short(v, n=160):
    s = json.dumps(v, ensure_ascii=False, default=str) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + "…"


def _log_turn(log, row):
    """Khối log một lượt, dựng từ chính dòng trace (INFO: tóm tắt; DEBUG: đầy đủ tham số/kết quả tool)."""
    r = row.get("router") or {}
    log.info("khách: %s", row["customer_text"])
    log.info("  router  %s intent=%s conf=%s %sms%s", r.get("backend"), r.get("intent"),
             None if r.get("confidence") is None else round(r["confidence"], 2), r.get("ms"),
             f" FALLBACK={r['fallback']}" if r.get("fallback") else "")
    if r.get("flags"):
        on = {k: round(v, 2) for k, v in r["flags"].items() if v >= 0.5}
        if on:
            log.info("  flags   %s", on)
    log.info("  goals   %s", row.get("goals"))
    for tc in row.get("tool_calls", []):
        res = tc.get("result") or {}
        err = res.get("error") if isinstance(res, dict) else None
        log.info("  tool    %s(%s)%s", tc["name"], _short(tc["args"], 120), f" → LỖI {err}" if err else "")
        log.debug("          → %s", _short(res, 600))
    g = row.get("guardrail") or {}
    if g.get("problems"):
        log.warning("guardrail %s → %s", g["problems"], g.get("action"))
    u, lat = row.get("llm_usage") or {}, row.get("latency") or {}
    log.info("  llm     tokens=%s ttft=%sms total=%sms", u, lat.get("ttft_ms"), lat.get("total_ms"))
    log.info("  agent:  %s", row["agent_text"])
    if row.get("questions"):
        log.info("  hỏi     %s", [q.get("slot", q) if isinstance(q, dict) else q for q in row["questions"]])
    for w in row.get("memory_writes", []):
        log.info("  memory  %s %s=%s (%s)", w.get("op"), w.get("key"), _short(w.get("value"), 80), w.get("source"))


def run_scenario(args):
    scen, config, run_id, router_backend, gen_backend, log_level, verbose = args
    from core import log as cclog
    level = cclog.setup(log_level, verbose)
    with cclog.capture(level) as lines:
        sid, rows = _run_scenario(scen, config, run_id, router_backend, gen_backend)
    cclog.set_context()
    return sid, rows, lines


def _run_scenario(scen, config, run_id, router_backend, gen_backend):
    from core import log as cclog
    from core.llm.generator import Generator
    from core.llm.router import Router
    from harness.agent import CallSession
    from harness.loader import agent_view
    from harness.memory import Memory
    from harness.textnorm import mask_pii
    from harness.tools import ToolBox

    log = cclog.get("run")
    view = agent_view(scen)
    sid = view["scenario_id"]
    cur = {"call": "call_1", "turn": 0, "text": ""}      # vị trí đang chạy → báo đúng chỗ khi lỗi
    cclog.set_context(sid)
    log.info("=== %s (%s, router=%s, generator=%s)", sid, config, router_backend, gen_backend)
    mem = Memory(f"{run_id}:{config}:{sid}", read_enabled=(config == "full"))
    mem.wipe()
    ToolBox.reset_world()
    router, gen = Router(router_backend), Generator(gen_backend)
    rows = []
    try:
        for c in view["calls"]:
            cur.update(call=c["call"], turn=0, text="")
            cclog.set_context(f"{sid} {c['call']}")
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
            b = sess.brief or {}
            log.info("--- %s %s kênh=%s khách=%s quay_lại=%s must_not_ask=%s stale=%s brief=%sms", c["call"], c["date"],
                     c["channel"], (sess.customer or {}).get("customer_id"), b.get("is_returning"), b.get("must_not_ask"),
                     b.get("stale_warnings"), sess.brief_ms)
            for i, t in enumerate(c["turns"], start=1):
                cur.update(turn=i, text=mask_pii(t if isinstance(t, str) else json.dumps(t, ensure_ascii=False)))  # log lỗi cũng phải che PII
                cclog.set_context(f"{sid} {c['call']} t{i}")
                row = sess.turn(t)
                _log_turn(log, row)
                rows.append({"run_id": run_id, "config": config, "scenario_id": sid, "call": c["call"], "turn": i, **row})
            sess.end()
    except Exception as e:
        tb = traceback.format_exc()
        where = f"{cur['call']} lượt {cur['turn']}" if cur["turn"] else f"{cur['call']} (lúc mở cuộc gọi)"
        log.error("LỖI ở %s — khách nói: %r\n%s", where, cur["text"], tb.rstrip())
        rows.append({"run_id": run_id, "config": config, "scenario_id": sid, "call": cur["call"], "turn": cur["turn"],
                     "customer_text": cur["text"], "error": f"{type(e).__name__}: {e}", "traceback": tb})
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
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="in khối từng lượt ra màn hình và ghi log mức DEBUG (đủ tham số/kết quả tool, HTTP status) vào <out>.log")
    ap.add_argument("--log-level", default=os.environ.get("LOG_LEVEL", "INFO"), choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                    help="mức log ghi vào <out>.log (mặc định LOG_LEVEL hoặc INFO)")
    a = ap.parse_args()

    scens = load_scenarios(a.scenarios)
    if a.only:
        scens = [s for s in scens if s["scenario_id"] in a.only]
    run_id = a.run_id or time.strftime("run-%Y%m%d-%H%M%S")
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    from harness.memory import engine
    engine()                      # tạo bảng một lần trước khi chia tiến trình (tránh tranh chấp create_all)
    from core import log as cclog
    cclog.setup(a.log_level, a.verbose)
    jobs = [(s, a.config, run_id, a.router, a.generator, a.log_level, a.verbose) for s in scens]
    t0 = time.time()
    if a.workers > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            results = list(ex.map(run_scenario, jobs))
    else:
        results = [run_scenario(j) for j in jobs]
    base = os.path.splitext(a.out)[0]
    n_rows = n_err = 0; errors = []
    results = sorted(results, key=lambda x: x[0])
    with open(a.out, "w", encoding="utf-8") as fh:
        for sid, rows, _ in results:
            for r in rows:
                if r.get("error"):
                    n_err += 1; errors.append(r); continue
                fh.write(json.dumps(r, ensure_ascii=False, default=str) + "\n"); n_rows += 1
    with open(base + ".log", "w", encoding="utf-8") as fh:
        fh.write(f"# run_id={run_id} config={a.config} router={a.router} generator={a.generator} "
                 f"log_level={'DEBUG' if a.verbose else a.log_level}\n")
        for _, _, lines in results:
            fh.writelines(l + "\n" for l in lines)
    err_path = base + ".errors.jsonl"
    if errors:
        with open(err_path, "w", encoding="utf-8") as fh:
            for r in errors:
                fh.write(json.dumps({k: r.get(k) for k in ("scenario_id", "call", "turn", "customer_text", "error", "traceback")},
                                    ensure_ascii=False) + "\n")
        for r in errors:
            print(f"[ERROR] {r['scenario_id']} {r['call']} lượt {r['turn']}: {r['error']}", file=sys.stderr)
        print(f"  traceback đầy đủ: {err_path}  |  log từng lượt: {base}.log", file=sys.stderr)
    elif os.path.exists(err_path):
        os.remove(err_path)                     # không để file lỗi của lần chạy trước gây nhầm
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
