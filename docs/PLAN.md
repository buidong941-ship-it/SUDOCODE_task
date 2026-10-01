# Kế hoạch còn lại — Vòng 1

Lập ngày 01/10/2026, sau khi đọc lại `debaiSUDO.md` và `DIEU-CHINH-DE.md`, đối chiếu với code trên nhánh `claude/sleepy-albattani-aqjrof`.
Hạn nộp: BTC chưa công bố. Lịch dưới đây tính 4 tuần; khi có hạn thì co giãn, **giữ nguyên thứ tự ưu tiên**.

## 1. Hiện trạng so với đề

✅ đã có · 🟡 có một phần · ❌ chưa có. Cột "Tiêu chí" là hệ số chấm ở mục G.

| Hạng mục (mục đề) | Yêu cầu M1 | Hiện trạng | Tiêu chí |
|---|---|---|---|
| Kịch bản đa phiên (C.1, C.4) | ≥ 20 kịch bản + ≥ 5 ca khó; ≥ 30 khách đa phiên; ≥ 10 khách đa kênh | ✅ 67 kịch bản (45 dev / 22 test), 9 template, `validate.py` | 1, 4 |
| Transcript hội thoại (C.1) | ≥ 120 cuộc dạng transcript | 🟡 127 cuộc nhưng **chỉ có lượt khách** (câu mẫu điền giá trị); chưa có transcript đủ 2 phía | 1 |
| Audio (C.1) | ≥ 40 cuộc / ≥ 1 giờ | ❌ | 1 |
| ASR + ITN + WER/CER (C.1, A.5, ĐC-8) | ASR local, WER/CER/Entity Acc trên audio BTC + ≥ 20 file nhóm | ❌ (mới có ITN số trong `harness/textnorm.py`) | 1, 4 |
| Teencode, trích xuất có cấu trúc | intent, SP, size/màu, giá đã báo, hẹn gọi lại, người quyết định, kết quả | ✅ luật (`textnorm.py`, `extractor.py`) — chưa đối chiếu tay | 1 |
| PII (C.1) | Che SĐT/CCCD/địa chỉ khi lưu log **và khi gửi model ngoài** | 🟡 CCCD/STK đã che; **SĐT, địa chỉ vẫn gửi DeepSeek nguyên văn** | 1, guardrail |
| Bộ nhớ 4 tầng (C.1) | working/episodic/profile/KB; ghi gì–không ghi gì; khách đổi ý | ✅ 3 tầng SQL + supersede + TTL + nguồn gốc. 🟡 KB: tìm từ khóa, chưa RAG vector | 2 |
| Session Continuity (C.2) | nhận diện, Call Brief, mở đầu tiếp nối, không hỏi lại | ✅ (`_build_brief`, kiểm tra KM/giá/tồn kho lúc nhận diện) | 2 |
| Tool (C.2, ĐC-3) | ≥ 3 tool, giá từ tool | ✅ đủ 9 tool BTC qua `mock_tools` | 2 |
| Guardrail, fallback, chuyển máy | | ✅ guardrail số tiền/PII/nội bộ, router fallback, `handoff.transfer` | 2 |
| **MCP hoặc A2A (C.3)** | ≥ 2 MCP server, bắt buộc `mcp-memory` | ❌ **chưa có gì** | **3 (15%)** |
| Script đánh giá + baseline (C.4) | 1 lệnh, 5 chỉ số, baseline không bộ nhớ | ✅ `run_eval.py` + `reference_eval.py`, 2 cấu hình | 4 |
| **Số liệu thật** | | ❌ mới chạy offline/giả lập — chưa gọi Jev/DeepSeek thật | 4 |
| Độ trễ (ĐC-1) | Brief ≤ 5 s, TTFT p95 ≤ 3 s, total p95 ≤ 8 s | 🟡 đã đo trong trace, chưa có số thật | 2 |
| **Cơ chế cải tiến (C.5)** | ≥ 1 cơ chế, 2 vòng trên cùng bộ test, người duyệt, quay lui | ❌ | **5 (13%)** |
| **Giao diện + demo (C.6)** | web: khung chat, Call Brief, dòng thời gian bộ nhớ; demo 2 cuộc | ❌ | **6 (13%)** |
| Báo cáo, video, slide (F) | phân tích ≥ 10 ca sai, video 5–8 phút, ≤ 15 slide | ❌ (đã có `ARCHITECTURE.md`, `HARNESS.md`) | 4, 8 |
| Log/debug | | ✅ `<out>.log`, `<out>.errors.jsonl`, `-v` | — |

**Ba lỗ hổng lớn nhất theo điểm:** MCP (15%), cơ chế cải tiến (13%), giao diện/demo (13%). Tiếp theo là ASR + audio (một phần của 12%) và **số liệu thật** — thiếu số thật thì tiêu chí 4 gần như bằng 0.

