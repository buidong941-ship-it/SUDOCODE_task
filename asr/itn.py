"""Chuẩn hóa số cho đầu ra ASR tiếng Việt.

- `itn(text)`  (Inverse Text Normalization, chữ → ký hiệu): "bốn triệu tám trăm chín mươi nghìn" → "4.890.000",
  "hai trăm bốn chín k" → "249.000", "không chín một bảy hai hai ba bốn năm sáu" → "0917223456",
  "ngày hai mươi hai tháng mười" → "ngày 22/10", "ô đê ba trăm mười hai nghìn…" → "OD312456", "cê ô đê" → "COD".
- `to_spoken(text)` (chiều ngược, ký hiệu → chữ): đưa transcript về CÙNG dạng với asr/ground_truth.json (số viết
  bằng chữ như lời nói) trước khi tính WER/CER — theo `normalization_rule` của BTC. Nhóm chọn dạng chữ.
- `entities(units, ref_date)`: trích thực thể (giá, SĐT, mã đơn, diện tích, size, ngày hết KM…) từ các đoạn transcript
  sau ITN; giá trị nhắc sau ghi đè giá trị trước (giống cách BTC gộp `entities` cấp hội thoại).
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from harness.textnorm import DIGIT, SCALE, _num_from_compact, words_to_int  # noqa: E402

DIGIT_ONLY = {"không": "0", "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5", "sáu": "6", "bảy": "7",
              "bẩy": "7", "tám": "8", "chín": "9"}
NUM_WORDS = set(DIGIT) | set(SCALE) | {"rưỡi"}
BIG = {"nghìn", "ngàn", "triệu", "tỷ", "tỉ"}


# ----------------------------------------------------------------------------------------------- chữ → số
def _groups(run):
    """Tách một dãy từ số liền nhau thành các con số riêng: "ba năm" = [3] + chữ "năm" (năm = year),
    "hai trăm bốn chín" = 249 (đọc tắt hàng chục sau "trăm"), "mười lăm hai mươi" = [15, 20]."""
    out, cur = [], []
    i = 0
    while i < len(run):
        w = run[i]
        if cur and w in DIGIT and cur[-1] in DIGIT and cur[-1] not in ("linh", "lẻ"):
            if len(cur) >= 2 and cur[-2] == "trăm" and (len(cur) < 3 or cur[-3] in DIGIT):
                cur = cur[:-1] + [cur[-1], "mươi", w]            # "trăm bốn chín" → "trăm bốn mươi chín"
                i += 1
                continue
            out.append(cur); cur = []
            if w == "năm" and i == len(run) - 1:                 # "bảo hành ba năm" → năm là đơn vị thời gian
                out.append(["năm"]); i += 1
                continue
        cur.append(w); i += 1
    if cur:
        out.append(cur)
    return out


def _fmt(n, words):
    return f"{n:,}".replace(",", ".") if (n >= 10_000 or any(w in BIG for w in words)) else str(n)


def itn(text):
    toks = re.split(r"(\s+|[,.;:!?()\"])", text)
    words = [(i, t) for i, t in enumerate(toks) if t and not re.fullmatch(r"\s+|[,.;:!?()\"]", t)]
    out = list(toks)
    j = 0
    while j < len(words):
        k = j
        while k < len(words) and words[k][1].lower() in NUM_WORDS and (
                k == j or all(not toks[x].strip() for x in range(words[k - 1][0] + 1, words[k][0]))):   # chỉ cách nhau dấu cách
            k += 1
        if k == j:
            j += 1
            continue
        run = [w.lower() for _, w in words[j:k]]
        if len(run) >= 9 and all(w in DIGIT_ONLY for w in run) and run[0] == "không":     # SĐT đọc từng số
            rep = ["".join(DIGIT_ONLY[w] for w in run)]
        else:
            rep = []
            for g in _groups(run):
                if (g == ["năm"] and rep) or g == ["không"]:       # "ba năm" (đơn vị) / "đúng không" (phủ định)
                    rep.append(g[0])
                elif all(w in SCALE or w in ("linh", "lẻ", "rưỡi") for w in g):
                    rep.append(" ".join(g))                               # "mười"/"nghìn" đứng một mình vẫn là số
                    if g in (["mười"],):
                        rep[-1] = "10"
                else:
                    rep.append(_fmt(words_to_int(" ".join(g)), g))
        first, last = words[j][0], words[k - 1][0]
        out[first] = " ".join(rep)
        for x in range(first + 1, last + 1):
            out[x] = ""
        j = k
    s = "".join(out)
    s = re.sub(r"(\d[\d.]*)\s*(?:k|nghìn|ngàn)\b", lambda m: _fmt(int(m.group(1).replace(".", "")) * 1000, ["nghìn"]), s)
    s = re.sub(r"(\d[\d.]*)\s*củ\b", lambda m: _fmt(int(m.group(1).replace(".", "")) * 1_000_000, ["triệu"]), s)
    s = re.sub(r"\b(?:ô|o)\s*đê\s*(\d[\d.]{4,})", lambda m: "OD" + m.group(1).replace(".", ""), s, flags=re.I)
    s = re.sub(r"\bcê\s*ô\s*đê\b", "COD", s, flags=re.I)
    s = re.sub(r"\bngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\b", r"ngày \1/\2", s)
    s = re.sub(r"(\d+)\s*mét vuông\b", r"\1 m2", s)
    return s


# ----------------------------------------------------------------------------------------------- số → chữ
_U = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]


def _read3(n, full):
    h, t, u = n // 100, n // 10 % 10, n % 10
    out = []
    if h or full:
        out += [_U[h], "trăm"]
    if t == 0:
        if u:
            out += (["linh"] if (h or full) else []) + [_U[u]]
    elif t == 1:
        out += ["mười"] + ([{5: "lăm"}.get(u, _U[u])] if u else [])
    else:
        out += [_U[t], "mươi"] + ([{1: "mốt", 5: "lăm"}.get(u, _U[u])] if u else [])
    return out


def int_to_words(n):
    """5200000 → "năm triệu hai trăm nghìn"; 2026 → "hai nghìn không trăm hai mươi sáu"; 105 → "một trăm linh năm"."""
    if n == 0:
        return "không"
    parts, scales, i = [], ["", "nghìn", "triệu", "tỷ"], 0
    groups = []
    while n:
        groups.append(n % 1000); n //= 1000
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0:
            continue
        parts += _read3(g, full=i < len(groups) - 1) + ([scales[i]] if scales[i] else [])
    return " ".join(parts)


def to_spoken(text):
    s = re.sub(r"\bCOD\b", "cê ô đê", text, flags=re.I)
    s = re.sub(r"\bOD\s?(\d+)", lambda m: "ô đê " + int_to_words(int(m.group(1))), s, flags=re.I)
    s = re.sub(r"(?<!\d)(0\d{9})(?!\d)", lambda m: " ".join(_U[int(c)] for c in m.group(1)), s)          # SĐT
    s = re.sub(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{4}))?\b",
               lambda m: f"{int_to_words(int(m.group(1)))} tháng {int_to_words(int(m.group(2)))}"
                         + (f" năm {int_to_words(int(m.group(3)))}" if m.group(3) else ""), s)
    s = re.sub(r"\b\d+\s*tr\d{1,3}\b|\b\d+(?:[.,]\d+)?k\b", lambda m: int_to_words(_num_from_compact(m.group())), s)  # 5tr7, 249k
    s = re.sub(r"(\d+(?:[.,]\d+)?)\s*(tr|triệu)\b", lambda m: _decimal_words(m.group(1), 1_000_000), s)
    s = re.sub(r"(\d+)\s*k\b", lambda m: int_to_words(int(m.group(1)) * 1000), s)
    s = re.sub(r"(\d+)\s*(?:m2|m²)", lambda m: int_to_words(int(m.group(1))) + " mét vuông", s)
    s = re.sub(r"\d{1,3}(?:\.\d{3})+|\d+", lambda m: int_to_words(int(m.group().replace(".", ""))), s)
    return re.sub(r"\s*(?:đ|vnđ|đồng)\b", "", s)


def _decimal_words(num, unit):
    if "," in num or "." in num:
        return int_to_words(int(round(float(num.replace(",", ".")) * unit)))
    return int_to_words(int(num) * unit)


# ----------------------------------------------------------------------------------------------- thực thể
def entities(units, ref_date):
    """units: các đoạn transcript (mỗi lượt / mỗi segment ASR) theo thứ tự thời gian → {tên: giá trị}."""
    from harness.extractor import BLOCKERS, customer_slots
    from harness.textnorm import fold
    from harness.tools import find_products, mt
    SKUS = {p["sku"] for p in mt.PRODUCTS}
    year = ref_date[:4]
    ent, compared = {}, False
    for raw in units:
        t = itn(raw)
        low, f = t.lower(), fold(t)
        prods = find_products(raw) or find_products(t)
        if prods:
            ent["sku"] = prods[-1]
        elif ent.get("sku"):                       # "mẫu x" sau khi đã nói "e pia y" → cùng dòng, đổi đuôi
            m = re.search(r"\bmẫu\s+([a-z0-9]{1,4})\b", low)
            if m:
                cand = re.sub(r"-[A-Z0-9]+$", "-" + m.group(1).upper(), ent["sku"])
                if cand in SKUS:
                    ent["sku"] = cand
        m = re.search(r"(?<!\d)(0\d{9})(?!\d)", t)
        if m:
            ent["phone"] = m.group(1)
        m = re.search(r"\bOD(\d{6})\b", t)
        if m:
            ent["order_id"] = "OD" + m.group(1)
        m = re.search(r"(\d+)\s*(?:m2|mét)\b", low)
        if m:
            ent["room_area_m2"] = int(m.group(1))
        m = re.search(r"(?:đến|hết)\s+(?:hết\s+)?ngày\s+(\d{1,2})/(\d{1,2})", low)
        if m:
            ent["promo_expiry"] = f"{year}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
        m = re.search(r"bảo hành\s+(\d+)\s*(tháng|năm)", low)
        if m:
            ent["warranty_months"] = int(m.group(1)) * (12 if m.group(2) == "năm" else 1)
        m = re.search(r"đổi trả\s+(?:trong\s+)?(\d+)\s*ngày", low)
        if m:
            ent["return_days"] = int(m.group(1))
        m = re.search(r"(\d+)\s*(?:đến|-)\s*(\d+)\s*ngày", low)
        if m and "giao" in low:
            ent["delivery_days"] = int(m.group(2))
        sizes = re.findall(r"size\s+(\d{2})", low)
        m = re.search(r"đổi\s+(?:lên|sang|qua)\s+(?:size\s+)?(\d{2})", low)
        if m:
            ent["size_new"] = int(m.group(1))
        elif sizes and "size_old" not in ent:
            ent["size_old"] = int(sizes[0])
        if re.search(r"còn hàng", low):
            ent["in_stock"] = True
        elif re.search(r"hết hàng", low):
            ent["in_stock"] = False
        if re.search(r"đổi size.*miễn phí|miễn phí.*đổi", low):
            ent["exchange_fee_vnd"] = 0
        # tiền: phân loại theo ngữ cảnh trong đoạn
        for val_s, clause, ctx in _money_with_context(t):
            v = int(val_s.replace(".", ""))
            ent[_money_kind(clause) or _money_kind(ctx) or "price_vnd"] = v
        slots = customer_slots(raw, ref_date)
        for k in ("has_children", "payment", "color"):
            if k in slots:
                ent[k] = slots[k]
        if "COD" in t or "khi nhận hàng" in low:
            ent["payment"] = "COD"
        for rx, label in BLOCKERS:
            if re.search(rx, f):
                ent["blocker"] = label
        if re.search(r"so sanh|ben kia|ben khac|dat hon", f):
            compared = True
        if compared and re.search(r"can nhac|bao lai|suy nghi", f):     # chần chừ SAU khi đã so giá
            ent["blocker"] = "so sanh gia"
    return ent


def _money_kind(ctx):
    for rx, kind in ((r"bên kia|bên khác|chỗ khác|shop khác|đối thủ", "competitor_price_vnd"),
                     (r"ngân sách|tầm .*thôi|khoảng .*thôi", "budget_vnd"),
                     (r"phụ thu|cồng kềnh", "bulky_fee_vnd"),
                     (r"đơn từ|miễn phí vận chuyển|freeship", "min_free_ship_vnd")):
        if re.search(rx, ctx):
            return kind
    return None


def _money_with_context(t):
    """[(số, mệnh đề chứa số, mệnh đề + 60 ký tự trước)] cho các số viết dạng 5.200.000 (mệnh đề cắt theo dấu phẩy)."""
    out = []
    for clause in re.split(r"[,;.!?](?!\d)", t):
        for m in re.finditer(r"(?<![\d.])(\d{1,3}(?:\.\d{3})+)(?![\d.])", clause):
            if not re.search(r"\bOD$", clause[:m.start()].strip()):
                out.append((m.group(1), clause.lower(), (t[:t.find(clause)][-60:] + clause).lower()))
    return out
