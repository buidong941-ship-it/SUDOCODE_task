#!/usr/bin/env python3
"""Kiểm tra che PII khi gửi model ngoài:

1. Chạy kịch bản qua DeepSeek + Jev giả lập (tests/fake_api_server.py), ghi lại MỌI request gửi đi → không được chứa
   SĐT hay địa chỉ của khách (chỉ có [SĐT_n] / [ĐỊA_CHỈ_n]).
2. Câu trả lời sau khi ghép lại phải giống hệt chạy offline (không che) → che + ghép không làm mất/sai thông tin.
3. File log không chứa SĐT/địa chỉ nguyên văn.

    python tests/pii_check.py [--scenarios datagen/out/dev]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from http.server import ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tests"))
import fake_api_server as fake                                   # noqa: E402
from harness.extractor import ADDRESS_RX                          # noqa: E402

BODIES = []


class Capture(fake.H):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(n)
        BODIES.append(raw.decode("utf-8", "replace"))
        self.rfile = __import__("io").BytesIO(raw)
        self.headers.replace_header("Content-Length", str(len(raw)))
        return super().do_POST()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default=os.path.join(ROOT, "datagen", "out", "dev"))
    a = ap.parse_args()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Capture)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    out = tempfile.mkdtemp(prefix="pii_check_")
    base_env = {**os.environ, "DATABASE_URL": f"sqlite:///{out}/m.db", "TYPESAFE_API_KEY": "test-key-123",
                "TYPESAFE_BASE_URL": url, "DEEPSEEK_API_KEY": "test-key-123", "DEEPSEEK_BASE_URL": url}
    for name, gen, router in (("offline", "offline", "rules"), ("live", "deepseek", "jev")):
        subprocess.run([sys.executable, os.path.join(ROOT, "run_eval.py"), "--scenarios", a.scenarios, "--config", "full",
                        "--out", f"{out}/{name}.jsonl", "--generator", gen, "--router", router, "--run-id", name],
                       check=True, env=base_env, cwd=ROOT, stderr=subprocess.DEVNULL)
    off = [json.loads(l) for l in open(f"{out}/offline.jsonl", encoding="utf-8")]
    live = [json.loads(l) for l in open(f"{out}/live.jsonl", encoding="utf-8")]

    # PII thật của các kịch bản: SĐT khách + địa chỉ khách nói ra
    phones, addrs = set(), set()
    for r in off:
        phones |= set(re.findall(r"\b0\d{9}\b", json.dumps(r["tool_calls"], ensure_ascii=False)))
        m = ADDRESS_RX.search(r["customer_text"])
        if m:
            addrs.add(m.group(1).strip())
    def readable(b):                      # request JSON có thể escape \uXXXX → đưa về chữ thường để tìm
        try:
            return json.dumps(json.loads(b), ensure_ascii=False)
        except ValueError:
            return b
    sent = "\n".join(readable(b) for b in BODIES)
    leaked_p = sorted(p for p in phones if p in sent)
    leaked_a = sorted(x for x in addrs if x in sent)
    tokens = len(re.findall(r"\[(?:SĐT|ĐỊA_CHỈ)_\d+\]", sent))
    print(f"{len(BODIES)} request gửi ra ngoài; {len(phones)} SĐT, {len(addrs)} địa chỉ trong kịch bản; mã che xuất hiện {tokens} lần")
    print(f"  SĐT lọt ra ngoài: {leaked_p or 'không'}")
    print(f"  địa chỉ lọt ra ngoài: {leaked_a or 'không'}")
    # router khác nhau (rules vs jev giả lập) có thể đổi intent → chỉ so các lượt cùng goals
    same = [(x, y) for x, y in zip(off, live) if x["goals"] == y["goals"]]
    diff = [(x, y) for x, y in same if x["agent_text"].strip() != y["agent_text"].strip()]   # client DeepSeek strip() câu
    print(f"  câu trả lời sau khi ghép lại khác bản không che: {len(diff)}/{len(same)} lượt cùng kế hoạch")
    for x, y in diff[:3]:
        print(f"    {x['scenario_id']} {x['call']} t{x['turn']}\n      offline: {x['agent_text'][:150]}\n      live:    {y['agent_text'][:150]}")
    log = open(f"{out}/live.log", encoding="utf-8").read()
    leaked_log = sorted({p for p in phones if p in log} | {x for x in addrs if x in log})
    print(f"  PII nguyên văn trong file log: {leaked_log[:5] or 'không'}")
    ok = not (leaked_p or leaked_a or diff or leaked_log) and tokens > 0
    print("OK" if ok else "CÓ LỖI", f"({out})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