## 2. Thứ tự ưu tiên

1. **Số thật trước** (vòng 0). Mọi thứ sau đều cần một mốc để so.
2. **MCP** — 15% điểm, và là thay đổi kiến trúc nên làm sớm trước khi viết UI/cải tiến dựa lên nó.
3. **Cơ chế cải tiến** — cần vòng 0 đã có; cho ra bảng "trước/sau".
4. **ASR + audio** — làm song song được, ít phụ thuộc phần còn lại.
5. **UI + demo + báo cáo**.
6. M2 / điểm thưởng chỉ khi 1–5 xong.

## 3. Lịch 4 tuần

### Tuần 0 (2–3 ngày, bắt đầu ngay): số thật vòng 0

- [ ] Điền `TYPESAFE_API_KEY`, `DEEPSEEK_API_KEY` vào `.env`. Không có Jev → `--router llm`.
- [ ] Chạy `full` + `baseline_no_memory` trên `test_set/public_sample`, `datagen/out/dev`, `datagen/out/test`. Lưu vào `runs/r0/` kèm `.config.json`, `.log`.
- [ ] Kiểm ngưỡng đề: RQR giảm ≥ 40% so với baseline, TSR ≥ 70%, HR giá ≤ 5%, TTFT p95 ≤ 3 s, total p95 ≤ 8 s, Call Brief ≤ 5 s.
- [ ] Đối chiếu tay ~20 lượt `questions`/`claims` (bộ trích dùng luật — nếu trích sai thì RQR/HR sai). Ghi tỷ lệ khớp vào báo cáo.
- [ ] Gửi BTC 3 câu hỏi: SAMPLE-03 `OD682761` vs mock `OD600001`; SAMPLE-02 `promo_active=false`; xin bản sửa `asr/ground_truth.json` (entities ghi đè D01/D02) + cách chấm entity trong `reference_eval.py`.
- **Xong khi:** có bảng A.6 vòng 0 với số thật, tái lập bằng 1 lệnh.

### Tuần 1: MCP + PII + khởi động ASR

- [ ] **`mcp-memory`** (FastMCP): bọc `harness/memory.py` — `get_brief`, `get_facts`, `write_fact`, `add_session`, `forget_customer`, `merge_customer`. Phân quyền: chỉ Context & Memory được ghi.
- [ ] **`mcp-commerce`** (hoặc tách `mcp-catalog` + `mcp-crm`): bọc `eval/mock_tools.py`, giữ đúng tên/tham số `schemas/tools.schema.json`.
- [ ] `harness/tools.py` và `Memory` gọi qua MCP client (giữ chế độ gọi trực tiếp làm cờ `--transport direct|mcp` để so tốc độ).
- [ ] Kiểm tương đương: chạy lại vòng 0 qua MCP → trace phải cho **cùng chỉ số** (chỉ khác latency). Ghi thêm độ trễ MCP vào báo cáo.
- [ ] Viết vào `ARCHITECTURE.md`: vì sao chọn MCP thay vì A2A, và một tình huống cụ thể MCP giúp ích (vd. UI copilot và agent dùng chung `mcp-memory`, người và AI thấy cùng một bộ nhớ → giải Case 3).
- [ ] **PII:** thay SĐT/địa chỉ bằng token (`<PHONE_1>`, `<ADDR_1>`) trước khi gửi DeepSeek/Jev; ghép lại sau khi sinh. Thêm `mask_pii` cho SĐT trong `<out>.log`.
- [ ] **ASR:** `asr/transcribe.py` dùng faster-whisper (hoặc PhoWhisper) + ITN số tiền/SĐT/ngày → `asr/hypotheses.json`; chạy `reference_eval.py --asr` trên 4 hội thoại BTC.
- **Xong khi:** `run_eval.py --transport mcp` cho cùng số với vòng 0; WER/CER đầu tiên trên audio BTC.

### Tuần 2: Dữ liệu đủ chỉ tiêu + RAG

- [ ] Dùng DeepSeek viết lại `customer_turns` cho tự nhiên (giữ slot), chạy lại `validate.py` — kịch bản nào lệch đáp án thì loại.
- [ ] Xuất **transcript 2 phía** từ trace của harness chạy với model thật → `data/transcripts/*.json` (≥ 120 cuộc).
- [ ] **Audio:** edge-tts (giọng nam/nữ) từ ≥ 40 cuộc, ≥ 1 giờ; thêm nhiễu + lọc băng thông điện thoại cho một phần. Ghi hạn chế: edge-tts không có giọng theo vùng miền rõ rệt.
- [ ] WER/CER/Entity Accuracy (số tiền, SĐT) trên ≥ 20 file của nhóm + 4 file BTC, báo riêng sạch/nhiễu.
- [ ] **RAG vector** cho `policy/`: chunk theo mã mục `[XX-nn]`, embedding bge-m3, pgvector (hoặc Chroma); lọc bản hết hiệu lực theo `changelog.md` và ngày đơn; chặn tài liệu `NOI-BO`. Chạy `reference_eval.py --rag` → Recall@3/@5, abstain rate.
- [ ] Viết `docs/DATASET.md`: cách sinh, phân bố (persona, ngành, kênh, miền), hạn chế, xử lý PII.
- **Xong khi:** đủ mọi con số bảng C.1 cột M1; Recall@k có số.

