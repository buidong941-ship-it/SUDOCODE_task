# Harness — cách chạy và cấu trúc code

Kiến trúc tổng thể: `docs/ARCHITECTURE.md`. File này mô tả phần đã code: **Jev làm orchestrator/router, DeepSeek sinh lời thoại**, tool bọc `eval/mock_tools.py`, bộ nhớ SQLite/Postgres, xuất trace đúng `schemas/trace_log.schema.json`.

## Cài đặt

```bash
pip install -r requirements.txt
cp .env.example .env      # điền TYPESAFE_API_KEY, DEEPSEEK_API_KEY
```

## Lệnh BTC chạy

```bash
python run_eval.py --scenarios test_set/public_sample --config full --out runs/r0/full.jsonl
python run_eval.py --scenarios test_set/public_sample --config baseline_no_memory --out runs/r0/baseline.jsonl
python eval/reference_eval.py --scenarios test_set/public_sample --trace runs/r0/full.jsonl --baseline runs/r0/baseline.jsonl
```

Tùy chọn:

| Cờ | Ý nghĩa |
|---|---|
| `--router jev\|llm\|rules` | Orchestrator. `llm` = DeepSeek trả JSON. `rules` = luật từ khóa, **chỉ dùng kiểm thử**. |
| `--generator deepseek\|offline` | Sinh lời thoại. `offline` = câu mẫu, **chỉ dùng kiểm thử**. |
| `--workers N` | Chạy song song N tiến trình, mỗi kịch bản độc lập. |
| `--only SAMPLE-01 …` | Chạy một số kịch bản. |
| `--run-id` | Namespace bộ nhớ + tên lần chạy. |
| `--verbose` / `-v` | In khối từng lượt ra màn hình và ghi log mức DEBUG vào `<out>.log`. |
| `--log-level DEBUG\|INFO\|WARNING\|ERROR` | Mức log ghi vào `<out>.log` (mặc định `LOG_LEVEL` trong `.env`, hoặc `INFO`). |

Mỗi lần chạy ghi thêm `<out>.config.json`: model, tham số, commit, thời gian. Không ghi khóa API.

## Log và debug

Mỗi lần chạy, cạnh file trace `<out>.jsonl` có:

| File | Nội dung |
|---|---|
| `<out>.log` | Log từng lượt, gom theo kịch bản (không bị trộn khi `--workers > 1`). Mỗi dòng có nhãn `[SAMPLE-01 call_2 t3]`. |
| `<out>.errors.jsonl` | Chỉ có khi có lỗi: `scenario_id`, `call`, `turn`, câu khách vừa nói, thông điệp lỗi, **traceback đầy đủ**. Tự xóa khi lần chạy sau không lỗi. |
| `<out>.config.json` | Cấu hình lần chạy, số lỗi. |

Mức log:
- **Màn hình** mặc định chỉ hiện WARNING trở lên: router lỗi hoặc không chắc nên dùng luật (`router.fallback`), guardrail bắt lỗi rồi sinh lại, lỗi API (kèm HTTP status), traceback khi kịch bản lỗi. `-v` hiện thêm khối từng lượt.
- **INFO** (mặc định trong file): đầu mỗi cuộc gọi (khách nhận diện được, `must_not_ask`, `stale_warnings`, thời gian Call Brief); mỗi lượt: câu khách, router (intent, độ tin cậy, cờ, ms), goals, tool đã gọi (đánh dấu tool trả lỗi), token và độ trễ LLM, câu agent, slot agent hỏi, bộ nhớ ghi gì.
- **DEBUG** (`-v` hoặc `--log-level DEBUG`): thêm kết quả tool đầy đủ, prompt gửi DeepSeek, xác suất từng intent của Jev, và dòng HTTP của thư viện (`POST …/chat/completions "200 OK"`, `POST …/v1/systemone <- 200 in 210ms`, "Retrying request…").

Không log khóa API: chỉ log URL, status, thời gian, token (header bí mật bị SDK che).

Cách khoanh vùng lỗi:
```bash
python run_eval.py --scenarios test_set/public_sample --config full --out runs/dbg/full.jsonl --only SAMPLE-03 -v
grep -n "WARNING\|ERROR" runs/dbg/full.log          # router fallback, guardrail, lỗi API
grep -n "SAMPLE-03 call_2 t2" runs/dbg/full.log       # toàn bộ một lượt
```

## Kiểm thử không cần mạng

