# Hướng dẫn đo latency thống nhất (bổ sung cho bảng "Chế độ hoạt động & hiệu năng")

## Định nghĩa (đã chỉnh sửa, thay dòng "Thời gian phản hồi mỗi lượt")

| Chỉ số | Mốc bắt đầu | Mốc kết thúc | M1 (chat) | M2 (voice) |
|---|---|---|---|---|
| TTFT | request lượt chat đến API backend | token đầu tiên của câu trả lời được sinh | p95 ≤ 3 s | — |
| Total latency | như trên | token cuối cùng | p95 ≤ 8 s | — |
| TTFA | người dùng dừng nói (VAD end-of-speech) | byte audio đầu tiên được phát | — | p95 ≤ 2,5 s |
| Call Brief | sự kiện nhận diện SĐT (cuộc gọi/chat đến) | object CallBrief sẵn sàng / hiển thị | ≤ 5 s | ≤ 3 s |

## Quy tắc đo

1. Đo tại **ranh giới backend/harness** (middleware ghi timestamp lúc nhận request và lúc emit token). Không tính thời gian render UI và mạng phía client. Nhóm muốn báo thêm số end-to-end từ UI thì ghi riêng.
2. Chạy **toàn bộ lượt của bộ test** (tối thiểu 100 lượt). Bỏ 3 lượt đầu (warm-up: nạp model, kết nối DB). p95 tính theo `reference_eval.py`.
3. Ghi vào trace log (`latency.ttft_ms`, `latency.total_ms`, `latency.ttfa_ms`, `call_brief_latency_ms`) — script chấm tự tổng hợp.
4. Baseline và hệ thống đo **cùng phần cứng / cùng API / cùng model**. Báo cáo ghi rõ: CPU/GPU, RAM, model + tham số, nhà cung cấp API, thời điểm chạy.
5. Call Brief: được **precompute** phần tóm tắt episodic ở cuối phiên trước (khai báo trong `precomputed_parts`), nhưng tại thời điểm nhận diện SĐT phải chạy lại bước kiểm tra tính mới (KM còn hạn? tồn kho? có tương tác kênh khác sau phiên trước?) — thời gian bước này tính vào Call Brief latency.
6. Với M1 xử lý file ghi âm offline: thời gian ASR **không** tính vào TTFT (ghi riêng "ASR time / phút audio").
7. Streaming là được phép và khuyến khích; nếu không streaming thì TTFT = Total.
