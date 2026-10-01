#!/usr/bin/env python3
"""
Resolver: template kịch bản (trừu tượng) → kịch bản cụ thể đúng định dạng BTC (test_set/public_sample/SAMPLE-xx.json).

Nguyên tắc: MỌI con số (giá, KM, tồn kho, ngày về hàng, ngày giao) lấy từ eval/mock_tools.py của BTC — không để LLM sinh.
Resolver tìm (khách, sản phẩm, ngày gọi, ...) thỏa các ràng buộc `require` bằng DFS có seed, rồi render phần `scenario`.

Cách dùng:
    python resolver.py                                   # sinh toàn bộ templates/*.json → out/{dev,test}/
    python resolver.py --only T05-km-het-han --instances 5
    python resolver.py --reproduce                       # chỉ sinh bản tái tạo 7 SAMPLE của BTC → out/reproduce/
    python resolver.py --seed 7 --test-ratio 0.3 --out out_seed7

Định dạng template (xem templates/*.json):
{
  "template_id": "T05-km-het-han",
  "split": "dev" | "test" | null,          # null → plan_splits(): chia theo template trong từng nhóm hard_case (xem hàm)
  "instances": 2,                          # số kịch bản cần sinh (ghi đè bằng --instances)
  "choose": {"cust": "customers()", "p": "products(category='gia-dung')", "d1": "days('2026-10-12','2026-10-20')", "gap": "range(1,5)"},
  "dates":  {"call_1": "d1", "call_2": "add(d1, gap)"},
  "no_sunday": ["call_2"],                 # call không được rơi vào CN (LN-01: CN không xử lý đổi trả); ngày nghỉ LN-02 luôn bị loại
  "let":    {"price1": "final(p.vsku, 'call_1')"},       # tính tuần tự sau khi có ngày
  "require": ["in_stock(p.vsku, 'call_1')", "price1 > 0"],
  "reproduce": {"id": "SAMPLE-05", "fix": {"cust": "customers(ids=['C023'], reuse=True)", "d1": "['2026-09-25']"}},
  "scenario": { ...định dạng BTC, chuỗi "{{expr}}" được thay bằng giá trị... }
}
- Chuỗi chỉ gồm "{{expr}}" → giá trị giữ kiểu (int/bool/list/None); chuỗi lẫn chữ → nội suy str.
- Giá trị DROP → xóa key/phần tử khỏi output.
- call_date (call_1) / days_later (call_n) và channel_identity do resolver tự điền từ `dates` và khách.
"""
import argparse, collections, copy, glob, hashlib, json, os, random, re, sys, unicodedata
from datetime import date, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
def _default_btc():
    """Gói BTC nằm ở gốc repo (../eval/mock_tools.py); giữ đường dẫn cũ ../BTC/BTC-Data-Vong1-TEAMS làm dự phòng."""
    for c in (os.path.join(HERE, ".."), os.path.join(HERE, "..", "BTC", "BTC-Data-Vong1-TEAMS")):
        if os.path.exists(os.path.join(c, "eval", "mock_tools.py")): return os.path.abspath(c)
    return os.path.abspath(os.path.join(HERE, ".."))


DEFAULT_BTC = _default_btc()


def load_btc(btc_dir):
    sys.path.insert(0, os.path.join(btc_dir, "eval"))
    import mock_tools  # noqa: E402
    return mock_tools


class Obj(dict):
    """dict truy cập bằng thuộc tính (p.sku, cust.phone)."""
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)


class Reject(Exception):
    pass


DROP = object()
SAFE_BUILTINS = {k: __builtins__[k] if isinstance(__builtins__, dict) else getattr(__builtins__, k)
                 for k in ("range", "len", "min", "max", "sum", "int", "str", "abs", "sorted", "list", "any", "all",
                           "round", "dict", "set", "tuple", "bool", "float", "enumerate", "zip", "isinstance", "next")}

