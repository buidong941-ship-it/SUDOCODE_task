# Giải đáp câu hỏi mentor — Đề thi Vòng 1

Kèm gói dữ liệu này. Các điều chỉnh đề áp dụng chung xem `DIEU-CHINH-DE.md`.

## Team 5 — mentor anh Lộc Đỗ

**1. Thời gian thực hiện & có cần đợi dataset chung không?**
Lộ trình ~4 tuần theo mục E. Không cần đợi: BTC đã phát catalog, khuyến mãi, CRM seed và tài liệu chính sách dùng chung (`catalog/`, `policy/`); team sinh dataset hội thoại của mình ngay từ tuần 1 trên nền đó. Bộ test ẩn chỉ dùng lúc chấm, cùng định dạng với `test_set/public_sample/`, nên script đánh giá của team đọc được 5 kịch bản mẫu là chạy được trên bộ ẩn. *(Mốc ngày: BTC thông báo riêng.)*

**2. Case 2 — khách gọi xong chuyển sang inbox luôn?**
Có, thuộc phạm vi Case 2 (identity resolution SĐT / Zalo ID / FB ID). M1 đã yêu cầu ≥ 10 khách có cả gọi lẫn chat; `crm_seed.json` có sẵn khách mang cả ba định danh. Bộ test ẩn có kịch bản chat Fanpage → gọi hotline (xem `SAMPLE-04`).

**3. Chuyển tiếp máy giữa chừng — lấy dữ liệu hội thoại trước thế nào?**
Môi trường mô phỏng, không có tổng đài thật. Working memory ghi theo từng lượt (không đợi kết thúc cuộc gọi); lúc chuyển máy, agent gọi `handoff.transfer` với brief sinh từ trạng thái hiện tại (schema `schemas/handoff_brief.schema.json`). Lưu real-time giữa cuộc gọi và store là cách được khuyến khích; team chỉ cần trình bày ghi gì, lúc nào.

**4. Chuyển máy đúng có tính Task Success cho ca khó không?**
Có. Kịch bản khai báo `expected_outcome: "chuyen_may"` và `success_if.tool_called = "handoff.transfer"` + `brief_must_contain`; script tham chiếu (`eval/reference_eval.py`) chấm đúng như vậy. Agent không thể "chuyển máy mọi thứ" vì các kịch bản khác yêu cầu `order.create` / `schedule.callback`. Nên báo thêm tỷ lệ chuyển máy thừa.

**5. Handoff brief — cần routing/distribution không?**
Không. Chỉ chấm *khi nào chuyển* và *bàn giao kèm gì*. Tool mock trả `ticket_id`. Routing theo kỹ năng nếu làm thì tính sáng tạo ở tiêu chí 6.

**6. Latency Call Brief tính từ đâu, có được precompute không?**
Từ sự kiện nhận diện SĐT đến khi `CallBrief` (schema `schemas/call_brief.schema.json`) sẵn sàng/hiển thị, gồm DB + LLM. Precompute tóm tắt episodic ở cuối phiên trước là hợp lệ (khai báo `precomputed_parts`), nhưng bước kiểm tra tính mới (KM hết hạn, tồn kho, tương tác kênh khác sau phiên trước) phải chạy lúc nhận diện và tính vào latency. Chi tiết: `eval/huong-dan-do-latency.md`.

**7. Bao nhiêu request để tính p95, đo ở đâu?**
Toàn bộ lượt của bộ test, tối thiểu 100 lượt (bộ ẩn có ~170 lượt). Đo tại ranh giới backend/harness, bỏ 3 lượt warm-up, không tính render UI. Ghi vào trace (`latency.ttft_ms`, `total_ms`), script tự tổng hợp p50/p95. Baseline và hệ thống cùng phần cứng/API/model.

**8. Được thêm metric không?**
Được, khuyến khích, với điều kiện có công thức và script tính được. Không thay thế 5 chỉ số bắt buộc; được tính ở tiêu chí 4 (phân tích lỗi) và tiêu chí 6 (sáng tạo). `reference_eval.py` đã tính sẵn thêm Calls-to-Close và số lượt TB/cuộc để team tham khảo.

