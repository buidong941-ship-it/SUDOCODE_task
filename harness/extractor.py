"""Extractor: trích có cấu trúc từ lời KHÁCH (slot → bộ nhớ) và từ lời AGENT (questions[], claims[], facts_used → trace).

Toàn bộ là luật/regex: rẻ, tái lập được, và mô tả được trong báo cáo (BTC chấm tay extractor — không được "ăn gian").
Quy ước claims: chỉ ghi dữ kiện agent KHẲNG ĐỊNH và đối chiếu được (giá, KM, tồn kho, ngày giao, bảo hành, đổi trả).
"""
import re

from harness.textnorm import find_money, fold, parse_relative_datetime

# ----------------------------------------------------------------------------- lời khách → slot
BLOCKERS = [(r"(hoi|ban voi) (chong|ong xa|anh nha|bo no)", "can hoi chong"), (r"(hoi|ban voi) (vo|ba xa|chi nha|me no)", "can hoi vo"),
            (r"hoi (con|nguoi nha|gia dinh|bo me|me)", "can hoi nguoi nha"), (r"(so sanh|so gia|tham khao) (gia|them)", "so sanh gia"),
            (r"(can nhac|suy nghi|xem them|tim hieu them)", "can nhac")]
ADDRESS_RX = re.compile(r"(?:giao (?:về|tới|đến|cho \w+ (?:về|tới|ở))|địa chỉ(?: mới| giao)?(?: là|:)?|(?:giờ|hiện|nhà) (?:chị|anh|em|cô|chú)? ?ở|chuyển (?:nhà|về) (?:ra|vào|về|tới)?)\s+"
                        r"((?:số |ngõ |hẻm |\d)[^.!?]*?)(?=\s+(?:nhé|nha|nhá|ạ|em|giúp|luôn|trong tuần|thanh toán)\b|[.!?]|$)", re.I)


def customer_slots(text, today):
    """Slot khách nói trong câu này (chưa so với bộ nhớ). Giá trị đã chuẩn hóa."""
    t, f = text.lower(), fold(text)
    out = {}
    m = re.search(r"(\d{1,3})\s*(?:m2|m²|mét vuông|mét|m\b)", t)
    if m: out["room_area_m2"] = int(m.group(1))
    if re.search(r"\b(be|con nho|em be|tre nho|tre con|chau nho|bé)\b", f) and not re.search(r"khong co (be|con)", f):
        out["has_children"] = True
    for s, e, v in find_money(text):
        ctx = fold(text[max(0, s - 30):e + 15])
        if re.search(r"ben (kia|khac)|shopee|lazada|cho khac|tiki", ctx): out["competitor_price_vnd"] = v
        elif re.search(r"(bao|noi|bao gia|thay|giam xong|con)\b", ctx) and not re.search(r"ngan sach", ctx):
            out.setdefault("claimed_prices", []).append(v)
        elif re.search(r"ngan sach|tam|khoang|toi da|duoi|co (tam|khoang)", ctx): out["budget_vnd"] = v
    m = re.search(r"(?:size|cỡ|số)\s*(\d{2}|xs|s|m|l|xl|xxl)\b", t)
    if m: out["size"] = m.group(1).upper()
    from harness.tools import COLORS
    for code, words in COLORS.items():
        if any(re.search(r"\bmau " + re.escape(fold(w)) + r"\b", f) for w in words):
            out["color"] = code
    m = ADDRESS_RX.search(text)
    if m and not re.search(r"địa chỉ cũ|như cũ", t):
        out["address"] = m.group(1).strip(" ,")
    if re.search(r"\bcod\b|thanh toan khi nhan|tien mat|nhan hang (roi )?tra", f): out["payment"] = "COD"
    elif re.search(r"chuyen khoan|ck truoc|qua ngan hang|momo|zalopay", f): out["payment"] = "bank"
    for rx, label in BLOCKERS:
        if re.search(rx, f):
            out["blocker"] = label; break
    w = parse_relative_datetime(text, today)
    if w and re.search(r"goi lai|lien lac|bao lai|goi cho", f):
        out["callback_requested"] = f"{w[0]}T{w[1] or '09:00'}"
    m = re.search(r"(?:chị|anh|cô|chú|em|tôi|mình) (?:là|tên là|tên) ([A-ZĐ][a-zà-ỹ]+)", text)
    if m: out["self_name"] = m.group(1)
    return out


# ----------------------------------------------------------------------------- lời agent → questions[]
SLOT_KW = [
    ("room_area_m2", r"(m2|m²|met vuong|dien tich|phong .*(rong|bao nhieu))"),
    ("budget_vnd", r"(ngan sach|tam gia|du dinh chi|muc gia)"),
    ("has_children", r"(be|tre nho|em be|con nho)"),
    ("size", r"(size|co chan|co ao|mang so)"),
    ("color", r"\bmau (gi|nao|den|trang|xam|navy|be|do)|chon mau"),
    ("address", r"(dia chi|giao (ve|toi) dau|o dau a)"),
    ("payment", r"(thanh toan|cod|chuyen khoan)"),
    ("customer_name", r"(ten (gi|la gi)|xung ho|goi .* the nao)"),
    ("phone", r"(so dien thoai|sdt)"),
    ("blocker", r"(bang khoan|trao doi|anh nha|chi nha|ong xa|ba xa|nguoi nha|da hoi|y kien)"),
    ("callback_time", r"(goi lai .*(luc|khi) nao|may gio|gio nao|hen .* (luc|ngay))"),
    ("product_advised", r"(san pham nao|mau nao|quan tam (den )?(gi|san pham)|tim (mau|san pham)|loai nao)"),
    ("order_id", r"ma don"),
    ("confirm_order", r"(len don|chot don|dat hang)"),
]
CONFIRM_RX = re.compile(r"(dung khong|phai khong|dung a|van (lay|giu|la|o|dung)|\bnhi\b|chu a\b|nhu cu|hay (la )?(van|doi)|xac nhan|co phai)")


