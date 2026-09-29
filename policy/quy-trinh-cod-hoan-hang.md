# Quy trình COD, hoàn hàng & hoàn tiền — Shop BTC (2026-10)

## [QT-01] Xác nhận đơn COD trước giao
Đơn COD trên 2.000.000đ: nhân viên gọi xác nhận trong vòng 4 giờ làm việc kể từ khi tạo đơn, hỏi lại: sản phẩm, số lượng, địa chỉ, khung giờ nhận. Đơn không xác nhận được sau 2 cuộc gọi cách nhau tối thiểu 3 giờ → giữ 3 ngày → hủy tự động. Đơn **trên 10.000.000đ không áp dụng COD**; nhân viên hướng dẫn chuyển khoản hoặc tách đơn nếu khách đồng ý (tách đơn không làm mất điều kiện khuyến mãi `min_qty` nếu các đơn tạo cùng ngày và cùng SĐT).

## [QT-02] Khách từ chối nhận COD
Lần 1: ghi nhận lý do, không phạt. Lần 2 trong 6 tháng: các đơn sau yêu cầu chuyển khoản trước 100%. Hàng hoàn kho trong 3–5 ngày; nếu là hàng đặt riêng (bundle theo yêu cầu), khách chịu phí ship 2 chiều.

## [QT-03] Tiếp nhận yêu cầu đổi/trả
Nhân viên tạo yêu cầu bằng `order.update` với `action` là `exchange_size`, `exchange_product` hoặc `return`, kèm `reason`. Yêu cầu chỉ hợp lệ trong thời hạn DT-01. Với `exchange_product`: nếu sản phẩm mới rẻ hơn, phần chênh lệch được **hoàn lại** cho khách (theo DT-04); nếu đắt hơn, khách thanh toán phần chênh khi nhận hàng (COD) hoặc chuyển khoản.

## [QT-04] Hoàn tiền
Thời gian 3–5 ngày làm việc kể từ khi kho xác nhận nhận hàng đạt điều kiện. Kênh hoàn: đơn COD → chuyển khoản ngân hàng khách cung cấp; đơn online → về phương thức ban đầu. **Thông tin tài khoản ngân hàng, CCCD của khách chỉ được nhập vào biểu mẫu hoàn tiền của hệ thống, không ghi vào ghi chú hội thoại hay bộ nhớ khách hàng**; trong log chỉ lưu 4 số cuối.

## [QT-05] Sản phẩm lỗi khi nhận
Khách phát hiện lỗi ngoại quan lúc nhận COD: từ chối nhận, không mất phí. Phát hiện lỗi sau khi nhận: chụp ảnh/video gửi Zalo OA trong 48 giờ; shop đổi mới 1-1 theo DT-05, shop chịu toàn bộ phí vận chuyển.

## [QT-06] Xóa dữ liệu theo yêu cầu khách
Khách yêu cầu xóa thông tin cá nhân: nhân viên xác nhận lại bằng một câu, ghi nhận yêu cầu, hệ thống xóa hồ sơ (profile, episodic) trong 72 giờ, giữ lại lịch sử đơn hàng theo yêu cầu kế toán (ẩn danh hóa SĐT). Sau khi xóa, khách gọi lại được coi là khách mới.
