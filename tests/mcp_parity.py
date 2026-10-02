#!/usr/bin/env python3
"""Kiểm tra: chạy qua MCP (mcp-commerce + mcp-memory) cho CÙNG trace với gọi hàm trực tiếp — chỉ được khác độ trễ.

    python tests/mcp_parity.py                                   # 7 SAMPLE, cả full + baseline, router=rules, generator=offline
    python tests/mcp_parity.py --scenarios datagen/out/dev --workers 4

In ra số lượt so sánh, số lượt lệch (kèm trường lệch đầu tiên) và độ trễ thêm của MCP. Exit 1 nếu có lệch.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOLATILE = {"latency", "call_brief_latency_ms", "run_id"}            # đo thời gian / tên lần chạy
VOLATILE_NESTED = {("router", "ms"), ("call_brief", "generated_at"), ("call_brief", "latency_ms")}


def strip(row):
    """Bỏ trường đo thời gian. Tool lỗi ở CẢ hai đường: chỉ so `error`, không so câu chữ `detail`
    (MCP kiểm inputSchema trước khi chạy nên báo "… is a required property" thay vì TypeError của Python)."""
    r = {k: v for k, v in row.items() if k not in VOLATILE}
    r["tool_calls"] = [{**tc, "result": {k: v for k, v in tc["result"].items() if k != "detail"}}
                       if isinstance(tc.get("result"), dict) and tc["result"].get("error") == "tool_exception" else tc
                       for tc in r.get("tool_calls", [])]
    for tc in r["tool_calls"]:                                         # handoff brief ghi giờ đồng hồ thật
        if isinstance((tc.get("args") or {}).get("brief"), dict):
            tc["args"] = {**tc["args"], "brief": {k: v for k, v in tc["args"]["brief"].items() if k != "generated_at"}}
    for a, b in VOLATILE_NESTED:
        if isinstance(r.get(a), dict):
            r[a] = {k: v for k, v in r[a].items() if k != b}
    return r


def first_diff(a, b, path=""):
    if type(a) is not type(b):
        return f"{path}: {a!r} ≠ {b!r}"
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            d = first_diff(a.get(k), b.get(k), f"{path}.{k}")
            if d:
                return d
    elif isinstance(a, list):
        if len(a) != len(b):
            return f"{path}: len {len(a)} ≠ {len(b)}"
        for i, (x, y) in enumerate(zip(a, b)):
            d = first_diff(x, y, f"{path}[{i}]")
            if d:
                return d
    elif a != b:
        return f"{path}: {a!r} ≠ {b!r}"
    return None


def run(out_dir, transport, config, a):
    out = os.path.join(out_dir, f"{transport}-{config}.jsonl")
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{out_dir}/{transport}.db"}
    cmd = [sys.executable, os.path.join(ROOT, "run_eval.py"), "--scenarios", a.scenarios, "--config", config, "--out", out,
           "--router", a.router, "--generator", a.generator, "--transport", transport, "--run-id", "parity",
           "--workers", str(a.workers)]
    subprocess.run(cmd, check=True, env=env, cwd=ROOT, stderr=subprocess.DEVNULL)
    return [json.loads(l) for l in open(out, encoding="utf-8")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default=os.path.join(ROOT, "test_set", "public_sample"))
    ap.add_argument("--router", default="rules")
    ap.add_argument("--generator", default="offline")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--out-dir", default=None)
    a = ap.parse_args()
    out_dir = a.out_dir or tempfile.mkdtemp(prefix="mcp_parity_")
    os.makedirs(out_dir, exist_ok=True)
    bad = n = 0; extra = []; n_exc = [0]
    for config in ("full", "baseline_no_memory"):
        d, m = run(out_dir, "direct", config, a), run(out_dir, "mcp", config, a)
        if len(d) != len(m):
            print(f"[{config}] số lượt khác nhau: direct {len(d)} ≠ mcp {len(m)}"); bad += 1; continue
        for x, y in zip(d, m):
            n += 1
            diff = first_diff(strip(x), strip(y))
            if diff:
                bad += 1
                if bad <= 10:
                    print(f"[{config}] {x['scenario_id']} {x['call']} t{x['turn']}: {diff[:300]}")
            extra.append(y["latency"]["total_ms"] - x["latency"]["total_ms"])
            n_exc[0] += sum(1 for tc in y.get("tool_calls", []) if (tc.get("result") or {}).get("error") == "tool_exception")
    if n_exc[0]:
        print(f"lưu ý: {n_exc[0]} lời gọi tool lỗi (tool_exception) ở cả hai đường — lỗi của harness, xem <out>.log")
    print(f"so {n} lượt: {bad} lượt lệch. Độ trễ thêm của MCP mỗi lượt: "
          f"trung vị {statistics.median(extra):.0f}ms, p95 {sorted(extra)[int(0.95 * (len(extra) - 1))]:.0f}ms  ({out_dir})")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