def _sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def agent_questions(text, known_values):
    """known_values: {slot: value} đã biết — câu hỏi có chứa giá trị đã biết → câu xác nhận."""
    out = []
    for s in _sentences(text):
        if not s.endswith("?"):
            continue
        f = fold(s)
        slot = next((name for name, rx in SLOT_KW if re.search(rx, f)), None)
        if slot is None:
            from harness.tools import find_products
            slot = "product_advised" if find_products(s) else "other"
        has_known = slot in known_values and str(known_values[slot]).lower() in s.lower()
        qtype = "confirm" if has_known or CONFIRM_RX.search(f) else "open"
        out.append({"slot": slot, "type": qtype, "text": s})
    return out


# ----------------------------------------------------------------------------- lời agent → claims[]
def agent_claims(text, quote=None, focus_sku=None):
    """Giá: số tiền trong câu có ngữ cảnh 'giá/còn/chỉ/tổng' (không phải ngân sách/phí ship/giảm).
    KM: khẳng định đang có / đã hết. Tồn kho: còn hàng / hết hàng. Giao hàng: 'x(-y) ngày'."""
    claims = []
    for s in _sentences(text):
        f = fold(s)
        for st, en, v in find_money(s):
            ctx = fold(s[max(0, st - 40):st])
            after = fold(s[en:en + 20])
            if re.search(r"(ngan sach|giam|tiet kiem|phi|ship|phu thu|chenh lech|hoan|ben kia|ben khac|tren|duoi|toi da|han muc)", ctx[-25:]):
                continue
            if re.search(r"(gia|con|chi|tong|thanh tien|la|ban|niem yet)", ctx) or re.search(r"^\s*(a|thoi|nhe)", after):
                field = "list_price_vnd" if re.search(r"niem yet|gia goc", ctx) else "price_vnd"
                if re.search(r"(hom truoc|lan truoc|hom \d|truoc day|da bao|da tu van|co tu van)", f):
                    field = "price_quoted_vnd"            # nhắc lại giá đã báo trong quá khứ, không phải khẳng định giá hiện tại
                claims.append({"field": field, "value": v, "text": s})
        if re.search(r"(het han|da ket thuc|khong con ap dung|het chuong trinh|het khuyen mai)", f):
            claims.append({"field": "promo_active", "value": False, "text": s})
        elif re.search(r"(dang co|van con|dang ap dung|duoc tang|co khuyen mai|uu dai|tang kem|giam con)", f) and re.search(r"(khuyen mai|uu dai|tang|giam)", f):
            claims.append({"field": "promo_active", "value": True, "text": s})
        if re.search(r"(tam het|het hang|het mat|chua co hang)", f):
            claims.append({"field": "in_stock", "value": False, "text": s})
        elif re.search(r"(con hang|co san|san hang)", f):
            claims.append({"field": "in_stock", "value": True, "text": s})
        m = re.search(r"giao[^.?!]*?(\d+)(?:\s*(?:-|den|toi)\s*(\d+))?\s*ngay", f)
        if m:
            claims.append({"field": "delivery_days", "value": int(m.group(2) or m.group(1)), "text": s})
        m = re.search(r"bao hanh[^.?!]*?(\d+)\s*(thang|nam)", f)
        if m:
            claims.append({"field": "warranty_months", "value": int(m.group(1)) * (12 if m.group(2) == "nam" else 1), "text": s})
        m = re.search(r"doi tra[^.?!]*?(\d+)\s*ngay|trong (?:vong )?(\d+) ngay", f)
        if m and re.search(r"doi|tra", f):
            claims.append({"field": "return_days", "value": int(m.group(1) or m.group(2)), "text": s})
    return claims


# ----------------------------------------------------------------------------- facts_used (CCR)
def facts_used(text, tool_args_list, carried):
    """carried: {slot: value} nạp từ phiên trước. Fact được tính 'dùng' khi giá trị xuất hiện trong lời agent hoặc tham số tool."""
    used, low = [], text.lower()
    f = fold(text)
    args_blob = " ".join(str(v).lower() for a in tool_args_list for v in a.values())
    for slot, val in carried.items():
        if val in (None, "", [], {}):
            continue
        hit = False
        if isinstance(val, bool):
            hit = slot == "has_children" and bool(re.search(r"\b(be|tre nho|con nho|em be)\b", f))
        elif isinstance(val, int):
            hit = any(v == val for _, _, v in find_money(text)) or bool(re.search(rf"\b{val}\s*(m2|m²|mét|m\b)", low)) or str(val) in args_blob
        else:
            sval = str(val).lower()
            if slot == "blocker":
                hit = bool(re.search(r"(anh nha|chi nha|ong xa|ba xa|nguoi nha|trao doi|hoi y kien|so sanh|can nhac)", f))
            elif slot == "product_advised":
                from harness.tools import product_name
                hit = sval in args_blob or fold(product_name(val)).split()[-1] in f.split() and fold(product_name(val)).split()[-2] in f
            else:
                hit = sval in low or sval in args_blob or fold(sval) in f
        if hit:
            used.append(slot)
    return used
