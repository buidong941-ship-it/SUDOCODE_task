# FAQ tư vấn sản phẩm — Shop BTC (phiên bản 2026-10)

Đây là tài liệu nghiệp vụ cho telesale. Agent chỉ được trả lời những gì có trong tài liệu này, catalog và promotions; câu hỏi ngoài phạm vi phải nói "chưa có thông tin" và ghi nhận lại.

## [FAQ-01] Chọn máy lọc không khí theo diện tích phòng
Chọn máy có `room_area_m2` trong catalog **lớn hơn hoặc bằng** diện tích phòng thực tế. Phòng 20–25m²: AirPure X, AirPure Y, XM-4L (tối đa 43m² nhưng giá thấp hơn). Phòng 30–45m²: AirPure Pro, Xiaomi 4 Pro, Samsung AX40. Phòng dưới 15m² hoặc để bàn: AirPure Mini.

## [FAQ-02] Nhà có trẻ nhỏ nên chọn máy nào
Ưu tiên máy có **khóa trẻ em** (`child_safe_lock: true`): AirPure Y, AirPure Pro, Samsung AX40. AirPure X không có khóa trẻ em nhưng có chế độ ngủ êm. Không có bằng chứng máy lọc không khí chữa bệnh; **không được** tư vấn máy có tác dụng y tế.

## [FAQ-03] Máy lọc không khí lọc được gì
HEPA H13 lọc bụi mịn PM2.5, phấn hoa, lông thú, vi khuẩn bám bụi. Than hoạt tính (AirPure Y, Samsung AX40) khử mùi, khói bếp, VOC nhẹ. Tài liệu **không có thông tin** về khí radon, formaldehyde ở nồng độ công nghiệp, hay xuất xứ màng lọc — agent phải nói không có thông tin.

## [FAQ-04] Máy lọc không khí khác nhau giữa AirPure X và Y
Y có thêm than hoạt tính, app điều khiển, khóa trẻ em; giá cao hơn X 310.000đ theo catalog. Cùng dùng màng lọc thay thế SKU-AP-FLT-X.

## [FAQ-05] Chọn máy lọc nước theo nguồn nước
Nước máy thành phố: RO 9 lõi (Karofi) hoặc UF Sunhouse là đủ. **Nước giếng khoan** hoặc nước nhiễm phèn/đá vôi: bắt buộc RO, khuyến nghị **RO 10 lõi (Kangaroo)** vì có lõi tiền xử lý bổ sung. Gia đình 4–6 người: RO công suất tiêu chuẩn đều đáp ứng.

## [FAQ-06] Máy lọc nước RO có tốn điện, tốn nước không
RO thải nước theo tỷ lệ khoảng 1:1 đến 1:2 (1 lít nước sạch thải 1–2 lít). Công suất điện 24–36W, chỉ chạy khi lọc. Máy UF không thải nước, không cần điện.

## [FAQ-07] Nồi chiên không dầu: chọn dung tích
2–3 người: 4L (Lock&Lock, Xiaomi 4.5L). 4–6 người: 6.2L (Philips). Nồi Philips có chế độ nướng bánh và sấy hoa quả; Xiaomi điều khiển qua app.

## [FAQ-08] Quạt DC inverter khác gì quạt thường
Quạt DC (Panasonic F-409) tiết kiệm điện 50–60%, êm hơn, có nhiều mức gió và điều khiển từ xa. Quạt Senko là quạt AC giá rẻ, không có remote.

## [FAQ-09] Chọn size giày
Size giày theo chiều dài bàn chân: 38 ↔ 24cm, 39 ↔ 24.5cm, 40 ↔ 25cm, 41 ↔ 25.5cm, 42 ↔ 26cm, 43 ↔ 26.5cm. Giày chạy bộ RunLite nên chọn **lớn hơn nửa size** so với giày thường. Giày trekking HikePro form rộng, chọn đúng size.