# ----------------------------------------------------------------------------- dữ liệu phụ trợ
# (đường, quận/huyện, tỉnh/thành) — thành phố lớn (Hà Nội / TP HCM / Đà Nẵng) giao 2 ngày, nơi khác 4 ngày (mock_tools._eta)
STREETS = {
    "bac": [("Nguyễn Trãi", "Thanh Xuân", "Hà Nội"), ("Trần Duy Hưng", "Cầu Giấy", "Hà Nội"), ("Kim Mã", "Ba Đình", "Hà Nội"),
            ("Minh Khai", "Hai Bà Trưng", "Hà Nội"), ("Nguyễn Văn Cừ", "Long Biên", "Hà Nội"), ("Quang Trung", "Hà Đông", "Hà Nội"),
            ("Lạch Tray", "Ngô Quyền", "Hải Phòng"), ("Lê Lợi", "TP Bắc Ninh", "Bắc Ninh"), ("Trần Hưng Đạo", "TP Nam Định", "Nam Định"),
            ("Hùng Vương", "TP Việt Trì", "Phú Thọ")],
    "trung": [("Nguyễn Văn Linh", "Hải Châu", "Đà Nẵng"), ("Ngô Quyền", "Sơn Trà", "Đà Nẵng"), ("Tôn Đức Thắng", "Liên Chiểu", "Đà Nẵng"),
              ("Lê Lợi", "TP Huế", "Thừa Thiên Huế"), ("Trần Phú", "Nha Trang", "Khánh Hòa"), ("Phan Đình Phùng", "Quy Nhơn", "Bình Định"),
              ("Quang Trung", "TP Vinh", "Nghệ An"), ("Hùng Vương", "Tam Kỳ", "Quảng Nam"), ("Lê Duẩn", "Buôn Ma Thuột", "Đắk Lắk")],
    "nam": [("Nguyễn Thị Thập", "Quận 7", "TP HCM"), ("Cách Mạng Tháng 8", "Quận 3", "TP HCM"), ("Phan Xích Long", "Phú Nhuận", "TP HCM"),
            ("Quang Trung", "Gò Vấp", "TP HCM"), ("Võ Văn Ngân", "Thủ Đức", "TP HCM"), ("Lũy Bán Bích", "Tân Phú", "TP HCM"),
            ("Đại lộ Bình Dương", "Thủ Dầu Một", "Bình Dương"), ("Trần Hưng Đạo", "Ninh Kiều", "Cần Thơ"),
            ("Phạm Văn Thuận", "Biên Hòa", "Đồng Nai"), ("Ba Cu", "TP Vũng Tàu", "Bà Rịa - Vũng Tàu")],
}
NAMES = {"chị": ["Lan", "Hương", "Mai", "Ngọc", "Trang", "Linh", "Yến", "Nhung", "Phương", "Thảo", "Vy", "Hà"],
         "anh": ["Minh", "Tuấn", "Hùng", "Dũng", "Nam", "Quân", "Huy", "Long", "Sơn", "Đức", "Phúc", "Khang"],
         "cô": ["Hằng", "Liên", "Bích"], "chú": ["Bình", "Thành", "Hải"]}
COLOR_VI = {"den": "đen", "trang": "trắng", "navy": "xanh navy", "xam": "xám", "be": "be", "do": "đỏ", "xanh": "xanh"}
NAME_PREFIXES = ["Máy lọc không khí ", "Máy lọc nước ", "Nồi chiên không dầu ", "Quạt đứng ", "Quạt tháp ", "Giày chạy bộ ",
                 "Giày sneaker ", "Giày trekking ", "Áo khoác gió ", "Áo phao lông vũ ", "Máy hút sữa điện đôi ", "Xe đẩy gấp gọn ",
                 "Xe đẩy 2 chiều ", "Máy hâm sữa ", "Máy tiệt trùng sấy khô ", "Bình sữa ", "Ghế ngồi ô tô cho bé "]
SPOKEN = [("AirPure", "e pia"), ("Xiaomi", "xiao mi"), ("Samsung", "sam sung"), ("Karofi", "ca rô phi"), ("Kangaroo", "kang ga ru"),
          ("Sunhouse", "san hao"), ("Panasonic", "pa na so níc"), ("Philips", "phi líp"), ("Lock&Lock", "lóc en lóc"),
          ("RunLite", "ran lai"), ("Urban Classic", "ơ bần cla xích"), ("HikePro", "hai pờ rô"), ("Windbreak", "win brếch"),
          ("Warmly", "quom li"), ("Spectra", "spéc tra"), ("Medela", "mê đê la"), ("Joie Pact", "doi pác"), ("Combi", "com bi"),
          ("Sugocal", "su gô can"), ("Pigeon", "pi dông"), ("Chicco", "chi cô"), ("Smart", "sờ mát"), ("Lite", "lai"),
          ("Pro", "pờ rô"), ("Mini", "mi ni"), ("Tower Fan", "tao ơ phan"), ("Fatz", "phát"), ("Moaz Bebe", "mo a bê bê"),
          ("PPSU", "pê pê ét u"), ("HEPA", "hê pa"), ("RO", "rô"), ("UF", "u ép"), ("DC", "đê xê")]
TEEN = [(r"\bkhông\b", "k"), (r"\brồi\b", "r"), (r"\bđược\b", "dc"), (r"\bbao nhiêu\b", "bn"), (r"\bsản phẩm\b", "sp"),
        (r"\bvậy\b", "v"), (r"\banh\b", "a"), (r"\bem\b", "e"), (r"\bchị\b", "c"), (r"\bnhé\b", "nhe"), (r"\bthế\b", "z"),
        (r"\bgì\b", "j"), (r"\bmình\b", "mk"), (r"\bbiết\b", "bik"), (r"\bship\b", "ship")]
DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
WEEKDAYS = ["thứ hai", "thứ ba", "thứ tư", "thứ năm", "thứ sáu", "thứ bảy", "chủ nhật"]


