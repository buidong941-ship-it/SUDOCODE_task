# datagen — sinh kịch bản test theo định dạng BTC

```
templates/*.json  ──resolver.py──▶  out/{dev,test}/GEN-*.json  ──validate.py──▶  báo cáo lỗi + coverage
                    (mock_tools BTC)                               (mock_tools + reference_eval BTC)
```

## Lệnh
```bash
python resolver.py                         # sinh toàn bộ → out/dev, out/test (+ out/manifest.json)
python resolver.py --only T05-km-het-han --instances 5
python resolver.py --seed 7 --out out_seed7 # bộ khác, cùng template
python resolver.py --reproduce             # tái tạo 7 SAMPLE của BTC → out/reproduce (kiểm tra resolver)

python validate.py out/dev out/test --report out/validate_report.json
python validate.py out/reproduce --diff-against ../test_set/public_sample
python validate.py ../test_set/public_sample   # kiểm cả dữ liệu BTC
```
Gói dữ liệu BTC được tìm tự động ở gốc repo (`../eval/mock_tools.py`); dùng `--btc <thư mục>` nếu để chỗ khác.
Windows: đặt `PYTHONIOENCODING=utf-8` nếu terminal lỗi Unicode.

## Nguyên tắc
- Giá, KM, tồn kho, ngày về hàng, ngày giao đều lấy từ `eval/mock_tools.py` của BTC. Không lấy từ LLM, không viết tay.
- Template khai báo **ràng buộc** (`require`); resolver dùng DFS có seed để tìm khách, SKU và ngày thoả ràng buộc. Nhờ đó mỗi template sinh được nhiều kịch bản khác nhau.
- Chia dev/test **theo template** để tránh rò rỉ câu chữ khi làm vòng cải tiến, nhưng tính **trong từng nhóm `hard_case`** (`plan_splits` trong `resolver.py`): nhóm ≥ 2 template luôn có ≥ 1 template ở dev và ≥ 1 ở test; nhóm chỉ 1 template thì chia theo instance (bản cuối vào test, ghi `_meta.split_by = "instance"`). Nhờ vậy loại ca nào cũng vừa được phát triển vừa được đo. Viết thêm template thứ hai cho các nhóm này để bỏ hẳn chia theo instance.
- Địa chỉ khách sinh theo SĐT và không trùng giữa hai khách; địa chỉ viết cứng trong template được giữ riêng.
- Harness chỉ được đọc lượt khách, kênh, ngày gọi — **không** đọc `_meta`, `facts_established`, `ground_truth_facts`, `success_if`. Bộ nhớ phải reset giữa các kịch bản (template T10/T11 cố ý dùng lại cùng khách CRM).
- `customer_turns` hiện là câu mẫu có điền giá trị. Bước sau là dùng LLM viết lại cho tự nhiên (giữ nguyên các slot), rồi chạy lại `validate.py`.

## Template
Xem docstring đầu `resolver.py`. Các biến và hàm dùng được trong `{{ }}`:
`cust` (id, name, xh, Xh, phone, fb_id, zalo_id, region, address, sessions), `p` (sku, vsku, name, short, list, price_list, attrs, size, color_vi),
`D` (ngày từng call), `final/q/disc/best_promo/promos/promo_active/promo_end/promo_label`, `in_stock/restock/inv/eta`, `basket_total`,
`vnd/k/trieu/trieu_words/num_words/spoken/teen/price_forms/money_regex`, `add/days/ddmm/weekday/region_days`, `new_order_id/new_digits`, `pick`, `DROP`.

## Phát hiện về dữ liệu BTC (validator)
- SAMPLE-02 call_2: `promo_active=false`, nhưng ngày 18/10 GIFT-FILTER vẫn áp cho AP-X (hết hạn 22/10).
- RUN-10 là KM `once_per_customer`: sau khi đã đặt đơn với RUN-10, `order.update` đổi size sẽ tính giá mới **không còn giảm**, nên mock thu thêm chênh lệch.
- README của BTC nhắc tới `eval/validate_scenarios.py` nhưng gói không có file này. `validate.py` ở đây thay thế nó.
