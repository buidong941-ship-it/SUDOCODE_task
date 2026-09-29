# Gói dữ liệu BTC — AI Challenge Vòng 1 (Harness Agent Call Center)

Ngày quy ước "hôm nay" của toàn bộ dữ liệu: **2026-10-15** (`reference_date`). Mọi kiểm tra "khuyến mãi còn hiệu lực" tính theo ngày này, hoặc theo `call_date` / `days_later` trong kịch bản.

## Phát cho các team (PUBLIC)

| Đường dẫn | Nội dung | Dùng cho |
|---|---|---|
| `catalog/products.json`, `products.csv` | 40 sản phẩm (3 ngành) + 96 biến thể size/màu (có phụ thu size lớn), 2 SKU ngừng bán có successor, 2 combo | tool `catalog.search`, `inventory.check` |
| `catalog/inventory_timeline.json` | Tồn kho thay đổi theo ngày (hết hàng giữa 2 cuộc gọi, ngày về hàng) | `inventory.check(on=...)` |
| `catalog/promotions.json` | 14 chương trình KM: có điều kiện (min_qty, loại size, 1 lần/khách, theo vùng, thu cũ đổi mới), 3 **đã hết hạn**, 1 chưa bắt đầu | `pricing.get_quote`, HR, KM-04 chọn KM có lợi nhất |
| `catalog/crm_seed.json` | 50 khách seed (SĐT, Zalo ID, FB ID); có khách lịch sử 8 tháng, đơn đang giao, **2 người chung SĐT** | `crm.get_customer`, identity resolution, TTL |
| `policy/*.md` | 14 tài liệu, 99 chunk `[XX-nn]`: chính sách hiện hành + **bản cũ hết hiệu lực** + changelog + **tài liệu nội bộ không được lộ** + lịch nghỉ + spec bảng + playbook + tài liệu nhiễu | RAG, guardrail, version conflict |
| `rag/qa_labeled.json` | 60 câu, 6 loại (single/multi_hop/version_conflict/unanswerable/restricted/numeric) | Recall@k, abstain, version accuracy (M2) |
| `schemas/` | Schema tool mock, HandoffBrief, CallBrief, trace log, `scenario_format.md` | thống nhất để chấm chéo |
| `eval/mock_tools.py` | **Mock tool tham chiếu** (giá sau KM theo điều kiện, tồn kho theo ngày, COD limit, dời lịch ngày nghỉ, SĐT chung, mask PII) | nhóm bọc thành MCP hoặc đối chiếu |
| `simulator/` | Spec customer simulator + 12 persona prompt chuẩn | M2, so sánh chéo |
| `eval/llm_judge_rubric.json` | 12 tiêu chí PASS/FAIL + prompt judge | M2, tiêu chí 6 |
| `test_set/public_sample/` | 7 kịch bản mẫu (5 thường + 2 ca khó: ASR lỗi/teencode, chính sách cũ) | để team làm script chấm chạy được trên định dạng của BTC |
| `asr/ground_truth.json` | 12 hội thoại đa lượt (86 lượt, 2 người nói, ~12 phút), 4 có nhiễu; entity theo lượt | WER/CER/Entity Accuracy + diarization (M2); audio BTC sinh bằng `make_audio.py` (Gemini TTS / ElevenLabs / F5-TTS-Vietnamese) |
| `eval/reference_eval.py` | Script chấm tham chiếu: 5 chỉ số, TSR ca khó, guardrail violations, memory checks, latency, WER/CER/diarization, RAG (`--rag`) | con số của team phải tái lập được bằng script này |
| `eval/validate_scenarios.py` | Kiểm tra kịch bản ↔ catalog nhất quán qua mock_tools | BTC chạy sau mỗi lần sửa |
| `eval/make_example_trace.py`, `eval/runs/` | Trace ví dụ + báo cáo mẫu | xem định dạng trace |
| `eval/huong-dan-do-latency.md` | Quy tắc đo TTFT / Total / TTFA / Call Brief | bảng hiệu năng (đã chỉnh sửa) |
| `DIEU-CHINH-DE.md` | Các điểm đề thi được điều chỉnh/bổ sung | mọi team |
| `GIAI-DAP-MENTOR.md` | Trả lời câu hỏi của mentor Team 5, 8, 10 | mọi team |

## Những gì BTC giữ lại (team không nhận)

Bộ test ẩn 41 kịch bản (cùng định dạng `test_set/public_sample/`), 8/12 hội thoại ground truth ASR (team nhận 4 mẫu D01–D04), và script sinh dữ liệu. Ngày chấm BTC phát bộ ẩn + audio đầy đủ, chạy hệ thống của team ở 2 cấu hình và chấm bằng `eval/reference_eval.py` đúng như file trong gói này.

## Quy trình chấm chéo

1. Team nộp repo; README của team phải có lệnh dạng `python run_eval.py --scenarios <dir> --config full|baseline_no_memory --out trace.jsonl`.
2. BTC thay `<dir>` bằng bộ ẩn, chạy 2 cấu hình, rồi `python eval/reference_eval.py --scenarios <dir> --trace full.jsonl --baseline baseline.jsonl --asr <asr_dir>`.
3. Bảng A.6 in ra từ script là con số chính thức để so giữa các team. Phần `questions[]`/`claims[]` trong trace do extractor của team sinh — BTC chấm tay ngẫu nhiên 20 lượt để kiểm tra extractor có "ăn gian" không (bỏ sót câu hỏi/claim).
4. Metric team tự bổ sung, simulator, Recall@k trên tài liệu riêng: chấm ở tiêu chí 4/6 theo chất lượng phân tích, không so số tuyệt đối.
