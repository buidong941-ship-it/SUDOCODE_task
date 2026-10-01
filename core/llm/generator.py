"""Sinh lời thoại cho khách từ "kế hoạch lượt" (goals + facts) do harness dựng.

- `deepseek`: LLM viết câu tự nhiên, CHỈ được dùng con số/sự kiện có trong facts (guardrail kiểm lại sau).
- `offline` : câu mẫu điền sẵn — chỉ để kiểm thử pipeline khi không có mạng/khóa API, không dùng báo cáo số liệu.
generate() trả (text, ttft_ms, total_ms, usage).
"""
import json
import time

from core.config import settings

SYSTEM = """Bạn là nhân viên telesale (trợ lý AI) của shop bán lẻ online, nói tiếng Việt tự nhiên, lễ phép, đúng ngữ điệu bán hàng (dạ/vâng/ạ), xưng "em", gọi khách theo `honorific` trong dữ liệu.
QUY TẮC BẮT BUỘC:
1. Mọi giá tiền, khuyến mãi, tồn kho, ngày giao, mã đơn chỉ được lấy đúng từ FACTS. Không tự tính, không làm tròn khác, không bịa. Viết tiền dạng 5.200.000đ.
2. Thực hiện đúng các GOALS theo thứ tự; không tự hứa thêm điều gì ngoài FACTS.
3. Tối đa 1 câu hỏi mỗi lượt. Không hỏi lại thông tin trong KNOWN (chỉ được hỏi xác nhận kiểu "... đúng không ạ?").
4. Nếu FACTS không có thông tin khách hỏi: nói rõ "em chưa có thông tin" về điều đó, không đoán.
5. Không bao giờ nói mình là người thật. Không nhắc giá nhập, giá vốn, nhà cung cấp. Không bình luận hay chê bên khác.
6. Không đọc lại số CCCD/số tài khoản của khách.
7. Ngắn gọn: 1–3 câu, như nói qua điện thoại."""


class Generator:
    def __init__(self, backend=None):
        self.backend = backend or settings.generator_backend

    def generate(self, plan, retry_note=None):
        if self.backend == "deepseek":
            from core.llm.deepseek import DeepSeek
            user = ("DỮ LIỆU LƯỢT NÀY (JSON):\n" + json.dumps(plan, ensure_ascii=False, default=str)
                    + "\n\nViết câu trả lời của nhân viên cho lượt này.")
            if retry_note:
                user += f"\nLƯU Ý: bản trước bị chặn vì: {retry_note}. Sửa lại, chỉ dùng số trong FACTS."
            msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
            return DeepSeek().chat(msgs)
        t0 = time.perf_counter()
        text = render_offline(plan)
        ms = int((time.perf_counter() - t0) * 1000)
        return text, ms, ms, None


# ---------------------------------------------------------------------- câu mẫu (offline)
def _vnd(x):
    return f"{int(x):,}".replace(",", ".") + "đ"


def _dm(d):
    return f"{int(d[8:10])}/{int(d[5:7])}" if d and len(d) >= 10 else d


