# Đặc tả Customer Simulator chuẩn BTC (M2)

Mục đích: để kết quả simulator giữa các team **so sánh được** (phản hồi Team 8), BTC quy định persona, cơ chế kiên nhẫn và cách log. Team tự chọn model đóng vai (khuyến nghị cùng model với agent, temperature 0.3, seed cố định) nhưng phải dùng prompt persona trong `personas.json` và quy tắc dưới đây. Điểm chấm là **thiết kế + tính lặp lại**, không phải con số tuyệt đối.

## 1. Trạng thái simulator
```
state = {
  "persona_id", "goal" (customer_goal của kịch bản), "facts" (facts_established đã biết),
  "patience": P0,                # kiên nhẫn ban đầu theo persona (2–5)
  "asked_slots": set(),          # slot agent đã hỏi
  "irritation": 0,               # tăng khi bị hỏi lại
  "committed": false,            # đã đồng ý mua/hẹn
}
```

## 2. Quy tắc phản ứng (áp dụng theo thứ tự)
1. **Hỏi lại slot đã có** (slot ∈ must_not_ask, hoặc đã trả lời trong phiên): `patience -= 1`, `irritation += 1`; khách vẫn trả lời nhưng thêm câu phàn nàn ("hôm trước chị nói rồi mà"). Câu **xác nhận** (dạng "vẫn … đúng không ạ?") không trừ kiên nhẫn **lần đầu**; lần thứ 2 cùng slot trừ như câu hỏi mở.
2. **patience == 0**: khách kết thúc ("thôi để chị xem lại") → cuộc gọi kết thúc, `outcome = "tu_choi"`. Với persona `khach_goi_lan_3_het_kien_nhan`, P0 = 1 ở cuộc thứ 3.
3. **Agent bịa/khác giá đã biết**: khách phản ứng ("hôm trước em bảo 4.890 mà?"), `patience -= 1`, và **không** chấp nhận giá mới cao hơn nếu không có giải thích (agent phải nêu lý do: KM hết hạn).
4. **Agent hỏi thông tin mới cần thiết** (địa chỉ giao, phương thức thanh toán): khách trả lời bình thường, không trừ.
5. **Agent đề xuất đúng nhu cầu + giá khớp kỳ vọng (`success_if`)**: khách đồng ý theo `expected_outcome`; nếu kịch bản là `hen_goi_lai`, khách vẫn hẹn lại dù agent thuyết phục.
6. **Agent im lặng/ trả lời lạc đề 2 lượt liên tiếp**: khách hỏi "em còn đó không?", lần 3 cúp máy.
7. Khách **không bao giờ** tự cung cấp thông tin ngoài `facts_established` + `customer_turns` của kịch bản; nếu agent hỏi thứ không có trong kịch bản, khách trả lời "chị không rõ" (không bịa) — tránh simulator tự sinh fact làm lệch ground truth.
8. Tối đa **12 lượt khách** mỗi cuộc; vượt → kết thúc `outcome = "timeout"`.

## 3. Bám kịch bản
Simulator nhận `customer_turns` làm "dàn ý" (những điều khách *sẽ* nói theo thứ tự) và chỉ diễn đạt lại theo persona, không thêm ý mới. Nếu agent đã trả lời trước điều khách định hỏi, bỏ qua lượt đó.

## 4. Log bắt buộc
Mỗi cuộc: `{"scenario_id","call","persona_id","seed","patience_trace":[...],"outcome","n_turns","ended_by":"agent|customer|timeout"}`. Chạy **3 seed** cho mỗi kịch bản và báo cáo trung bình ± độ lệch — đây là "tính lặp lại".

## 5. Chấm
BTC chấm: (a) có cài đúng 8 quy tắc trên (đọc code/prompt); (b) chạy lại 3 seed cho 5 kịch bản BTC chọn, độ lệch TSR ≤ 10 điểm; (c) simulator không rò rỉ ground truth cho agent (không đưa `must_not_ask`/`success_if` vào prompt của khách hàng theo cách agent nhìn thấy).
