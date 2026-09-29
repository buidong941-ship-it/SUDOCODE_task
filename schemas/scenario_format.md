# Định dạng kịch bản test (mở rộng Phụ lục B)

Mỗi file `SC-xx.json`: `scenario_id, level (M1|M2), persona, hard_case, customer_phone, customer_name, honorific, notes, calls{call_1..call_3}`.

Trường trong mỗi `call_n`:
| Trường | Ý nghĩa | Dùng cho |
|---|---|---|
| `channel`, `channel_identity` | hotline / chat_fanpage / zalo_oa + định danh kênh | identity resolution |
| `call_date` hoặc `days_later` | ngày của cuộc gọi (mặc định reference_date 2026-10-15 + cộng dồn days_later) | KM hết hạn, tồn kho theo ngày, TTL |
| `customer_turns` | lượt khách viết sẵn (deterministic) | chấm chéo |
| `customer_turns_asr` + `input_mode` | bản lỗi ASR / teencode — **hệ thống phải nhận bản này** nếu có | chuẩn hóa tiếng Việt |
| `seed_history` | phiên cũ (từ CRM) cần nạp trước khi gọi | TTL, khách cũ |
| `facts_established` | fact khách cung cấp trong call này (ground truth để ghi nhớ) | CCR của call sau |
| `must_carry_over` | slot bắt buộc dùng đúng ở call này | CCR |
| `must_not_ask` | slot không được hỏi mở | RQR |
| `success_if` | điều kiện Task Success (xem dưới) | TSR |
| `ground_truth_facts` | sự thật để đối chiếu claim | HR |
| `memory_expectation` | trạng thái bộ nhớ kỳ vọng sau call (giá trị mới, giá trị bị supersede, hồ sơ không được ghi nhầm) | memory_checks (sàng lọc) + chấm tay |
| `expected_outcome` | hen_goi_lai / chot_don / chuyen_may / tu_choi | over-escalation |

`success_if` hỗ trợ: `tool_called` (+ `args_match` ⊆ args; `null` = không cần tool), `also_ordered`, `total_match_vnd`, `brief_must_contain`, `must_say_any` (≥1 cụm xuất hiện trong lời agent), `agent_must_say` (cụm "không có thông tin"), `must_not_call_tools`, `forbidden_claims` ([{field,value}] hoặc chuỗi; value `"*any*"` = mọi giá trị), `trace_must_not_match` (regex trên agent_text + memory_writes + tool args → PII/nội bộ), `max_agent_questions`.

Ngày của call_n = `call_date` nếu có, nếu không = ngày call trước + `days_later` (call_1 mặc định 2026-10-15). Tool mock phải nhận ngày này qua `on`.
