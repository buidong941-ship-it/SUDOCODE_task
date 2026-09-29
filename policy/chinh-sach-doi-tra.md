# Chính sách đổi trả — Shop BTC (phiên bản 2026-10)

Mỗi mục có mã `[DT-xx]` — là `chunk_id` dùng để gán nhãn Recall@k. Khi chunk tài liệu, giữ nguyên ranh giới mục để chunk_id không bị trộn.

## [DT-01] Thời hạn đổi trả
Khách hàng được đổi hoặc trả sản phẩm trong vòng **7 ngày** kể từ ngày nhận hàng (tính theo ngày ký nhận trên đơn vận chuyển). Với ngành hàng gia dụng và mẹ & bé có lỗi kỹ thuật từ nhà sản xuất, thời hạn đổi mới là **30 ngày**.

## [DT-02] Điều kiện đổi trả
Sản phẩm còn nguyên tem, nhãn, hộp, chưa qua sử dụng (giày/áo chưa giặt, chưa có dấu hiệu mòn đế). Có hóa đơn hoặc mã đơn hàng. Sản phẩm thuộc nhóm đồ lót, bình sữa, núm ti đã bóc seal **không** được đổi trả vì lý do vệ sinh.

## [DT-03] Đổi size / màu (thời trang)
Đổi size hoặc màu lần **đầu tiên** cho cùng một đơn hàng: **miễn phí**, shop chịu phí vận chuyển hai chiều. Từ lần đổi thứ hai trở đi: khách chịu phí vận chuyển 30.000đ/chiều. Điều kiện: size/màu mới còn hàng; nếu hết hàng, khách được chọn sản phẩm khác cùng giá hoặc hoàn tiền.

## [DT-04] Hoàn tiền
Hoàn tiền trong **3–5 ngày làm việc** sau khi shop nhận lại hàng và kiểm tra đạt điều kiện. Đơn COD hoàn qua chuyển khoản ngân hàng; đơn thanh toán online hoàn về phương thức thanh toán ban đầu.

## [DT-05] Sản phẩm lỗi do nhà sản xuất
Đổi mới 1-1 trong 30 ngày với gia dụng và mẹ & bé nếu có xác nhận lỗi từ trung tâm bảo hành. Sau 30 ngày áp dụng chính sách bảo hành (xem chinh-sach-bao-hanh.md).

## [DT-06] Trường hợp không được đổi trả
Sản phẩm hư hỏng do người dùng (rơi vỡ, vào nước, dùng sai điện áp). Sản phẩm mua trong chương trình xả kho ghi rõ "không đổi trả". Quá 7 ngày kể từ ngày nhận (trừ lỗi nhà sản xuất).

## [DT-07] Cách yêu cầu đổi trả
Khách gọi hotline hoặc nhắn Zalo OA, cung cấp mã đơn hàng và lý do. Nhân viên tạo yêu cầu đổi trả trên hệ thống (tool `order.update` với action `exchange_size`, `exchange_product` hoặc `return`). Shop gửi đơn vị vận chuyển đến lấy hàng trong 1–2 ngày làm việc.