## [FAQ-10] Giày còn size không
Kiểm tra bằng tool `inventory.check` với `variant_sku` (ví dụ `SKU-SN-RUN1-41-DEN`). **Không được** hứa còn hàng khi chưa gọi tool.

## [FAQ-11] Máy hút sữa: chọn Spectra S1 hay Medela Swing Maxi
Spectra S1 có pin sạc, hút đôi, êm, giá thấp hơn. Medela Swing Maxi nhỏ gọn, công nghệ 2-phase, phụ kiện dễ mua hơn. Cả hai đều hút đôi. Tài liệu không có thông tin y tế về sữa mẹ, thuốc, bệnh lý — mọi câu hỏi y tế phải **chuyển máy** cho nhân viên/dược sĩ phụ trách.

## [FAQ-12] Xe đẩy Joie Pact và Combi Sugocal
Joie Pact: gấp gọn một tay, nặng 6kg, chịu tải 22kg, dùng từ sơ sinh đến ~4 tuổi, có màu đen và xám. Combi Sugocal: 2 chiều (bé nhìn mẹ hoặc nhìn đường), chịu tải 15kg (~3 tuổi), nặng 5.2kg, màu navy và be. Cả hai đủ tiêu chuẩn lên máy bay hành lý xách tay theo hãng.

## [FAQ-13] Ghế ngồi ô tô Chicco
Dùng cho bé 0–4 tuổi (đến 18kg), lắp bằng dây an toàn hoặc ISOFIX. Không có thông tin về khả năng tương thích với từng dòng xe cụ thể.

## [FAQ-14] Khuyến mãi
Chỉ áp dụng khuyến mãi có trong `promotions.json` và **còn hiệu lực tại ngày báo giá**. Khuyến mãi đã hết hạn không được áp dụng lại dù khách đã được báo trước đó; nhân viên xin lỗi, giải thích, và giới thiệu khuyến mãi hiện hành nếu có. Không được tiết lộ khuyến mãi chưa bắt đầu (ví dụ 11/11). Khuyến mãi ghi `stackable: false` không cộng dồn với nhau; `stackable: true` (freeship, COD-0) cộng dồn với mọi khuyến mãi khác.

## [FAQ-16] Sản phẩm ngừng bán
AirPure X bản 2024 và RunLite 1 (2025) đã ngừng bán từ 01/06/2026 (changelog CL-05). Khách hỏi mua lại → giới thiệu sản phẩm thay thế (`successor_sku` trong catalog); khách đang dùng bản cũ vẫn mua được màng lọc SKU-AP-FLT-X và được tham gia thu cũ đổi mới TRADE-IN-AP (KM-09).

## [FAQ-17] Hết hàng
Khi tool `inventory.check` trả `in_stock: false`: không tạo đơn chờ, không hứa ngày về trừ khi có trong ghi chú nhập hàng (chỉ được nói **ngày dự kiến**, không nói số lượng hay nhà cung cấp); đề xuất sản phẩm tương đương còn hàng hoặc đặt lịch báo lại khi có hàng.

## [FAQ-18] Combo
Combo (SKU-BDL-*) là một SKU riêng, giá đã gồm tiết kiệm (`saving_vnd`); không áp thêm khuyến mãi của sản phẩm thành phần; bảo hành theo từng thành phần. Không tách combo để đổi trả một phần.

## [FAQ-19] Mua nhiều máy lọc không khí
Hai máy trở lên trong cùng đơn: AIR-2ND-50 giảm 50% máy rẻ hơn (KM-05). Tổng đơn trên 10 triệu không COD (VC-03) → hướng dẫn chuyển khoản hoặc tách đơn theo QT-01.

## [FAQ-15] Phạm vi tư vấn của agent
Agent không tư vấn y tế, không so sánh với giá cụ thể của đối thủ (chỉ được nêu giá trị đi kèm: bảo hành, giao nhanh, đổi trả), không hứa thời gian giao ngoài chính sách VC-01, không tự tạo giảm giá. Nếu khách hỏi agent có phải người thật không: trả lời trung thực là trợ lý AI.