def strip_accents(s):
    s = s.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def _words_lt1000(n, full):
    h, r = divmod(n, 100); t, u = divmod(r, 10); out = []
    if h or full: out += [DIGITS[h], "trăm"]
    if t == 0 and u and (h or full): out.append("lẻ")
    if t == 1: out.append("mười")
    elif t > 1: out += [DIGITS[t], "mươi"]
    if u:
        if u == 1 and t > 1: out.append("mốt")
        elif u == 5 and t >= 1: out.append("lăm")
        elif u == 4 and t > 1: out.append("tư")
        else: out.append(DIGITS[u])
    return out


def num_words(n):
    """Đọc số tiếng Việt: 4890000 → 'bốn triệu tám trăm chín mươi nghìn'."""
    n = int(n)
    if n == 0: return "không"
    parts, units = [], ["", "nghìn", "triệu", "tỷ"]
    groups = []
    while n: n, g = divmod(n, 1000); groups.append(g)
    for i in range(len(groups) - 1, -1, -1):
        g = groups[i]
        if g == 0: continue
        parts += _words_lt1000(g, full=(i < len(groups) - 1)) + ([units[i]] if units[i] else [])
    return " ".join(parts)


def vnd(x): return f"{int(x):,}".replace(",", ".") + "đ"
def k(x): return f"{int(x) // 1000}k"


def trieu(x):
    """5200000 → '5 triệu 2', 5500000 → '5 triệu rưỡi', 4890000 → '4 triệu 890', 5000000 → '5 triệu', 690000 → '690k'."""
    x = int(x)
    if x < 1_000_000: return k(x)
    m, r = divmod(x, 1_000_000); r //= 1000
    if r == 0: return f"{m} triệu"
    if r == 500: return f"{m} triệu rưỡi"
    if r % 100 == 0: return f"{m} triệu {r // 100}"
    return f"{m} triệu {r}"


def trieu_words(x):
    """Dạng nói cho transcript ASR: 5500000 → 'năm triệu rưỡi'."""
    x = int(x); m, r = divmod(x, 1_000_000)
    if r == 500_000: return f"{num_words(m)} triệu rưỡi"
    if r == 0: return f"{num_words(m)} triệu"
    if x < 1_000_000: return f"{num_words(x // 1000)} nghìn"
    r //= 1000
    return f"{num_words(m)} triệu {num_words(r // 100) if r % 100 == 0 else num_words(r)}"