**9. Giao diện M1 — agent tự trả lời khách?**
Đúng. M1: agent nói chuyện trực tiếp với khách qua chat text; UI tối thiểu gồm khung hội thoại, Call Brief hiện khi khách gọi/nhắn lại, dòng thời gian bộ nhớ. File ghi âm → ASR → cùng harness. Copilot (gợi ý cho nhân viên) là M2.

**10. Model ở mục E chỉ là gợi ý? Giới hạn kích thước/tier?**
Chỉ gợi ý. Không giới hạn tham số hay tier API cho LLM. Ràng buộc: không fine-tune; ASR local ở M1; baseline và hệ thống cùng model + tham số; phải ước tính chi phí/cuộc gọi (tiêu chí 7). Toàn bộ local được điểm thưởng.

**11. Hỏi xác nhận quá nhiều có bị trừ không?**
Có. Quy tắc bổ sung (đã cài trong `reference_eval.py`): xác nhận lại slot đã xác nhận trong cùng phiên → tính câu hỏi thừa. Đọc vẹt 5–6 thông tin cũ trong câu chào bị trừ ở tiêu chí 6 và rubric LLM-judge (M2). Kịch bản `SC-27` (M2) còn có `max_agent_questions: 1` với khách hết kiên nhẫn.

## Team 8 — mentor anh Thạch

**1. Dataset tự build → metrics không cùng base.**
Đã xử lý: BTC phát catalog + khuyến mãi + chính sách dùng chung **và mock tool tham chiếu** (`eval/mock_tools.py`, để giá/tồn kho/KM của mọi team cho cùng kết quả), và chấm chéo trên **bộ test ẩn** cùng định dạng `test_set/public_sample/`. 5 chỉ số bắt buộc để so giữa các team tính bằng `eval/reference_eval.py` trên trace của team (`schemas/trace_log.schema.json`). Dataset riêng của team vẫn cần cho phát triển, cho vòng cải tiến 2 vòng, và được chấm ở tiêu chí 1 về chất lượng thiết kế.

**2. Customer simulator phụ thuộc thiết kế.**
Đúng, nên BTC chuẩn hóa simulator: `simulator/customer_simulator_spec.md` (8 quy tắc phản ứng, cơ chế kiên nhẫn theo persona/cuộc, chạy 3 seed) + `personas.json` (prompt persona chuẩn). Chấm chéo 5 chỉ số vẫn dùng `customer_turns` viết sẵn; simulator chấm ở phần thiết kế và tính lặp lại (độ lệch TSR giữa 3 seed ≤ 10 điểm).

**3. Calls-to-Close.**
Số cuộc gọi trung bình đến khi chốt được đơn, tính trên khách đã chốt. Trong bộ test đa phiên: đơn được `order.create` ở cuộc thứ mấy. Hệ thống có bộ nhớ tốt chốt ở cuộc 2 thay vì cuộc 3 — chỉ số kinh tế trực tiếp nhất. M2, không bắt buộc; script tham chiếu đã tính sẵn.

**4. Recall@k cần label.**
BTC phát `rag/qa_labeled.json` (60 câu, 6 loại, gán `chunk_id` theo mã mục `[XX-nn]` trong 14 tài liệu `policy/`, có phiên bản cũ và tài liệu nội bộ làm bẫy). Team nào làm RAG chạy `reference_eval.py --rag` để có Recall@3/@5, abstain rate cùng cơ sở. Tài liệu riêng của team: tự gán nhãn, chấm về phương pháp.

## Team 10 — mentor anh Tuấn

**1. 1 turn hay multi-turn, text hay audio?**
Multi-turn và **đa phiên**: mỗi kịch bản 2–3 cuộc gọi cùng một khách, mỗi cuộc nhiều lượt (`customer_turns`). Đánh giá tự động (RQR, CCR, TSR, HR) chạy trên text. Audio chỉ dùng đo WER/CER/Entity Accuracy trên `asr/` (12 hội thoại đa lượt của BTC + ≥ 20 file của team), sau đó text ASR đi qua cùng pipeline. Hội thoại BTC có 2 người nói nên M2 dùng luôn để chấm diarization.

**2. STT local hay API? Trả text hay audio?**
ASR bắt buộc local ở M1 (Whisper / PhoWhisper / faster-whisper). LLM được dùng API. Agent xử lý text và trả text là đủ cho M1. TTS / voice gần real-time là M2 (TTFA p95 ≤ 2,5 s), chỉ làm khi M1 đã ổn.
