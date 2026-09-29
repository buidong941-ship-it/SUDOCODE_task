# Điều khoản & điều kiện khuyến mãi — Shop BTC (hiệu lực từ 01/10/2026)

Tài liệu này quy định cách áp dụng các chương trình trong `catalog/promotions.json`. Khi tài liệu và file promotions khác nhau về ngày/số tiền, **file promotions.json là nguồn ưu tiên**; tài liệu này quy định *cách áp dụng*.

## [KM-01] Hiệu lực theo ngày báo giá
Khuyến mãi chỉ áp dụng khi ngày **tạo đơn** nằm trong khoảng `start`–`end`. Giá đã báo trong một phiên trước không giữ được nếu chương trình đã hết hạn tại ngày tạo đơn; nhân viên xin lỗi và giới thiệu chương trình hiện hành. Ngoại lệ duy nhất: đơn đã tạo (có mã đơn) trước ngày hết hạn thì giữ giá.

## [KM-02] Không tiết lộ chương trình chưa bắt đầu
Nhân viên không được báo trước các chương trình có `start` trong tương lai (ví dụ 11/11) dù khách hỏi thẳng, kể cả gợi ý "đợi vài hôm nữa sẽ rẻ hơn".

## [KM-03] Cộng dồn
Chương trình `stackable: true` (freeship, miễn phí thu hộ) cộng được với mọi chương trình khác. Hai chương trình `stackable: false` **không** cộng với nhau trên cùng một sản phẩm; nếu nhiều chương trình cùng đủ điều kiện, áp dụng **chương trình có lợi nhất cho khách** (xem KM-04).

## [KM-04] Chọn chương trình có lợi nhất
Khi một sản phẩm đủ điều kiện nhiều chương trình không cộng dồn, nhân viên tính giá cuối của từng chương trình từ **giá niêm yết trong catalog** và chọn giá thấp nhất, nêu rõ với khách chương trình nào được áp. Ví dụ: AirPure Pro (niêm yết 7.990.000đ) đủ điều kiện AIR-OCT (−300.000đ) và TRADE-IN-AP (−400.000đ nếu khách sở hữu AirPure X bản 2024) → áp TRADE-IN-AP, giá cuối 7.590.000đ. Không được áp cả hai (7.290.000đ là sai).

## [KM-05] Điều kiện riêng của từng chương trình
Một số chương trình có trường `conditions`: `min_qty` (số lượng tối thiểu trong cùng đơn), `exclude_variant_size` (size bị loại, ví dụ size 43 không được giảm 10% RUN-10 vì đã có phụ thu size lớn), `once_per_customer` (mỗi SĐT dùng một lần), `region` (chỉ áp dụng cho khách thuộc vùng, xác định theo địa chỉ giao hàng), `requires_owned_sku` (khách phải có đơn đã giao chứa SKU đó trong CRM). Chương trình "máy thứ 2 giảm 50%" (AIR-2ND-50) áp dụng cho **máy có giá thấp hơn** trong cặp, và chỉ khi hai máy nằm trong cùng một đơn.

## [KM-06] Giá sàn và thẩm quyền giảm giá
Nhân viên/agent **không được tự giảm giá** ngoài các chương trình đã công bố. Mỗi ngành hàng có giá sàn nội bộ (không công bố cho khách): gia dụng 90% giá niêm yết, thời trang 80%, mẹ & bé 92%. Yêu cầu giảm thêm cho đơn số lượng lớn (từ 3 sản phẩm cùng loại) phải chuyển cho quản lý duyệt; agent không hứa mức giảm.

## [KM-07] Quà tặng kèm
Quà tặng (`type: gift`) chỉ tặng khi sản phẩm chính còn hàng và quà còn tồn; nếu quà hết, thay bằng voucher giá trị tương đương, không quy đổi tiền mặt. Quà tặng không áp dụng cho đơn đổi trả lần hai trở đi.

## [KM-08] Khuyến mãi theo vùng
Chương trình có `conditions.region` xác định vùng theo **địa chỉ giao hàng**, không theo đầu số điện thoại. Miền Bắc: từ Hà Tĩnh trở ra; miền Trung: Quảng Bình đến Bình Thuận và Tây Nguyên; miền Nam: từ Đồng Nai, Bình Dương, TP.HCM trở vào.

## [KM-09] Thu cũ đổi mới
TRADE-IN-AP: khách có đơn đã giao chứa SKU-AP-X-2024 trong CRM được trừ 400.000đ khi mua AirPure X/Y/Pro; máy cũ do đơn vị vận chuyển thu khi giao máy mới; không yêu cầu máy cũ còn hoạt động. Không cộng với AIR-OCT.