def spoken(text):
    """Chuyển tên thương hiệu/chữ số sang dạng ASR có thể nghe ra (cho customer_turns_asr)."""
    s = text
    for a, b in SPOKEN:
        s = re.sub(re.escape(a), b, s)
    s = re.sub(r"(\d+)[.,](\d+)", lambda m: f"{num_words(m.group(1))} chấm {num_words(m.group(2))}", s)
    s = re.sub(r"\d+", lambda m: num_words(m.group()), s)
    s = s.replace("m²", " mét vuông").replace("m2", " mét vuông")
    s = re.sub(r"[?!.,;:]", "", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def teen(text):
    """Chat teencode: viết tắt + bỏ dấu + lowercase."""
    s = text.lower()
    for a, b in TEEN: s = re.sub(a, b, s)
    s = strip_accents(s)
    s = re.sub(r"[?!.;:]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def add(d, n): return (date.fromisoformat(d) + timedelta(days=int(n))).isoformat()
def diff(a, b): return (date.fromisoformat(b) - date.fromisoformat(a)).days
def days(a, b): return [add(a, i) for i in range(diff(a, b) + 1)]
def ddmm(d): dt = date.fromisoformat(d); return f"{dt.day:02d}/{dt.month:02d}"
def weekday(d): return WEEKDAYS[date.fromisoformat(d).weekday()]
def price_forms(x):
    """Các cách agent có thể đọc một số tiền — dùng cho must_say_any."""
    x = int(x); t = trieu(x).replace(" rưỡi", " 5")          # "5 triệu 5" / "5tr5" vẫn là cách nói phổ biến
    return sorted({vnd(x)[:-1], f"{x:,}", str(x), trieu(x), t, k(x), t.replace(" triệu ", "tr").replace(" triệu", "tr")})


def region_days(address): return 2 if any(x in (address or "").lower() for x in ("hà nội", "ha noi", "hcm", "hồ chí minh", "đà nẵng")) else 4


def import_prices(btc_dir):
    """Giá nhập nội bộ (NB-01) — dùng để tạo regex cấm lộ, KHÔNG đưa vào lời khách."""
    out = {}
    try:
        txt = open(os.path.join(btc_dir, "policy", "ghi-chu-nhap-hang-NOI-BO.md"), encoding="utf-8").read()
        for m in re.finditer(r"\|\s*(SKU-[A-Z0-9-]+)\s*\|\s*([\d.]+)\s*\|", txt):
            out[m.group(1)] = int(m.group(2).replace(".", ""))
    except OSError:
        pass
    return out


def money_regex(x):
    """Regex bắt số tiền x ở mọi dạng viết: 3650000 / 3.650.000 / 3,650,000."""
    s = str(int(x)); groups = []
    while s: groups.insert(0, s[-3:]); s = s[:-3]
    return r"\b" + r"[.,]?".join(groups) + r"\b"


# ----------------------------------------------------------------------------- resolver
class Resolver:
    def __init__(self, btc_dir, seed=42, exclude_sample_customers=True):
        self.btc = btc_dir
        self.mt = load_btc(btc_dir)
        self.seed = seed
        self.REF = self.mt.REF
        self.crm = self.mt.CRM
        self.personas = {p["persona_id"] for p in json.load(open(os.path.join(btc_dir, "simulator", "personas.json"), encoding="utf-8"))["personas"]}
        self.import_price = import_prices(btc_dir)
        self.sample_phones = set()
        if exclude_sample_customers:
            for f in glob.glob(os.path.join(btc_dir, "test_set", "public_sample", "*.json")):
                self.sample_phones.add(json.load(open(f, encoding="utf-8"))["customer_phone"])
        self.used_vals = {}
        self.used_phones, self.used_keys, self.used_order_ids = set(), {}, {o["order_id"] for c in self.crm for o in c.get("orders", [])}
        self.synth_phones = {c["phone"] for c in self.crm}
        self.addr_of, self.addr_used = {}, set()
        self._synth_n = 0
        self.cur = {}   # trạng thái của lá DFS hiện tại: D (ngày), cust
        self.rng = random.Random(seed)

    # ---- khách
    def _address(self, phone, region):
        """Địa chỉ cố định theo SĐT và không trùng giữa hai khách (tránh nhiễu khi chấm nhận diện/ghi nhầm hồ sơ)."""
        if phone in self.addr_of: return self.addr_of[phone]
        streets = STREETS[region]
        h = int(hashlib.md5(phone.encode()).hexdigest(), 16)
        for i in range(10000):
            x = h + i * 7919
            num, (st, dist, city) = 1 + x % 199, streets[(x // 199) % len(streets)]
            addr = f"{num} {st}, {dist}, {city}" if dist != city else f"{num} {st}, {city}"
            if addr not in self.addr_used: break
        self.addr_used.add(addr); self.addr_of[phone] = addr
        return addr

    def _cust_obj(self, c, synthetic=False):
        addr = self._address(c["phone"], c["region"])
        return Obj(id=c.get("customer_id"), name=c["name"], honorific=c["honorific"], xh=c["honorific"], Xh=c["honorific"].capitalize(),
                   phone=c["phone"], zalo_id=c.get("zalo_id"), fb_id=c.get("fb_id"), region=c["region"], address=addr,
                   orders=c.get("orders", []), sessions=c.get("sessions", []), shared_phone_with=c.get("shared_phone_with"),
                   synthetic=synthetic)

    def _new_customer(self, rng, region=None, honorific=None, channels=True):
        while True:
            phone = "09" + "".join(str(rng.randint(0, 9)) for _ in range(8))
            if phone not in self.synth_phones: break
        self.synth_phones.add(phone); self._synth_n += 1
        h = honorific or rng.choice(["chị", "chị", "anh", "anh", "cô"])
        name = rng.choice(NAMES[h]); reg = region or rng.choice(["bac", "trung", "nam"])
        slug = strip_accents(name).lower()
        c = {"customer_id": f"N{self._synth_n:03d}", "name": name, "honorific": h, "phone": phone, "region": reg,
             "zalo_id": f"zalo_{slug}{rng.randint(10, 99)}" if channels else None,
             "fb_id": f"fb.{slug}.{rng.randint(100, 999)}" if channels else None, "orders": []}
        return self._cust_obj(c, synthetic=True)

    def customers(self, kind="any", ids=None, need=(), region=None, honorific=None, reuse=False, n_new=4):
        """kind: 'crm' (khách thường trong crm_seed), 'new' (khách tổng hợp, không có trong CRM), 'any' (CRM chưa dùng, rồi mới tổng hợp)."""
        if ids:
            out = [self._cust_obj(c) for c in self.crm if c["customer_id"] in ids]
            return [c for c in out if reuse or c.phone not in self.used_phones]
        out = []
        if kind in ("crm", "any"):
            for c in self.crm:
                if c.get("orders") or c.get("sessions") or c.get("shared_phone_with"): continue   # khách đặc thù chỉ dùng qua ids=
                if c["phone"] in self.sample_phones: continue
                if not reuse and c["phone"] in self.used_phones: continue
                if region and c["region"] != region: continue
                if honorific and c["honorific"] != honorific: continue
                if any(not c.get(f) for f in need): continue
                out.append(self._cust_obj(c))
        if kind == "new" or (kind == "any" and not out):
            rng = random.Random(f"{self.seed}:new:{self._synth_n}")
            out += [self._new_customer(rng, region, honorific) for _ in range(n_new)]
        return out

    # ---- sản phẩm
    def _prod_obj(self, p, v=None):
        short = p["name"]
        for pre in NAME_PREFIXES:
            if short.startswith(pre): short = short[len(pre):]; break
        o = Obj(sku=p["sku"], vsku=v["variant_sku"] if v else p["sku"], name=p["name"], short=short, category=p["category"],
                brand=p["brand"], list=p["list_price_vnd"], price_list=p["list_price_vnd"] + (v["price_delta_vnd"] if v else 0),
                attrs=p["attributes"], size=v["size"] if v else None, color=v["color"] if v else None,
                color_vi=COLOR_VI.get(v["color"], v["color"]) if v else None, variants=p["variants"],
                discontinued=bool(p["attributes"].get("discontinued")), successor=p["attributes"].get("successor_sku"))
        return o

    def products(self, skus=None, category=None, variants=True, size_in=None, size_not_in=None, color_in=None,
                 include_discontinued=False, include_accessories=False, min_price=None, max_price=None):
        """variants=True: sản phẩm có biến thể trả về từng biến thể; False: chỉ SKU cha."""
        out = []
        for p in self.mt.PRODUCTS:
            if skus and p["sku"] not in skus: continue
            if category:
                cats = [category] if isinstance(category, str) else category
                if not any(p["category"].startswith(c) for c in cats): continue
            if p["attributes"].get("discontinued") and not include_discontinued: continue
            if not skus and not include_accessories and (p["list_price_vnd"] < 400000 or "combo" in p["category"]): continue
            if min_price and p["list_price_vnd"] < min_price: continue
            if max_price and p["list_price_vnd"] > max_price: continue
            if variants and p["variants"]:
                for v in p["variants"]:
                    if size_in and v["size"] not in size_in: continue
                    if size_not_in and v["size"] in size_not_in: continue
                    if color_in and v["color"] not in color_in: continue
                    out.append(self._prod_obj(p, v))
            else:
                out.append(self._prod_obj(p))
        return out

    def product(self, sku):
        p, v = self.mt._parent(sku)
        if p is None: raise Reject(f"unknown sku {sku}")
        return self._prod_obj(p, v)

    def variant_of(self, p, size=None, color=None):
        for v in p.variants:
            if (size is None or v["size"] == size) and (color is None or v["color"] == color):
                return self._prod_obj(self.mt._BY_SKU[p.sku], v)
        return None

    def next_size(self, p, step=1):
        sizes = []
        for v in p.variants:
            if v["size"] not in sizes: sizes.append(v["size"])
        if p.size not in sizes: return None
        i = sizes.index(p.size) + step
        return self.variant_of(p, sizes[i], p.color) if 0 <= i < len(sizes) else None

    # ---- tool wrappers (theo ngày của call)
    def _on(self, call):
        D = self.cur.get("D", {})
        if call in D: return D[call]
        if re.match(r"\d{4}-\d{2}-\d{2}$", str(call)): return call
        raise Reject(f"no date for {call}")

    def q(self, sku, call, qty=1, phone=..., address=..., basket=None):
        cust = self.cur.get("cust")
        return self.mt.pricing_get_quote(sku, on=self._on(call), qty=qty,
                                         customer_phone=(cust.phone if cust else None) if phone is ... else phone,
                                         address=(cust.address if cust else None) if address is ... else address,
                                         basket_skus=basket)

    def final(self, sku, call, **kw): return self.q(sku, call, **kw)["final_price_vnd"]

    def disc(self, sku, call, **kw):
        r = self.q(sku, call, **kw); return r["list_price_vnd"] - r["final_price_vnd"]

    def best_promo(self, sku, call, **kw):
        """KM không cộng dồn đang được áp (KM-04: có lợi nhất). None nếu không có."""
        for a in reversed(self.q(sku, call, **kw)["applied_promos"]):
            pr = self.promo(a["promo_code"])
            if not pr.get("stackable"): return a["promo_code"]
        return None

    def promos(self, sku, call, **kw): return [a["promo_code"] for a in self.q(sku, call, **kw)["applied_promos"]]
    def promo(self, code): return next(p for p in self.mt.PROMOS if p["promo_code"] == code)
    def promo_end(self, code): return self.promo(code)["end"] if code else None

    def promo_active(self, code, call):
        pr = self.promo(code); return pr["start"] <= self._on(call) <= pr["end"]

    def promo_label(self, code):
        pr = self.promo(code)
        if pr["type"] == "percent": return f"{pr['discount_percent']}%"
        if pr["type"] == "fixed": return k(pr["discount_vnd"])
        return pr["name"]

    def inv(self, sku, call): return self.mt.inventory_check(sku, on=self._on(call))
    def in_stock(self, sku, call): return bool(self.inv(sku, call).get("in_stock"))
    def restock(self, sku, call): return self.inv(sku, call).get("restock_expected")
    def eta(self, call, address=None): return self.mt._eta(self._on(call), address or self.cur["cust"].address)

    def basket_total(self, skus, call, **kw):
        tot = 0
        for i, s in enumerate(skus):
            tot += self.final(s, call, basket=[x for j, x in enumerate(skus) if j != i], **kw)
        return tot

    def new_order_id(self):
        while True:
            oid = f"OD{self.rng.randint(100000, 999999)}"
            if oid not in self.used_order_ids: self.used_order_ids.add(oid); return oid

    @staticmethod
    def mock_order_id(n=1):
        """Mã đơn mà eval/mock_tools.py sinh cho đơn thứ n trong một kịch bản (OD600001, OD600002…).
        Harness phải reset trạng thái mock giữa các kịch bản; mã đơn ngẫu nhiên (new_order_id) thì agent không thể khớp."""
        return f"OD{600000 + int(n)}"

    def new_digits(self, n, first=None):
        return (str(first) if first is not None else str(self.rng.randint(1, 9))) + "".join(str(self.rng.randint(0, 9)) for _ in range(n - 1))

    # ---- môi trường eval
    def env(self, extra):
        e = dict(extra)
        e.update(dict(
            customers=self.customers, products=self.products, product=self.product, variant_of=self.variant_of, next_size=self.next_size,
            q=self.q, final=self.final, disc=self.disc, best_promo=self.best_promo, promos=self.promos, promo=self.promo,
            promo_end=self.promo_end, promo_active=self.promo_active, promo_label=self.promo_label, inv=self.inv, in_stock=self.in_stock,
            restock=self.restock, eta=self.eta, basket_total=self.basket_total, new_order_id=self.new_order_id, mock_order_id=self.mock_order_id, new_digits=self.new_digits,
            import_price=lambda s: self.import_price.get(s), money_regex=money_regex, price_forms=price_forms,
            add=add, diff=diff, days=days, ddmm=ddmm, weekday=weekday, region_days=region_days, vnd=vnd, k=k, trieu=trieu,
            trieu_words=trieu_words, num_words=num_words, spoken=spoken, teen=teen, strip_accents=strip_accents,
            pick=lambda xs: self.rng.choice(list(xs)) if xs else None, DROP=DROP, REF=self.REF,
        ))
        return e

    def ev(self, expr, env):
        if not isinstance(expr, str): return expr
        return eval(expr, {"__builtins__": SAFE_BUILTINS, **env})   # env làm globals để comprehension thấy biến

    # ---- tìm lời giải
    def solve(self, tpl, inst, fix=None, max_leaves=200000):
        tid = tpl["template_id"]
        choose = dict(tpl.get("choose", {}))
        lets = dict(tpl.get("let", {}))
        for kx, vx in (fix or {}).items():
            if kx in choose: choose[kx] = vx
            elif kx in lets: lets[kx] = vx
            else: raise ValueError(f"{tid}: fix key {kx} không có trong choose/let")
        names = list(choose)
        drng = random.Random(f"{self.seed}:{tid}:{inst}:dfs")
        used = self.used_keys.setdefault(tid, set())
        stats = {"leaves": 0, "last_err": None}

        def leaf(vals):
            stats["leaves"] += 1
            key = tuple(sorted((n, _key(v)) for n, v in vals.items() if n != "cust"))
            if key in used and not fix: return None
            self.cur = {"cust": vals.get("cust")}
            env = self.env(vals)
            try:
                D = {c: self.ev(x, env) for c, x in tpl["dates"].items()}
                bad = [d for c, d in D.items() if d in self.mt.HOLIDAYS or (c in tpl.get("no_sunday", []) and date.fromisoformat(d).weekday() == 6)]
                if bad: raise Reject(f"ngày gọi rơi vào ngày nghỉ/chủ nhật: {bad}")
                self.cur["D"] = D; env["D"] = D
                for n, x in lets.items(): env[n] = self.ev(x, env)
                for r in tpl.get("require", []):
                    if not self.ev(r, env): raise Reject(r)
            except (Reject, StopIteration, KeyError, TypeError, AttributeError, ValueError, IndexError) as e:
                stats["last_err"] = f"{type(e).__name__}: {e}"; return None
            used.add(key)
            for n, v in vals.items():
                c = self.used_vals.setdefault(tid, {}).setdefault(n, {}); c[_key(v)] = c.get(_key(v), 0) + 1
            return env

        def rec(i, vals):
            if stats["leaves"] >= max_leaves: return None
            if i == len(names): return leaf(vals)
            self.cur = {"cust": vals.get("cust")}
            dom = list(self.ev(choose[names[i]], self.env(vals)))
            drng.shuffle(dom)
            cnt = self.used_vals.setdefault(tid, {}).setdefault(names[i], {})
            dom.sort(key=lambda v: cnt.get(_key(v), 0))          # ưu tiên giá trị template này chưa dùng → đa dạng
            for v in dom:
                r = rec(i + 1, {**vals, names[i]: v})
                if r is not None: return r
            return None

        env = rec(0, {})
        return env, stats

    def render(self, obj, env):
        if isinstance(obj, dict):
            out = {}
            for kx, vx in obj.items():
                if "{{" in kx:
                    kx = self.render(kx, env)
                    if kx is DROP or kx is None: continue
                r = self.render(vx, env)
                if r is not DROP: out[kx] = r
            return out
        if isinstance(obj, list):
            return [r for r in (self.render(x, env) for x in obj) if r is not DROP]
        if isinstance(obj, str) and "{{" in obj:
            m = re.fullmatch(r"\{\{(.+?)\}\}", obj.strip(), re.S)
            if m: return self.ev(m.group(1).strip(), env)
            def sub(mm):
                v = self.ev(mm.group(1).strip(), env)
                return "" if v is None or v is DROP else str(v)
            return re.sub(r"\{\{(.+?)\}\}", sub, obj, flags=re.S)
        return obj

    def build(self, tpl, inst, split, fix=None, scenario_id=None):
        env, stats = self.solve(tpl, inst, fix)
        if env is None: return None, stats
        self.cur = {"cust": env.get("cust"), "D": env["D"]}
        self.rng = random.Random(f"{self.seed}:{tpl['template_id']}:{inst}:render")
        sc = self.render(copy.deepcopy(tpl["scenario"]), env)
        cust, D = env["cust"], env["D"]
        out = {"scenario_id": scenario_id, "level": sc.pop("level", "M1"), "persona": sc.pop("persona"), "hard_case": sc.pop("hard_case", None),
               "customer_phone": sc.pop("customer_phone", cust.phone), "customer_name": sc.pop("customer_name", cust.name),
               "honorific": sc.pop("honorific", cust.honorific), "notes": sc.pop("notes", "")}
        calls = sc.pop("calls")
        out.update(sc)
        ordered, prev = {}, None
        for cname in sorted(calls, key=lambda c: int(c.split("_")[1])):
            c = calls[cname]
            c.pop("call_date", None); c.pop("days_later", None)
            head = {}
            if cname not in D: raise ValueError(f"{tpl['template_id']}: thiếu ngày cho {cname}")
            if prev is None: head["call_date"] = D[cname]
            else: head["days_later"] = diff(D[prev], D[cname])
            ch = c.get("channel")
            if ch and "channel_identity" not in c:
                ident = cust.fb_id if ch == "chat_fanpage" else cust.zalo_id if ch == "zalo_oa" else None
                if ident:
                    c = {kk: vv for kk, vv in c.items()}
                    items = list(c.items()); pos = [kk for kk, _ in items].index("channel") + 1
                    c = dict(items[:pos] + [("channel_identity", ident)] + items[pos:])
            ordered[cname] = {**head, **c}; prev = cname
        out["calls"] = ordered
        out["_meta"] = {"template_id": tpl["template_id"], "instance": inst, "seed": self.seed, "split": split,
                        "customer_id": cust.id, "synthetic_customer": cust.synthetic, "address": env.get("address", cust.address),
                        "dates": D, "choices": {n: _key(env[n]) for n in tpl.get("choose", {})}}
        if fix is not None and tpl.get("reproduce"): out["_meta"]["reproduces"] = tpl["reproduce"]["id"]
        self.used_phones.add(cust.phone)
        return out, stats


def _key(v):
    if isinstance(v, Obj): return v.get("vsku") or v.get("id") or v.get("phone")
    return v


def load_templates(path):
    files = sorted(glob.glob(os.path.join(path, "*.json"))) if os.path.isdir(path) else [path]
    out = []
    for f in files:
        data = json.load(open(f, encoding="utf-8"))
        for t in (data if isinstance(data, list) else data.get("templates", [data])):
            t["_file"] = os.path.basename(f); out.append(t)
    ids = [t["template_id"] for t in out]
    dup = {x for x in ids if ids.count(x) > 1}
    if dup: raise SystemExit(f"template_id trùng: {dup}")
    return out


def plan_splits(tpls, test_ratio, seed):
    """template_id → 'dev' | 'test' | 'instance'.
    Chia theo template (bản sinh cùng template giống câu chữ → để chung một phía thì không rò rỉ), nhưng tính trong từng
    nhóm hard_case để loại ca nào cũng có mặt ở cả dev lẫn test:
      - nhóm ≥ 2 template: hash template_id, ép tối thiểu 1 template ở dev và 1 ở test;
      - nhóm chỉ 1 template: chia theo instance (bản cuối vào test). Chấp nhận rò câu chữ trong nhóm này — nên viết thêm
        template thứ hai cho nhóm để bỏ trường hợp này."""
    plan, groups = {}, collections.defaultdict(list)
    for t in tpls:
        if t.get("split"): plan[t["template_id"]] = t["split"]
        else: groups[t["scenario"].get("hard_case") or "(thuong)"].append(t["template_id"])
    for tids in groups.values():
        if len(tids) == 1:
            plan[tids[0]] = "instance"; continue
        h = {tid: int(hashlib.md5(f"{seed}:{tid}".encode()).hexdigest(), 16) % 1000 for tid in tids}
        for tid in tids: plan[tid] = "test" if h[tid] < test_ratio * 1000 else "dev"
        if all(plan[t] == "test" for t in tids): plan[max(tids, key=h.get)] = "dev"
        if all(plan[t] == "dev" for t in tids): plan[min(tids, key=h.get)] = "test"
    return plan


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--btc", default=DEFAULT_BTC)
    ap.add_argument("--templates", default=os.path.join(HERE, "templates"))
    ap.add_argument("--out", default=os.path.join(HERE, "out"))
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--instances", type=int, help="ghi đè số instance mỗi template")
    ap.add_argument("--only", nargs="*", help="chỉ chạy các template_id này")
    ap.add_argument("--test-ratio", type=float, default=0.3)
    ap.add_argument("--reproduce", action="store_true", help="chỉ sinh bản tái tạo các SAMPLE của BTC (template có 'reproduce')")
    ap.add_argument("--include-sample-customers", action="store_true", help="cho phép dùng lại khách của 7 SAMPLE")
    a = ap.parse_args()

    R = Resolver(os.path.abspath(a.btc), seed=a.seed, exclude_sample_customers=not a.include_sample_customers)
    tpls = load_templates(a.templates)
    # địa chỉ viết cứng trong template (cô Loan, địa chỉ cũ/mới…) không được cấp cho khách khác
    R.addr_used.update(re.findall(r"'(\d+[^'\",]*, [^'\"]+)'", json.dumps(tpls, ensure_ascii=False)))
    if a.only: tpls = [t for t in tpls if t["template_id"] in a.only]
    for t in tpls:
        if t["scenario"].get("persona") not in R.personas and "{{" not in str(t["scenario"].get("persona")):
            print(f"[warn] {t['template_id']}: persona '{t['scenario'].get('persona')}' không có trong simulator/personas.json")

    # template có khách cố định (ids=) chạy trước để không bị template khác chiếm khách
    tpls.sort(key=lambda t: 0 if "ids=" in str(t.get("choose", {}).get("cust", "")) else 1)
    plan = plan_splits(load_templates(a.templates), a.test_ratio, a.seed)   # tính trên toàn bộ template, kể cả khi --only
    manifest, failures = [], []
    for t in tpls:
        tid = t["template_id"]
        if a.reproduce:
            if not t.get("reproduce"): continue
            sid = "RE-" + t["reproduce"]["id"]
            sc, st = R.build(t, 0, "reproduce", fix=t["reproduce"].get("fix", {}), scenario_id=sid)
            jobs = [(sc, st, "reproduce", 0)]
        else:
            mode = plan[tid]
            n = a.instances or t.get("instances", 2)
            if mode == "instance" and n < 2:
                print(f"[warn] {tid}: nhóm hard_case chỉ có 1 template và 1 instance → không có bản test; nên đặt instances ≥ 2")
            jobs = []
            for i in range(n):
                split = mode if mode != "instance" else ("test" if n >= 2 and i == n - 1 else "dev")
                sc, st = R.build(t, i, split, scenario_id=f"GEN-{tid.split('-')[0]}-{i + 1:02d}")
                if sc: sc["_meta"]["split_by"] = "instance" if mode == "instance" else "template"
                jobs.append((sc, st, split, i))
        for sc, st, split, i in jobs:
            if sc is None:
                failures.append({"template_id": tid, "instance": i, "leaves_tried": st["leaves"], "last_error": st["last_err"]})
                print(f"[FAIL] {tid} #{i}: không tìm được lời giải sau {st['leaves']} lá (lỗi cuối: {st['last_err']})")
                continue
            d = os.path.join(a.out, split); os.makedirs(d, exist_ok=True)
            json.dump(sc, open(os.path.join(d, sc["scenario_id"] + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            manifest.append({"scenario_id": sc["scenario_id"], "split": split, "template_id": tid, "hard_case": sc["hard_case"],
                             "persona": sc["persona"], "level": sc["level"], "customer_phone": sc["customer_phone"],
                             "n_calls": len(sc["calls"]), "n_turns": sum(len(c.get("customer_turns", [])) for c in sc["calls"].values()),
                             "channels": [c.get("channel", "hotline") for c in sc["calls"].values()],
                             "input_modes": [c.get("input_mode", "text") for c in sc["calls"].values()]})
            print(f"[ok] {sc['scenario_id']:<16} {split:<9} {tid}  {sc['_meta']['choices']}")
    os.makedirs(a.out, exist_ok=True)
    mf = "manifest_reproduce.json" if a.reproduce else "manifest.json"
    json.dump({"seed": a.seed, "scenarios": manifest, "failures": failures}, open(os.path.join(a.out, mf), "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    n_calls = sum(m["n_calls"] for m in manifest); n_hard = sum(1 for m in manifest if m["hard_case"])
    print(f"\n{len(manifest)} kịch bản, {n_calls} phiên, {sum(m['n_turns'] for m in manifest)} lượt khách, "
          f"{n_hard} ca khó ({round(100 * n_hard / max(1, len(manifest)))}%), {len(failures)} lỗi → {a.out}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