```bash
bash tests/smoke.sh
```

Script gồm hai phần:
1. Chạy `rules` + `offline` trên 7 kịch bản mẫu, chấm bằng `reference_eval.py`.
2. Dựng `tests/fake_api_server.py` giả lập API Jev (`POST /v1/systemone`) và DeepSeek (`POST /chat/completions`, có stream). Sau đó chạy đường thật `--router jev --generator deepseek` qua SDK chính thức để kiểm định dạng request/response.

Số liệu ở chế độ offline chỉ để bắt lỗi logic. **Số báo cáo phải chạy với Jev + DeepSeek thật.**

## Luồng một lượt (`harness/agent.py`)

```
lời khách ─► textnorm.perceive (teencode, ITN số tiền/SĐT/ngày, mask PII)
          ─► extractor.customer_slots (diện tích, ngân sách, size/màu, địa chỉ, thanh toán, rào cản, giờ hẹn)
          ─► Router (Jev): intent ∈ 11 nhãn + 7 cờ (đồng ý mua, trì hoãn, hỏi AI/người, xóa dữ liệu, y tế, giá nhập, đối thủ)
          ─► Planner (code xác định): gọi tool với tham số lấy từ kết quả tool → goals + facts
          ─► Generator (DeepSeek): nói theo goals, chỉ dùng số trong facts
          ─► guardrails.check (số tiền lạ, giá nhập/giá sàn nội bộ, PII, nhận là người, chê đối thủ) → sinh lại 1 lần → câu an toàn
          ─► extractor: questions[] / claims[] / facts_used → trace
          ─► memory: ghi fact (set/supersede, nguồn call_n#turn_k, TTL), báo giá, phiên
```

**Vì sao planner là code chứ không để LLM gọi tool:** tham số `order.create` (sku, giá sau KM, mã KM, giỏ hàng) lấy thẳng từ `pricing.get_quote` cùng ngày. Nhờ vậy giá trong đơn luôn khớp mock của BTC và HR về giá gần như bằng 0 do thiết kế. LLM chỉ lo câu chữ, Jev lo phân loại ý định (nhanh, có xác suất để đặt ngưỡng).

**Dự phòng:** Jev lỗi, hết thời gian chờ hoặc độ tin cậy dưới `ROUTER_MIN_CONFIDENCE` mà luật từ khóa có tín hiệu rõ thì chuyển sang luật. Lý do được ghi vào `trace.router.fallback`, để báo cáo tỷ lệ dự phòng.

## Các trường thêm trong trace (BTC bỏ qua, dùng cho phân tích lỗi)

`router` (intent, confidence, flags, backend, ms, fallback), `goals`, `guardrail`, `llm_usage`, `call_brief` (lượt 1).
Các trường này cũng được in trong `<out>.log` (xem "Log và debug").

## Cấu trúc thư mục

```
core/config.py            cấu hình từ .env
core/llm/router.py        Router: jev | llm | rules
core/llm/deepseek.py      client DeepSeek (OpenAI-compatible, streaming đo TTFT)
core/llm/generator.py     prompt hệ thống + câu mẫu offline
harness/loader.py         đọc kịch bản, CHỈ lộ phần agent được thấy
harness/textnorm.py       chuẩn hóa tiếng Việt, ITN, PII
harness/tools.py          bọc mock_tools + nhận diện sản phẩm/biến thể trong câu nói
harness/memory.py         bộ nhớ (SQLAlchemy; namespace theo run/config/kịch bản)
harness/knowledge.py      tra chính sách (tạm: từ khóa; bước sau thay bằng RAG vector)
harness/extractor.py      slot khách; questions/claims/facts_used của agent
harness/guardrails.py     kiểm câu trả lời
harness/agent.py          CallSession: nhận diện, Call Brief, planner, ghi nhớ
run_eval.py               chạy bộ kịch bản → trace JSONL
tests/                    smoke test + server giả lập API
```

## Giới hạn hiện tại

- **Chính sách:** tìm theo từ khóa, chưa có RAG vector và chưa xử lý "chính sách cũ cho đơn cũ".
- **Postgres:** đường dẫn `DATABASE_URL=postgresql+psycopg://…` đã có nhưng mới chạy thử trên SQLite.
- **Bộ trích `claims`/`questions`:** dùng luật. Cần đối chiếu tay khoảng 20 lượt sau khi có câu trả lời thật từ DeepSeek.
