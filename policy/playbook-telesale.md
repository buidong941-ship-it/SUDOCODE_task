# Playbook telesale — xử lý phản đối & quy tắc phát ngôn (Shop BTC, 10/2026)

Playbook là hướng dẫn cho nhân viên và agent. Nó **không** chứa giá/chính sách; các con số phải lấy từ catalog và tài liệu chính sách.

## [PB-01] Nguyên tắc mở đầu với khách gọi lại
Chào bằng tên và xưng hô đã lưu; nhắc lại tối đa **2 thông tin** liên quan nhất của phiên trước (sản phẩm + rào cản) dưới dạng câu xác nhận; không đọc lại toàn bộ hồ sơ. Nếu Call Brief không khớp với điều khách đang nói (khách hỏi ngành hàng khác, xưng tên khác), hỏi xác nhận danh tính một câu trước khi tiếp tục.

## [PB-02] Phản đối "đắt quá"
Không so giá với đối thủ, không xác nhận hay phủ nhận giá đối thủ khách nêu. Trả lời bằng giá trị đi kèm có trong tài liệu: bảo hành, đổi trả, quà tặng, giao lắp, chính hãng. Nếu khách vẫn muốn giảm: nêu chương trình hiện hành (nếu có); không hứa mức giảm ngoài chương trình; đơn số lượng lớn → "em xin phép chuyển quản lý xem xét và báo lại trong ngày".

## [PB-03] Phản đối "để hỏi người nhà"
Xác nhận thời điểm gọi lại cụ thể (ngày + khung giờ), ghi lịch bằng `schedule.callback`; nhắc thời hạn khuyến mãi nếu có (chỉ chương trình đang hiệu lực). Không tạo áp lực giả ("chỉ còn 1 máy") khi tồn kho không xác nhận điều đó.

## [PB-04] Phản đối "bên kia rẻ hơn"
Như PB-02. Tuyệt đối không nói xấu đối thủ, không nói "hàng bên đó là hàng giả".

## [PB-05] Khách hỏi ngoài tài liệu
Trả lời "hiện em chưa có thông tin về…", ghi nhận câu hỏi, hẹn phản hồi qua kênh khách chọn. Không suy đoán thông số, xuất xứ, tác dụng y tế.

## [PB-06] Câu hỏi y tế / an toàn cho trẻ / thuốc
Không tư vấn. Chuyển máy cho dược sĩ/nhân viên phụ trách với handoff brief. Với sản phẩm mẹ & bé, chỉ nêu thông số hãng công bố.

## [PB-07] Khách hỏi "em là người hay máy?"
Trả lời trung thực là trợ lý ảo/AI của shop, có thể chuyển người thật nếu khách muốn. Không né tránh, không nói "em là nhân viên".

## [PB-08] Thông tin cá nhân
Không đọc lại đầy đủ SĐT/địa chỉ/CCCD của khách ngoài mục đích xác nhận giao hàng; số CCCD, số tài khoản chỉ nhập vào biểu mẫu hệ thống, không nhắc lại thành lời, không ghi vào ghi chú. Khi khách yêu cầu xóa dữ liệu → làm theo QT-06.

## [PB-09] Chốt đơn
Trước khi gọi `order.create`: đọc lại một lần: sản phẩm (đúng biến thể), số lượng, giá cuối sau khuyến mãi, địa chỉ, phương thức thanh toán, thời gian giao dự kiến theo VC-01 (tính cả ngày nghỉ). Đơn trên 10 triệu không COD.

## [PB-10] Khách giận / hết kiên nhẫn
Xin lỗi ngắn, đi thẳng vào việc, không hỏi thêm quá 1 câu xác nhận; nếu lỗi do shop (báo giá sai giữa các kênh) thì thừa nhận và giải thích ngắn gọn lý do (khuyến mãi theo thời điểm), không đổ lỗi cho khách.

## [PB-11] Khách nhiều lần không mua
Sau 3 phiên không chốt: không gọi lại chủ động nữa trừ khi khách hẹn; ghi nhận "pending queue" và chỉ liên hệ khi có chương trình mới liên quan sản phẩm khách quan tâm.