### Tuần 3: Cơ chế cải tiến + vòng 1

- [ ] **Knowledge Gap Loop** (bắt buộc chọn): lượt agent trả lời "chưa có thông tin" / abstain / guardrail chặn → ghi `improve/gaps.jsonl` (câu hỏi, ngữ cảnh, kịch bản). Script gom nhóm → đề xuất bổ sung FAQ/playbook + tự sinh kịch bản test mới từ câu hỏi đó.
- [ ] **Exemplar Bank**: lượt thuộc kịch bản đạt TSR và không vi phạm → lưu làm few-shot theo (intent, persona); generator lấy 1–2 ví dụ gần nhất.
- [ ] **Người duyệt:** mọi thay đổi (FAQ mới, exemplar mới) vào `improve/pending/`; lệnh `python improve.py review` để duyệt/loại. Chỉ bản đã duyệt mới được nạp.
- [ ] **Quay lui:** sau khi áp thay đổi, chạy lại dev; chỉ số nào tụt quá ngưỡng (vd. HR tăng, TSR giảm > 3 điểm) → tự hoàn tác về phiên bản trước. Không bao giờ học từ lượt có claim sai, kể cả khi kịch bản chốt được đơn (chống "hứa đại để chốt").
- [ ] Chạy **vòng 1** trên cùng `datagen/out/test` (giữ nguyên) → bảng vòng 0 vs vòng 1.
- [ ] **Phân tích ≥ 10 ca sai** từ trace/log (`<out>.log` giúp tìm nhanh): ca, nguyên nhân gốc (router, planner, generator, bộ trích, dữ liệu BTC), cách sửa hoặc lý do không sửa.
- **Xong khi:** có bảng trước/sau trên cùng bộ test và danh sách thay đổi đã được người duyệt.

### Tuần 4: Giao diện, demo, nộp bài

- [ ] **Streamlit**: chọn khách/kênh → khung chat; Call Brief hiện khi khách gọi lại; dòng thời gian bộ nhớ (phiên, fact, fact bị thay thế, nguồn); nút chạy `reference_eval` và hiện bảng full vs baseline.
- [ ] Kịch bản demo C.6: cuộc 1 tư vấn + báo giá + KM + "hỏi người nhà" → cuộc 2 vài ngày sau: nhận diện, mở đầu tiếp nối, không hỏi lại, chốt đơn. (Có thời gian thì cuộc 3 đổi size.)
- [ ] Ước tính chi phí/cuộc gọi từ `llm_usage` trong trace (token × giá) + ước lượng tác động kinh doanh (Calls-to-Close).
- [ ] README: cài đặt, lệnh 1 dòng cho từng phần, khởi tạo dữ liệu.
- [ ] Báo cáo đánh giá, video 5–8 phút, ≤ 15 slide (nói rõ hạn chế và các lỗi dữ liệu BTC đã phát hiện).

## 4. M2 / điểm thưởng (chỉ khi M1 xong)

Theo thứ tự lợi ích/công sức: Calls-to-Close + p50/p95 + chi phí (đã có dữ liệu trong trace) → customer simulator 3 seed theo `simulator/` → LLM-judge với `eval/llm_judge_rubric.json` + chấm tay ≥ 20 mẫu (Cohen's kappa) → ablation từng cơ chế cải tiến → copilot gợi ý câu cho nhân viên → chạy LLM local (Qwen qua Ollama).

## 5. Rủi ro

| Rủi ro | Ứng phó |
|---|---|
| Không gọi được Jev/DeepSeek (mạng, khóa) | `--router llm`; nếu DeepSeek cũng không được thì đổi `DEEPSEEK_BASE_URL` sang API tương thích OpenAI khác — chỉ đổi `.env` |
| BTC không sửa SAMPLE-02/03, ground_truth | Báo cáo số theo bản BTC **và** bản đã sửa, ghi rõ chênh lệch do đâu |
| Bộ trích `questions`/`claims` bằng luật sai | Đối chiếu tay tuần 0; nếu < 90% khớp thì dùng LLM trích có kiểm tra |
| MCP làm chậm mỗi lượt | Đo; server chạy cùng máy (stdio); giữ `--transport direct` làm phương án dự phòng |
| Hết thời gian | Bỏ M2 trước, rồi rút gọn UI; **không bỏ** baseline, vòng 0/1 và MCP |
