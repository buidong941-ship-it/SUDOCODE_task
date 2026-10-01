"""Perceive: chuẩn hóa lời khách tiếng Việt trước khi vào harness.

- teencode / không dấu / viết tắt → câu chuẩn (đủ để rule và LLM hiểu)
- ITN: "năm triệu rưỡi" → 5500000, "5tr2" → 5200000, "690k" → 690000, "không chín tám…" → SĐT
- ngày tương đối: "thứ hai tuần sau", "mai", "ngày kia" → YYYY-MM-DD (tính từ ngày của cuộc gọi)
- mask PII (CCCD 12 số, STK 9–14 số) trước khi ghi log / gửi model ngoài
"""
import re
import unicodedata
from datetime import date, timedelta

# ----------------------------------------------------------------------------- tiện ích chung
def strip_accents(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def fold(s):
    """Dạng so khớp: thường, bỏ dấu, gộp khoảng trắng."""
    return re.sub(r"\s+", " ", strip_accents((s or "").lower())).strip()


# ----------------------------------------------------------------------------- teencode
TEEN = [
    (r"\bk\b|\bko\b|\bkhong\b|\bkg\b", "không"), (r"\br\b", "rồi"), (r"\bdc\b|\bđc\b|\bduoc\b", "được"),
    (r"\bbn\b|\bbao nhieu\b", "bao nhiêu"), (r"\bsp\b", "sản phẩm"), (r"\bv\b", "vậy"), (r"\bj\b", "gì"),
    (r"\bmk\b|\bmik\b", "mình"), (r"\bbik\b|\bbiet\b", "biết"), (r"\bok\b|\boke\b|\bokie\b", "ok"),
    (r"\bz\b", "thế"), (r"\bnhe\b", "nhé"), (r"\bship cod\b", "ship COD"), (r"\blen don\b", "lên đơn"),
    (r"\bvo\b", "vợ"), (r"\bchong\b", "chồng"), (r"\bgia\b", "giá"), (r"\bhom truoc\b", "hôm trước"),
    (r"\bdia chi\b", "địa chỉ"), (r"\bdoi\b", "đổi"),
]


def normalize_teencode(text):
    s = " " + text + " "
    for a, b in TEEN:
        s = re.sub(a, b, s, flags=re.I)
    return re.sub(r"\s+", " ", s).strip()


# ----------------------------------------------------------------------------- số tiếng Việt → int
DIGIT = {"không": 0, "linh": 0, "lẻ": 0, "một": 1, "mốt": 1, "hai": 2, "ba": 3, "bốn": 4, "tư": 4, "năm": 5, "lăm": 5,
         "nhăm": 5, "sáu": 6, "bảy": 7, "bẩy": 7, "tám": 8, "chín": 9}
SCALE = {"mươi": 10, "mười": 10, "trăm": 100, "nghìn": 1000, "ngàn": 1000, "triệu": 1_000_000, "tỷ": 1_000_000_000, "tỉ": 1_000_000_000}
_NUM_WORD = r"(?:không|linh|lẻ|một|mốt|hai|ba|bốn|tư|năm|lăm|nhăm|sáu|bảy|bẩy|tám|chín|mươi|mười|trăm|nghìn|ngàn|triệu|tỷ|tỉ|rưỡi)"


def words_to_int(words):
    """'bốn triệu tám trăm chín mươi nghìn' → 4890000; 'năm triệu rưỡi' → 5500000; 'năm triệu hai' → 5200000."""
    total, small, cur, scale = 0, 0, 0, None   # small: phần < 1000 đang gom; cur: chữ số chờ
    prev, tail = None, []                       # tail: token sau đơn vị lớn cuối cùng (để xử lý đọc tắt)
    for w in words.split():
        if w in ("linh", "lẻ"):
            pass
        elif w == "mười":
            small += 10
        elif w == "mươi":
            small += (cur or 1) * 10; cur = 0
        elif w == "trăm":
            small += (cur or 1) * 100; cur = 0
        elif w in ("nghìn", "ngàn", "triệu", "tỷ", "tỉ"):
            total += ((small + cur) or 1) * SCALE[w]; small = cur = 0; scale = SCALE[w]; tail = []; prev = w; continue
        elif w == "rưỡi":
            if scale: total += scale // 2
        elif w in DIGIT:
            if prev in ("mươi", "mười"): small += DIGIT[w]
            else: cur = DIGIT[w]
        tail.append(w); prev = w
    rest = small + cur
    # đọc tắt sau "triệu"/"nghìn": "năm triệu hai" = 5.200.000, "bốn triệu tám trăm chín" = 4.890.000
    if rest and scale and scale >= 1000 and "nghìn" not in tail and "ngàn" not in tail:
        unit = scale // 1000
        if len(tail) == 1 and tail[0] in DIGIT:
            return total + DIGIT[tail[0]] * unit * 100
        if len(tail) >= 2 and tail[-2] == "trăm" and tail[-1] in DIGIT:
            return total + (small + cur * 10) * unit
        if scale >= 1_000_000:
            return total + rest * unit
    return total + rest


def _num_from_compact(s):
    """'5tr2' → 5200000, '5 triệu 2' → 5200000, '4tr890' → 4890000, '690k' → 690000, '4.890.000' → 4890000."""
    s = s.lower().replace(" ", "")
    m = re.fullmatch(r"(\d+)(?:tr|triệu|trieu)(\d{1,3})?", s)
    if m:
        a, b = int(m.group(1)), m.group(2)
        if not b: return a * 1_000_000
        return a * 1_000_000 + int(b) * (100_000 if len(b) == 1 else 10_000 if len(b) == 2 else 1000)
    m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(k|nghìn|ngàn|nghin)", s)
    if m: return int(float(m.group(1).replace(",", ".")) * 1000)
    m = re.fullmatch(r"\d{1,3}(?:[.,]\d{3})+(?:đ|d|vnd)?", s)
    if m: return int(re.sub(r"\D", "", s))
    return None


MONEY_RX = re.compile(
    r"\d{1,3}(?:[.,]\d{3})+\s*(?:đ|vnđ|vnd|đồng)?"
    r"|\d+\s*(?:triệu|tr)\s*(?:rưỡi|\d{1,3}\b)?"
    r"|\d+(?:[.,]\d+)?\s*(?:k|nghìn|ngàn)\b"
    r"|\b\d{5,9}\s*(?:đ|vnđ|vnd|đồng)", re.I)
MONEY_WORDS_RX = re.compile(r"\b(?:%s)(?:\s+%s)*\b" % (_NUM_WORD, _NUM_WORD), re.I)


def find_money(text):
    """Trả [(start, end, value)] cho mọi số tiền trong câu (chữ số hoặc chữ)."""
    out = []
    for m in MONEY_RX.finditer(text):
        raw = m.group().strip()
        if "rưỡi" in raw:
            v = int(re.match(r"\d+", raw).group()) * 1_000_000 + 500_000
        else:
            v = _num_from_compact(re.sub(r"\s*(đ|vnđ|vnd|đồng)$", "", raw, flags=re.I))
            if v is None and re.fullmatch(r"\d{5,9}\s*(đ|vnđ|vnd|đồng)", raw, re.I):
                v = int(re.sub(r"\D", "", raw))
        if v and v >= 1000:
            out.append((m.start(), m.end(), v))
    for m in MONEY_WORDS_RX.finditer(text.lower()):
        w = m.group()
        if not re.search(r"triệu|nghìn|ngàn|trăm|tỷ|tỉ", w):
            continue
        if any(s <= m.start() < e for s, e, _ in out):
            continue
        v = words_to_int(w)
        if v >= 10_000:
            out.append((m.start(), m.end(), v))
    return sorted(out)


# ----------------------------------------------------------------------------- SĐT đọc bằng chữ
_DIG1 = {"không": "0", "một": "1", "hai": "2", "ba": "3", "bốn": "4", "năm": "5", "sáu": "6", "bảy": "7", "tám": "8", "chín": "9"}


def find_phone(text):
    m = re.search(r"\b0\d{9}\b", re.sub(r"(?<=\d)[ .-](?=\d)", "", text))
    if m: return m.group()
    seq = "".join(_DIG1.get(w, " ") for w in text.lower().split())
    m = re.search(r"0\d{9}", seq.replace(" ", ""))
    return m.group() if m else None


# ----------------------------------------------------------------------------- ngày tương đối
WEEKDAY = {"thứ hai": 0, "thứ 2": 0, "thứ ba": 1, "thứ 3": 1, "thứ tư": 2, "thứ 4": 2, "thứ năm": 3, "thứ 5": 3,
           "thứ sáu": 4, "thứ 6": 4, "thứ bảy": 5, "thứ 7": 5, "chủ nhật": 6}


def parse_relative_datetime(text, today):
    """Trả (YYYY-MM-DD, HH:MM | None) hoặc None. today: 'YYYY-MM-DD' của cuộc gọi."""
    t = text.lower(); d0 = date.fromisoformat(today); day = None
    if re.search(r"\bngày kia\b|\bngày mốt\b", t): day = d0 + timedelta(days=2)
    elif re.search(r"\bmai\b|\bngày mai\b", t): day = d0 + timedelta(days=1)
    elif re.search(r"\bhôm nay\b|\bchiều nay\b|\btối nay\b|\bsáng nay\b", t): day = d0
    for k, wd in WEEKDAY.items():
        if k in t:
            delta = (wd - d0.weekday()) % 7
            if "tuần sau" in t or "tuần tới" in t:
                delta = (7 - d0.weekday()) + wd
            elif delta == 0:
                delta = 7
            day = d0 + timedelta(days=delta)
            break
    m = re.search(r"(\d{1,2})[/-](\d{1,2})", t)
    if m and not day:
        try: day = date(d0.year, int(m.group(2)), int(m.group(1)))
        except ValueError: pass
    if not day:
        return None
    hour = None
    m = re.search(r"(\d{1,2})\s*(?:giờ|h|g)(?:\s*(\d{2}))?", t)
    if m:
        h = int(m.group(1))
        if ("chiều" in t or "tối" in t) and h < 12: h += 12
        hour = f"{h:02d}:{int(m.group(2) or 0):02d}"
    elif "chiều" in t: hour = "15:00"
    elif "sáng" in t: hour = "09:00"
    elif "tối" in t: hour = "19:00"
    return day.isoformat(), hour


# ----------------------------------------------------------------------------- PII
CCCD_RX = re.compile(r"\b0\d{11}\b")
BANK_RX = re.compile(r"\b\d{9,14}\b")
PHONE_RX = re.compile(r"\b0\d{9}\b")


def mask_pii(text):
    """CCCD/STK → giữ 4 số cuối. SĐT 10 số (bắt đầu 0) giữ nguyên vì nghiệp vụ cần, và log đã tách khỏi PII vault."""
    text = CCCD_RX.sub(lambda m: m.group()[:2] + "*" * 6 + m.group()[-4:], text)
    return BANK_RX.sub(lambda m: m.group() if PHONE_RX.fullmatch(m.group()) else "*" * (len(m.group()) - 4) + m.group()[-4:], text)


def perceive(raw, today):
    """Đầu vào thô → dict có văn bản chuẩn hóa, đã mask, cùng các thực thể số."""
    norm = normalize_teencode(raw)
    masked = mask_pii(norm)
    return {"raw": raw, "text": masked, "money": [v for _, _, v in find_money(masked)],
            "phone": find_phone(norm), "when": parse_relative_datetime(norm, today),
            "pii_found": masked != norm}
