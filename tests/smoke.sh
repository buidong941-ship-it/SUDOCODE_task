#!/usr/bin/env bash
# Kiểm thử nhanh không cần mạng/khóa API:
#  1) offline: router=rules, generator=offline trên 7 kịch bản mẫu, cả 2 cấu hình, chấm bằng reference_eval.py
#  2) tích hợp: Jev SDK + DeepSeek client gọi server giả lập (kiểm định dạng request/response thật)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=${OUT:-/tmp/smoke}; mkdir -p "$OUT"
export DATABASE_URL="sqlite:///$OUT/memory.db"
for c in full baseline_no_memory; do
  python run_eval.py --scenarios test_set/public_sample --config $c --out "$OUT/$c.jsonl" --router rules --generator offline --run-id smoke
done
(cd "$OUT" && python "$OLDPWD/eval/reference_eval.py" --scenarios "$OLDPWD/test_set/public_sample" --trace full.jsonl --baseline baseline_no_memory.jsonl | sed -n '/Chỉ số/,/Vi phạm/p')
python tests/fake_api_server.py 8765 & PID=$!; trap "kill $PID" EXIT; sleep 1
TYPESAFE_API_KEY=test-key-123 TYPESAFE_BASE_URL=http://127.0.0.1:8765 DEEPSEEK_API_KEY=test-key-123 DEEPSEEK_BASE_URL=http://127.0.0.1:8765 \
  python run_eval.py --scenarios test_set/public_sample --config full --out "$OUT/live.jsonl" --router jev --generator deepseek --run-id smoke-live
python - "$OUT/live.jsonl" <<'PY'
import json, sys
rows = [json.loads(l) for l in open(sys.argv[1])]
fb = [r["router"]["fallback"] for r in rows if r["router"]["fallback"]]
assert rows and not fb, f"router fallback: {fb[:3]}"
assert all(r["router"]["backend"] == "jev" for r in rows)
print(f"tích hợp OK: {len(rows)} lượt, Jev + DeepSeek (giả lập) không lỗi")
PY
