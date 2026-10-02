"""Che PII trước khi dữ liệu rời hệ thống (LLM ngoài) hoặc vào file log.

- `Redactor`: thay SĐT / địa chỉ bằng mã ([SĐT_1], [ĐỊA_CHỈ_1]) trước khi gửi DeepSeek/Jev, rồi `restore()` câu trả lời
  về giá trị thật. Nghiệp vụ vẫn dùng được (đơn hàng, hẹn gọi lại cần SĐT thật) mà model ngoài không thấy.
  CCCD / số tài khoản đã được che từ lúc nhận câu nói (`harness.textnorm.mask_pii`) và không bao giờ khôi phục.
- `mask_for_log()`: che một chiều cho dòng log (098****714, [địa chỉ]).
"""
import re

PHONE_RX = re.compile(r"(?<![\d*])(?:\+84|84|0)(?:[\s.-]?\d){9}(?![\d*])")
# địa chỉ trong câu nói: "số 12 ngõ 34 Láng Hạ, Đống Đa" / "12/3 đường Lê Lợi, quận 1" / "hẻm 45 …"
ADDRESS_RX = re.compile(
    r"(?:\b(?:số|sn)\s*)?\b\d+[\w/]*\s*,?\s*(?:đường|phố|ngõ|ngách|hẻm|kiệt|khu phố|thôn|ấp)\s+[^,.;!?\n]+"
    r"(?:\s*,\s*(?:(?:phường|p\.?|xã|thị trấn|quận|q\.?|huyện|thị xã|tp\.?|thành phố|tỉnh)\s*)?[^,.;!?\n]+){0,4}", re.I)
# không có từ khóa: "63 Phan Xích Long, Phú Nhuận, TP HCM" — số nhà + tên viết hoa + ≥ 2 đoạn ", Viết Hoa"
# (đòi 2 đoạn để không nhầm "Smart 4 Pro, Giá 5.490.000đ")
_UP = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
_CAPWORD = r"[%s][^\s,.;!?]*" % _UP
PLAIN_ADDRESS_RX = re.compile(r"\b\d{1,4}[A-Za-z]?(?:/\d+)*\s+%s(?:\s+(?:%s|\d+))*(?:\s*,\s*%s(?:\s+(?:%s|-|\d+))*){2,}"
                              % (_CAPWORD, _CAPWORD, _CAPWORD, _CAPWORD))
# địa chỉ sau cụm dẫn ("giao về …", "giờ ở …", "địa chỉ là …") — cùng regex harness dùng để trích slot `address`
from harness.extractor import ADDRESS_RX as CUE_ADDRESS_RX  # noqa: E402

PHONE_KEYS = {"phone", "customer_phone", "sdt", "so_dien_thoai"}
ADDRESS_KEYS = {"address", "dia_chi", "delivery_address", "new_address", "shipping_address"}


def _digits(s):
    d = re.sub(r"\D", "", s)
    return "0" + d[2:] if d.startswith("84") and len(d) == 11 else d


class Redactor:
    def __init__(self):
        self.token_of, self.value_of, self.n = {}, {}, {"SĐT": 0, "ĐỊA_CHỈ": 0}

    def _token(self, kind, key, original):
        if key not in self.token_of:
            self.n[kind] += 1
            tok = f"[{kind}_{self.n[kind]}]"
            self.token_of[key], self.value_of[tok] = tok, original
        return self.token_of[key]

    def _collect(self, obj, key=None):
        """Giá trị nằm dưới khóa phone/address → đăng ký trước, để thay được cả khi chúng xuất hiện trong câu chữ."""
        if isinstance(obj, dict):
            for k, v in obj.items():
                self._collect(v, str(k).lower())
        elif isinstance(obj, (list, tuple)):
            for v in obj:
                self._collect(v, key)
        elif isinstance(obj, str) and obj.strip():
            if key in PHONE_KEYS and len(_digits(obj)) >= 9:
                self._token("SĐT", _digits(obj), obj)
            elif key in ADDRESS_KEYS and len(obj) >= 6:
                self._token("ĐỊA_CHỈ", obj.strip().lower(), obj.strip())

    def redact_text(self, s):
        for key, tok in sorted(self.token_of.items(), key=lambda kv: -len(kv[0])):
            if not key.isdigit():                         # địa chỉ đã biết
                s = re.sub(re.escape(key), tok, s, flags=re.I)
        s = PHONE_RX.sub(lambda m: self._token("SĐT", _digits(m.group()), m.group()), s)
        s = CUE_ADDRESS_RX.sub(lambda m: m.group()[:m.start(1) - m.start()]
                               + self._token("ĐỊA_CHỈ", m.group(1).strip().lower(), m.group(1).strip()), s)
        s = ADDRESS_RX.sub(lambda m: self._token("ĐỊA_CHỈ", m.group().strip().lower(), m.group().strip()), s)
        return PLAIN_ADDRESS_RX.sub(lambda m: self._token("ĐỊA_CHỈ", m.group().strip().lower(), m.group().strip()), s)

    def redact(self, obj):
        """Bản sao của obj (dict/list/str lồng nhau) đã che PII. Gọi trên toàn bộ dữ liệu gửi đi."""
        self._collect(obj)

        def walk(o):
            if isinstance(o, dict):
                return {k: walk(v) for k, v in o.items()}
            if isinstance(o, (list, tuple)):
                return [walk(v) for v in o]
            return self.redact_text(o) if isinstance(o, str) else o
        return walk(obj)

    def restore(self, s):
        for tok, val in self.value_of.items():
            s = s.replace(tok, val)
        return s


# trong dòng log: tham số tool `"address": "…"` và dòng bộ nhớ `address=… (call_1#turn2)`
KEYED_ADDRESS_RX = re.compile(r'(\b(?:%s)"?\s*[:=]\s*"?)([^"\n…]+?)(?=["…]|\s\(|$)' % "|".join(sorted(ADDRESS_KEYS)), re.M)


def mask_for_log(s):
    s = KEYED_ADDRESS_RX.sub(lambda m: m.group(1) + "[địa chỉ]", s)
    s = PHONE_RX.sub(lambda m: (lambda d: d[:3] + "****" + d[-3:])(_digits(m.group())), s)
    s = CUE_ADDRESS_RX.sub(lambda m: m.group()[:m.start(1) - m.start()] + "[địa chỉ]", s)
    s = ADDRESS_RX.sub("[địa chỉ]", s)
    return PLAIN_ADDRESS_RX.sub("[địa chỉ]", s)