def render_offline(plan):
    h = plan.get("honorific") or "anh/chị"
    F = plan.get("facts", {})
    out = []
    for g in plan.get("goals", []):
        q = F.get("quote") or {}
        if g == "opening_returning":
            b = F.get("brief", {})
            pa = b.get("product_name")
            s = f"Dạ em chào {h} {plan.get('customer_name') or ''}".strip() + ","
            if pa:
                s += f" hôm {b.get('last_date_ddmm', 'trước')} bên em có tư vấn {h} mẫu {pa}"
                if b.get("price_quoted_vnd"): s += f" giá {_vnd(b['price_quoted_vnd'])}"
                s += "."
            if b.get("blocker"): s += f" {h.capitalize()} đã trao đổi với người nhà chưa ạ?"
            out.append(s)
        elif g == "greet":
            out.append(f"Dạ em chào {h}, em có thể hỗ trợ gì cho {h} ạ?")
        elif g == "ask_identity":
            out.append(f"Dạ số này bên em có nhiều hồ sơ, cho em xin tên của {h} để em hỗ trợ đúng ạ?")
        elif g in ("recommend", "quote"):
            if q:
                s = ("Dạ em gợi ý " if g == "recommend" else "Dạ ") + f"mẫu {q['name']} giá {_vnd(q['final_price_vnd'])}"
                if q.get("promo_names"): s += f", đang có ưu đãi {', '.join(q['promo_names'])}"
                if q.get("in_stock") is False: s += ", hiện mẫu này đang tạm hết hàng"
                out.append(s + " ạ.")
        elif g == "alternative_quote" and F.get("alternative"):
            a = F["alternative"]; out.append(f"Còn mẫu {a['name']} giá {_vnd(a['final_price_vnd'])} ạ.")
        elif g == "stale_promo":
            out.append("Dạ chương trình khuyến mãi hôm trước đã hết hạn rồi ạ, em báo lại giá hiện tại cho mình.")
        elif g == "out_of_stock":
            r = F.get("restock_expected")
            out.append("Dạ mẫu này hiện đang tạm hết hàng" + (f", dự kiến có hàng lại ngày {r}" if r else "") + " ạ.")
        elif g == "discontinued":
            out.append(f"Dạ mẫu {F.get('discontinued_name')} đã ngừng kinh doanh, bên em có mẫu thay thế là {F.get('successor_name')} ạ.")
        elif g == "ask_product":
            out.append(f"Dạ {h} đang quan tâm sản phẩm nào để em tư vấn ạ?")
        elif g == "ask_variant":
            out.append(f"Dạ {h} lấy size và màu nào ạ?")
        elif g == "ask_address":
            out.append(f"Dạ {h} cho em xin địa chỉ nhận hàng ạ?")
        elif g == "order_created":
            o = F["order"]; out.append(f"Dạ em đã lên đơn {o['order_id']} cho {h}, tổng {_vnd(o['total_vnd'])}, dự kiến giao ngày {_dm(o.get('estimated_delivery'))} ạ.")
        elif g == "ask_need":
            miss = F.get("need_slots_missing") or []
            out.append(f"Dạ nhà mình có bé nhỏ không {h} ạ?" if "has_children" in miss else f"Dạ {h} dự định ngân sách khoảng bao nhiêu ạ?")
        elif g == "ask_new_size":
            out.append(f"Dạ {h} muốn đổi sang size mấy ạ?")
        elif g == "exchange_offer":
            e = F.get("exchange_preview", {})
            out.append(f"Dạ {e.get('new_variant')} " + ("còn hàng" if e.get("in_stock") else "đang tạm hết") +
                       f", đổi size lần đầu bên em miễn phí ạ. Em làm thủ tục đổi cho {h} nhé?")
        elif g == "exchange_window_passed":
            o = F.get("old_order", {}); out.append(f"Dạ đơn {o.get('product')} mua ngày {_dm(o.get('date'))} đã quá thời hạn đổi trả 7 ngày ạ.")
        elif g == "explain_price_change":
            out.append(f"Dạ mức {_vnd(F['claimed_price_vnd'])} là giá khi còn khuyến mãi, chương trình đó nay đã hết hạn nên giá hiện tại là {_vnd(q.get('final_price_vnd'))} ạ.")
        elif g == "cart_total":
            ct = F["cart"]; out.append("Dạ " + ", ".join(f"{i['name']} {_vnd(i['final_price_vnd'])}" for i in ct["items"]) + f", tổng {_vnd(ct['total_vnd'])} ạ.")
        elif g == "cod_ok":
            out.append("Dạ đơn này mình thanh toán khi nhận hàng (COD) được ạ.")
        elif g == "address_updated":
            out.append(f"Dạ em đã cập nhật địa chỉ giao mới {F['address_update']['address']} cho đơn của {h} ạ.")
        elif g == "confirm_old_address":
            out.append(f"Dạ địa chỉ cũ bên em lưu là {F['old_address']}, {h} vẫn nhận ở đó đúng không ạ?")
        elif g == "confirm_order":
            out.append(f"{h.capitalize()} xác nhận giúp em để em lên đơn luôn nhé?")
        elif g == "ask_size_for_price":
            out.append(f"Dạ giá và ưu đãi mẫu này khác nhau theo size, {h} đi size mấy để em báo đúng giá ạ?")
        elif g == "order_exists":
            o = F["order"]; out.append(f"Dạ đơn {o['order_id']} của {h} em đã lên rồi ạ, dự kiến giao ngày {o.get('estimated_delivery')}.")
        elif g == "confirm_new_price":
            out.append(f"{h.capitalize()} có muốn em lên đơn với giá hiện tại không ạ?")
        elif g == "cod_limit":
            t = F.get("cod_total_vnd"); out.append(f"Dạ đơn{' tổng ' + _vnd(t) if t else ''} trên 10 triệu bên em không nhận COD, {h} chuyển khoản giúp em được không ạ?")
        elif g == "order_failed":
            out.append(f"Dạ em chưa tạo được đơn ({F.get('order_error')}), em kiểm tra lại và báo {h} ngay ạ.")
        elif g == "order_updated":
            u = F["update"]; s = f"Dạ em đã tạo yêu cầu cho đơn {u.get('order_id')}"
            if u.get("refund_vnd"): s += f", bên em hoàn lại {_vnd(u['refund_vnd'])}"
            if u.get("extra_payment_vnd"): s += f", {h} bù thêm {_vnd(u['extra_payment_vnd'])}"
            out.append(s + ", bên vận chuyển sẽ qua lấy hàng ạ.")
        elif g == "order_not_found":
            out.append(f"Dạ em chưa tìm thấy đơn của {h}, {h} đọc giúp em mã đơn ạ?")
        elif g == "order_status":
            os_ = F.get("orders") or []
            out.append("Dạ " + "; ".join(f"đơn {o['order_id']} đang {o.get('status')}" + (f", mã vận đơn {o['tracking']}" if o.get("tracking") else "") for o in os_) + " ạ." if os_ else f"Dạ em chưa thấy đơn nào của {h} ạ.")
        elif g == "callback_scheduled":
            c = F["callback"]; s = f"Dạ em hẹn gọi lại {h} lúc {c['callback_at'][11:16]} {c.get('weekday', '')} ngày {c.get('ddmm')}"
            if c.get("moved_reason"): s += f" vì {c['moved_reason']}"
            out.append(s + " ạ.")
        elif g == "defer_ack":
            out.append(f"Dạ vâng, {h} cứ trao đổi thêm, em gọi lại cho {h} sau ạ.")
        elif g == "refuse_discount":
            out.append("Dạ giá bên em là giá đã áp ưu đãi tốt nhất hiện có, em không giảm thêm được ạ.")
        elif g == "refuse_internal":
            out.append("Dạ thông tin giá nhập là thông tin nội bộ, em không cung cấp được ạ.")
        elif g == "no_competitor_comment":
            out.append("Dạ em không so sánh được giá bên khác, giá bên em là giá chính hãng ạ.")
        elif g == "policy_answer":
            sn = F.get("policy") or []
            out.append("Dạ theo chính sách bên em: " + sn[0]["text"].split("\n")[0][:220] if sn else "Dạ em chưa có thông tin về vấn đề này ạ.")
        elif g == "no_info":
            out.append("Dạ về vấn đề này em chưa có thông tin, em ghi nhận và kiểm tra lại rồi báo mình ạ.")
        elif g == "handoff":
            out.append(f"Dạ câu này em xin phép chuyển {h} sang chuyên viên để tư vấn chính xác, em đã gửi đầy đủ thông tin để {h} không phải nói lại ạ.")
        elif g == "is_bot":
            out.append("Dạ em là trợ lý AI của shop ạ, nếu cần em có thể chuyển mình sang nhân viên.")
        elif g == "data_deleted":
            out.append(f"Dạ em đã ghi nhận yêu cầu xóa dữ liệu của {h} ạ.")
        elif g == "closing":
            out.append(f"Dạ em cảm ơn {h} ạ.")
    return " ".join(out) or f"Dạ vâng ạ."
